from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from vinted_radar.domain.events import (
    EventEnvelope,
    JsonValue,
    canonical_json,
    ensure_json_object,
    normalize_json_value,
    sanitize_storage_segment,
)
from vinted_radar.domain.manifests import EvidenceManifest
from vinted_radar.platform.config import PlatformConfig, load_platform_config
from vinted_radar.platform.object_store import ObjectStoreObject, S3ObjectStore
from vinted_radar.platform.outbox import OutboxPublishResult, PostgresOutbox
from vinted_radar.platform.postgres_repository import POSTGRES_CURRENT_STATE_SINK

PARQUET_LAKE_SCHEMA_VERSION = 1
PARQUET_LAKE_COMPRESSION = "zstd"
PARQUET_CONTENT_TYPE = "application/vnd.apache.parquet"


@dataclass(frozen=True, slots=True)
class LakeWriteResult:
    batch_event: EventEnvelope
    manifest: EvidenceManifest
    event_object: ObjectStoreObject
    parquet_object: ObjectStoreObject
    manifest_object: ObjectStoreObject
    row_count: int
    parquet_schema_version: int
    parquet_compression: str
    partition: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "batch_event_id": self.batch_event.event_id,
            "manifest_id": self.manifest.manifest_id,
            "row_count": self.row_count,
            "parquet_schema_version": self.parquet_schema_version,
            "parquet_compression": self.parquet_compression,
            "partition": dict(self.partition),
            "event_object": self.event_object.as_dict(),
            "parquet_object": self.parquet_object.as_dict(),
            "manifest_object": self.manifest_object.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class EvidenceBatchEmissionResult:
    batch_event: EventEnvelope
    row_count: int
    lake_write: LakeWriteResult | None = None
    outbox_publish: OutboxPublishResult | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.batch_event.event_id,
            "event_type": self.batch_event.event_type,
            "row_count": self.row_count,
            "manifest_id": None if self.lake_write is None else self.lake_write.manifest.manifest_id,
            "lake_write": None if self.lake_write is None else self.lake_write.as_dict(),
            "outbox_publish": None if self.outbox_publish is None else self.outbox_publish.as_dict(),
        }


class ParquetLakeWriter:
    def __init__(
        self,
        object_store: S3ObjectStore,
        *,
        raw_events_prefix: str,
        manifests_prefix: str,
        parquet_prefix: str,
        manifest_schema_version: int = 1,
        parquet_schema_version: int = PARQUET_LAKE_SCHEMA_VERSION,
        parquet_compression: str = PARQUET_LAKE_COMPRESSION,
    ) -> None:
        if manifest_schema_version < 1:
            raise ValueError("manifest_schema_version must be >= 1")
        if parquet_schema_version < 1:
            raise ValueError("parquet_schema_version must be >= 1")
        self.object_store = object_store
        self.raw_events_prefix = raw_events_prefix
        self.manifests_prefix = manifests_prefix
        self.parquet_prefix = parquet_prefix
        self.manifest_schema_version = manifest_schema_version
        self.parquet_schema_version = parquet_schema_version
        self.parquet_compression = parquet_compression

    @classmethod
    def from_config(
        cls,
        config: PlatformConfig,
        *,
        client: object | None = None,
        parquet_schema_version: int = PARQUET_LAKE_SCHEMA_VERSION,
        parquet_compression: str = PARQUET_LAKE_COMPRESSION,
    ) -> ParquetLakeWriter:
        return cls(
            S3ObjectStore.from_config(config, client=client),
            raw_events_prefix=config.storage.raw_events,
            manifests_prefix=config.storage.manifests,
            parquet_prefix=config.storage.parquet,
            manifest_schema_version=config.schema_versions.manifests,
            parquet_schema_version=parquet_schema_version,
            parquet_compression=parquet_compression,
        )

    def write_batch(
        self,
        *,
        batch_event: EventEnvelope,
        rows: Sequence[Mapping[str, Any]],
        manifest_metadata: Mapping[str, Any] | None = None,
        manifest_type: str = "parquet-evidence-batch",
    ) -> LakeWriteResult:
        if not rows:
            raise ValueError("rows cannot be empty")

        occurred_on = _occurred_on(batch_event.occurred_at)
        partition = {
            "event_type": sanitize_storage_segment(batch_event.event_type),
            "occurred_on": occurred_on,
            "schema_version": f"v{self.parquet_schema_version}",
        }
        parquet_key = self.parquet_object_key(batch_event)
        event_key = batch_event.object_key(self.raw_events_prefix)

        event_object = self.object_store.put_text(
            key=event_key,
            text=batch_event.to_json(),
            content_type="application/json",
            metadata={
                "event_id": batch_event.event_id,
                "event_type": batch_event.event_type,
                "schema_version": batch_event.schema_version,
                "producer": batch_event.producer,
            },
        )

        parquet_bytes = self._build_parquet_bytes(batch_event=batch_event, rows=rows)
        parquet_object = self.object_store.put_bytes(
            key=parquet_key,
            data=parquet_bytes,
            content_type=PARQUET_CONTENT_TYPE,
            metadata={
                "event_id": batch_event.event_id,
                "event_type": batch_event.event_type,
                "occurred_on": occurred_on,
                "schema_version": self.parquet_schema_version,
                "compression": self.parquet_compression,
                "row_count": len(rows),
            },
        )

        metadata = {
            "writer": "vinted_radar.platform.lake_writer",
            "parquet_schema_version": self.parquet_schema_version,
            "parquet_compression": self.parquet_compression,
            "parquet_object_key": parquet_object.key,
            "row_count": len(rows),
            "occurred_on": occurred_on,
        }
        if manifest_metadata:
            metadata.update(ensure_json_object(manifest_metadata, field_name="manifest_metadata"))

        manifest = EvidenceManifest.from_event(
            batch_event,
            bucket=self.object_store.bucket,
            entries=(
                event_object.as_manifest_entry(logical_name="batch-event"),
                parquet_object.as_manifest_entry(logical_name="parquet-batch"),
            ),
            schema_version=self.manifest_schema_version,
            manifest_type=manifest_type,
            metadata=metadata,
        )
        manifest_key = manifest.object_key(self.manifests_prefix)
        manifest_object = self.object_store.put_text(
            key=manifest_key,
            text=manifest.to_json(),
            content_type="application/json",
            metadata={
                "manifest_id": manifest.manifest_id,
                "event_id": manifest.event_id,
                "manifest_type": manifest.manifest_type,
                "schema_version": manifest.schema_version,
            },
        )

        return LakeWriteResult(
            batch_event=batch_event,
            manifest=manifest,
            event_object=event_object,
            parquet_object=parquet_object,
            manifest_object=manifest_object,
            row_count=len(rows),
            parquet_schema_version=self.parquet_schema_version,
            parquet_compression=self.parquet_compression,
            partition=partition,
        )

    def parquet_object_key(self, batch_event: EventEnvelope) -> str:
        occurred_on = _occurred_on(batch_event.occurred_at)
        event_type = sanitize_storage_segment(batch_event.event_type)
        return (
            f"{self.parquet_prefix.rstrip('/')}/v{self.parquet_schema_version}"
            f"/event_type={event_type}/occurred_on={occurred_on}/{batch_event.event_id}.parquet"
        )

    def read_table(self, key: str) -> pa.Table:
        result = self.object_store.get_bytes(key)
        return pq.read_table(pa.BufferReader(result.data))

    def read_rows(self, key: str) -> list[dict[str, Any]]:
        return self.read_table(key).to_pylist()

    def _build_parquet_bytes(
        self,
        *,
        batch_event: EventEnvelope,
        rows: Sequence[Mapping[str, Any]],
    ) -> bytes:
        storage_rows = [
            _build_storage_row(
                batch_event=batch_event,
                row=row,
                row_index=index,
                parquet_schema_version=self.parquet_schema_version,
            )
            for index, row in enumerate(rows)
        ]
        table = pa.Table.from_pylist(storage_rows)
        table = table.replace_schema_metadata(
            {
                b"writer": b"vinted_radar.platform.lake_writer",
                b"batch_event_id": batch_event.event_id.encode("utf-8"),
                b"batch_event_type": batch_event.event_type.encode("utf-8"),
                b"batch_event_schema_version": str(batch_event.schema_version).encode("utf-8"),
                b"parquet_schema_version": str(self.parquet_schema_version).encode("utf-8"),
                b"parquet_compression": self.parquet_compression.encode("utf-8"),
            }
        )

        with tempfile.TemporaryDirectory(prefix="vinted-radar-lake-") as tmp_dir:
            stage_path = Path(tmp_dir) / "batch.parquet"
            pq.write_table(
                table,
                stage_path,
                compression=self.parquet_compression,
                use_dictionary=True,
            )
            return stage_path.read_bytes()


class CollectorEvidencePublisher:
    def __init__(
        self,
        *,
        lake_writer: ParquetLakeWriter | None = None,
        outbox: PostgresOutbox | None = None,
        sinks: Sequence[str] = (),
        closeables: Sequence[object] = (),
    ) -> None:
        self.lake_writer = lake_writer
        self.outbox = outbox
        self.sinks = _normalize_sinks(sinks)
        self._closeables = tuple(closeables)

    @classmethod
    def from_environment(
        cls,
        *,
        config: PlatformConfig | None = None,
        s3_client: object | None = None,
        postgres_connection: object | None = None,
        ensure_bucket: bool = True,
    ) -> CollectorEvidencePublisher | None:
        resolved_config = load_platform_config() if config is None else config
        lake_writer: ParquetLakeWriter | None = None
        outbox: PostgresOutbox | None = None
        sinks: list[str] = []
        closeables: list[object] = []

        created_s3_client = False
        created_postgres_connection = False

        if resolved_config.cutover.enable_object_storage_writes:
            lake_writer = ParquetLakeWriter.from_config(resolved_config, client=s3_client)
            if ensure_bucket:
                lake_writer.object_store.ensure_bucket()
            created_s3_client = s3_client is None
            if created_s3_client:
                closeables.append(lake_writer.object_store.client)

        if resolved_config.cutover.enable_postgres_writes:
            connection = postgres_connection
            if connection is None:
                import psycopg

                connection = psycopg.connect(resolved_config.postgres.dsn)
                created_postgres_connection = True
            outbox = PostgresOutbox(connection)
            if resolved_config.cutover.enable_clickhouse_writes:
                sinks.append("clickhouse")
            if resolved_config.cutover.enable_object_storage_writes:
                sinks.append("parquet")
                sinks.append(POSTGRES_CURRENT_STATE_SINK)
            if created_postgres_connection:
                closeables.append(connection)

        if lake_writer is None and outbox is None:
            return None
        return cls(
            lake_writer=lake_writer,
            outbox=outbox,
            sinks=sinks,
            closeables=closeables,
        )

    def emit_batch(
        self,
        *,
        batch_event: EventEnvelope,
        rows: Sequence[Mapping[str, Any]],
        manifest_metadata: Mapping[str, Any] | None = None,
        manifest_type: str = "parquet-evidence-batch",
        sinks: Sequence[str] | None = None,
    ) -> EvidenceBatchEmissionResult | None:
        if not rows:
            return None

        lake_write: LakeWriteResult | None = None
        if self.lake_writer is not None:
            lake_write = self.lake_writer.write_batch(
                batch_event=batch_event,
                rows=rows,
                manifest_metadata=manifest_metadata,
                manifest_type=manifest_type,
            )

        normalized_sinks = self.sinks if sinks is None else _normalize_sinks(sinks)
        outbox_publish: OutboxPublishResult | None = None
        if self.outbox is not None and normalized_sinks:
            outbox_publish = self.outbox.publish(
                batch_event,
                sinks=normalized_sinks,
                manifest=None if lake_write is None else lake_write.manifest,
            )

        return EvidenceBatchEmissionResult(
            batch_event=batch_event,
            row_count=len(rows),
            lake_write=lake_write,
            outbox_publish=outbox_publish,
        )

    def close(self) -> None:
        for resource in self._closeables:
            _close_resource_quietly(resource)


def _build_storage_row(
    *,
    batch_event: EventEnvelope,
    row: Mapping[str, Any],
    row_index: int,
    parquet_schema_version: int,
) -> dict[str, JsonValue]:
    normalized_row = _normalize_row_payload(row)
    return {
        "batch_event_id": batch_event.event_id,
        "batch_event_type": batch_event.event_type,
        "batch_event_schema_version": batch_event.schema_version,
        "batch_event_occurred_at": batch_event.occurred_at,
        "batch_event_occurred_on": _occurred_on(batch_event.occurred_at),
        "batch_event_partition_key": batch_event.partition_key,
        "batch_event_producer": batch_event.producer,
        "parquet_schema_version": parquet_schema_version,
        "row_index": row_index,
        **normalized_row,
    }



def _normalize_row_payload(row: Mapping[str, Any]) -> dict[str, JsonValue]:
    normalized: dict[str, JsonValue] = {}
    for key, value in row.items():
        normalized[str(key)] = _normalize_row_value(value)
    return normalized



def _normalize_row_value(value: Any) -> JsonValue:
    normalized = normalize_json_value(value)
    if isinstance(normalized, (dict, list)):
        return canonical_json(normalized)
    return normalized



def _occurred_on(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).date().isoformat()



def _normalize_sinks(sinks: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for sink in sinks:
        candidate = str(sink).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return tuple(normalized)



def _close_resource_quietly(resource: object) -> None:
    for method_name in ("close", "close_connections"):
        method = getattr(resource, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:  # noqa: BLE001
                pass
            return


__all__ = [
    "CollectorEvidencePublisher",
    "EvidenceBatchEmissionResult",
    "LakeWriteResult",
    "PARQUET_CONTENT_TYPE",
    "PARQUET_LAKE_COMPRESSION",
    "PARQUET_LAKE_SCHEMA_VERSION",
    "ParquetLakeWriter",
]
