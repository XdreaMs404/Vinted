from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry
from vinted_radar.platform.config import PlatformConfig, load_platform_config
from vinted_radar.platform.lake_writer import ParquetLakeWriter
from vinted_radar.platform.outbox import ClaimedOutboxRecord, PostgresOutbox
from vinted_radar.platform.postgres_repository import (
    POSTGRES_CURRENT_STATE_CONSUMER,
    POSTGRES_CURRENT_STATE_SINK,
    PostgresMutableTruthRepository,
)


@dataclass(frozen=True, slots=True)
class MutableTruthProjectedRecord:
    event_id: str
    event_type: str
    manifest_id: str | None
    row_count: int
    projection_status: str

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "manifest_id": self.manifest_id,
            "row_count": self.row_count,
            "projection_status": self.projection_status,
        }


@dataclass(frozen=True, slots=True)
class MutableTruthProjectionReport:
    consumer_name: str
    sink: str
    claimed_count: int
    processed_count: int
    skipped_count: int
    records: tuple[MutableTruthProjectedRecord, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "consumer_name": self.consumer_name,
            "sink": self.sink,
            "claimed_count": self.claimed_count,
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "records": [record.as_dict() for record in self.records],
        }


class MutableTruthProjectorService:
    def __init__(
        self,
        *,
        repository: PostgresMutableTruthRepository | object,
        outbox: PostgresOutbox,
        lake_writer: ParquetLakeWriter,
        sink: str = POSTGRES_CURRENT_STATE_SINK,
        consumer_name: str = POSTGRES_CURRENT_STATE_CONSUMER,
        retry_delay_seconds: float = 30.0,
        lagging_threshold_seconds: float = 300.0,
        closeables: Sequence[object] = (),
    ) -> None:
        self.repository = repository
        self.outbox = outbox
        self.lake_writer = lake_writer
        self.sink = str(sink).strip() or POSTGRES_CURRENT_STATE_SINK
        self.consumer_name = str(consumer_name).strip() or POSTGRES_CURRENT_STATE_CONSUMER
        self.retry_delay_seconds = max(float(retry_delay_seconds), 1.0)
        self.lagging_threshold_seconds = max(float(lagging_threshold_seconds), 1.0)
        self._closeables = tuple(closeables)

    @classmethod
    def from_environment(
        cls,
        *,
        config: PlatformConfig | None = None,
        postgres_connection: object | None = None,
        object_store_client: object | None = None,
        sink: str = POSTGRES_CURRENT_STATE_SINK,
        consumer_name: str = POSTGRES_CURRENT_STATE_CONSUMER,
        retry_delay_seconds: float = 30.0,
        lagging_threshold_seconds: float = 300.0,
    ) -> MutableTruthProjectorService:
        resolved_config = load_platform_config() if config is None else config
        created_postgres_connection = postgres_connection is None
        created_object_store_client = object_store_client is None

        connection = _connect_postgres(resolved_config.postgres.dsn) if postgres_connection is None else postgres_connection
        lake_writer = ParquetLakeWriter.from_config(resolved_config, client=object_store_client)
        closeables: list[object] = []
        if created_postgres_connection:
            closeables.append(connection)
        if created_object_store_client:
            closeables.append(lake_writer.object_store.client)

        return cls(
            repository=PostgresMutableTruthRepository(connection),
            outbox=PostgresOutbox(connection),
            lake_writer=lake_writer,
            sink=sink,
            consumer_name=consumer_name,
            retry_delay_seconds=retry_delay_seconds,
            lagging_threshold_seconds=lagging_threshold_seconds,
            closeables=closeables,
        )

    def close(self) -> None:
        repository_close = getattr(self.repository, "close", None)
        if callable(repository_close):
            repository_close()
        for resource in self._closeables:
            _close_resource_quietly(resource)

    def project_available(
        self,
        *,
        limit: int = 100,
        lease_seconds: int = 60,
        now: str | None = None,
        consumer_name: str | None = None,
    ) -> MutableTruthProjectionReport:
        resolved_consumer = self.consumer_name if consumer_name is None else str(consumer_name)
        claimed_at = now or _utc_now()
        claimed = self.outbox.claim_batch(
            self.sink,
            consumer_id=resolved_consumer,
            limit=max(int(limit), 1),
            lease_seconds=max(int(lease_seconds), 1),
            now=claimed_at,
        )
        if not claimed:
            self._update_checkpoint(
                consumer_name=resolved_consumer,
                status="idle",
                lag_seconds=0.0,
                last_error=None,
                metadata={"claimed_count": 0},
                updated_at=claimed_at,
            )
            return MutableTruthProjectionReport(
                consumer_name=resolved_consumer,
                sink=self.sink,
                claimed_count=0,
                processed_count=0,
                skipped_count=0,
                records=(),
            )

        processed: list[MutableTruthProjectedRecord] = []
        skipped_count = 0
        for record in claimed:
            delivered_at = _utc_now()
            manifest = self._fetch_manifest(record)
            self._update_manifest_projection(
                record=record,
                manifest=manifest,
                projection_status="pending",
                projected_at=record.event.occurred_at,
                last_error=None,
                metadata={"consumer_name": resolved_consumer, "sink": self.sink},
            )
            try:
                result = self._project_record(record, manifest=manifest)
                self.outbox.mark_delivered(
                    event_id=record.event.event_id,
                    sink=self.sink,
                    delivered_at=delivered_at,
                )
                lag_seconds = _lag_seconds(delivered_at, record.event.occurred_at)
                skipped_count += 1 if result.projection_status == "skipped" else 0
                processed.append(result)
                self._update_checkpoint(
                    consumer_name=resolved_consumer,
                    last_outbox_id=record.outbox_id,
                    last_event_id=record.event.event_id,
                    last_manifest_id=record.manifest_id,
                    last_claimed_at=record.claimed_at,
                    last_delivered_at=delivered_at,
                    status=_checkpoint_status(
                        lag_seconds=lag_seconds,
                        claimed_count=len(claimed),
                        limit=max(int(limit), 1),
                        lagging_threshold_seconds=self.lagging_threshold_seconds,
                    ),
                    lag_seconds=lag_seconds,
                    last_error=None,
                    metadata={
                        "event_type": record.event.event_type,
                        "row_count": result.row_count,
                        "projection_status": result.projection_status,
                    },
                    updated_at=delivered_at,
                )
            except Exception as exc:  # noqa: BLE001
                retry_at = _isoformat_utc(_parse_timestamp(delivered_at) + timedelta(seconds=self.retry_delay_seconds))
                self._update_manifest_projection(
                    record=record,
                    manifest=manifest,
                    projection_status="failed",
                    projected_at=delivered_at,
                    last_error=f"{type(exc).__name__}: {exc}",
                    metadata={"consumer_name": resolved_consumer, "sink": self.sink},
                )
                self.outbox.mark_failed(
                    event_id=record.event.event_id,
                    sink=self.sink,
                    error=f"{type(exc).__name__}: {exc}",
                    failed_at=delivered_at,
                    retry_at=retry_at,
                )
                self._update_checkpoint(
                    consumer_name=resolved_consumer,
                    last_outbox_id=record.outbox_id,
                    last_event_id=record.event.event_id,
                    last_manifest_id=record.manifest_id,
                    last_claimed_at=record.claimed_at,
                    last_delivered_at=None,
                    status="failed",
                    lag_seconds=_lag_seconds(delivered_at, record.event.occurred_at),
                    last_error=f"{type(exc).__name__}: {exc}",
                    metadata={"event_type": record.event.event_type, "retry_at": retry_at},
                    updated_at=delivered_at,
                )
                raise

        return MutableTruthProjectionReport(
            consumer_name=resolved_consumer,
            sink=self.sink,
            claimed_count=len(claimed),
            processed_count=len(processed),
            skipped_count=skipped_count,
            records=tuple(processed),
        )

    def _project_record(
        self,
        record: ClaimedOutboxRecord,
        *,
        manifest: EvidenceManifest,
    ) -> MutableTruthProjectedRecord:
        if record.event.event_type == "vinted.discovery.listing-seen.batch":
            rows = self._load_rows(manifest)
            run_id = str(record.event.payload["run_id"])
            self.repository.project_listing_seen_batch(
                run_id=run_id,
                listing_rows=rows,
                event_id=record.event.event_id,
                manifest_id=manifest.manifest_id,
                projected_at=record.event.occurred_at,
            )
            projection_status = "projected"
            row_count = len(rows)
        elif record.event.event_type == "vinted.state-refresh.probe.batch":
            rows = self._load_rows(manifest)
            self.repository.project_state_refresh_probes(
                probe_rows=rows,
                projected_at=record.event.occurred_at,
                event_id=record.event.event_id,
                manifest_id=manifest.manifest_id,
            )
            projection_status = "projected"
            row_count = len(rows)
        else:
            projection_status = "skipped"
            row_count = int(manifest.metadata.get("row_count") or 0)

        self._update_manifest_projection(
            record=record,
            manifest=manifest,
            projection_status=projection_status,
            projected_at=record.event.occurred_at,
            last_error=None,
            metadata={"consumer_name": self.consumer_name, "sink": self.sink},
        )
        return MutableTruthProjectedRecord(
            event_id=record.event.event_id,
            event_type=record.event.event_type,
            manifest_id=manifest.manifest_id,
            row_count=row_count,
            projection_status=projection_status,
        )

    def _fetch_manifest(self, record: ClaimedOutboxRecord) -> EvidenceManifest:
        if record.manifest_id is None:
            raise RuntimeError(
                f"Outbox event {record.event.event_id} for sink {self.sink} is missing a manifest reference."
            )
        manifest = self.outbox.fetch_manifest(record.manifest_id)
        if manifest is None:
            raise RuntimeError(
                f"Outbox event {record.event.event_id} references missing manifest {record.manifest_id}."
            )
        return manifest

    def _load_rows(self, manifest: EvidenceManifest) -> list[dict[str, Any]]:
        parquet_entry = _manifest_entry(manifest, logical_name="parquet-batch")
        rows = self.lake_writer.read_rows(parquet_entry.object_key)
        if parquet_entry.content_length < 0:
            raise RuntimeError(f"Manifest {manifest.manifest_id} contains an invalid parquet entry length.")
        return [dict(row) for row in rows]

    def _update_manifest_projection(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        projection_status: str,
        projected_at: str,
        last_error: str | None,
        metadata: Mapping[str, object] | None,
    ) -> None:
        self.repository.upsert_mutable_manifest(
            manifest_id=manifest.manifest_id,
            event_id=record.event.event_id,
            event_type=record.event.event_type,
            aggregate_type=record.event.aggregate_type,
            aggregate_id=record.event.aggregate_id,
            occurred_at=record.event.occurred_at,
            manifest_type=manifest.manifest_type,
            projection_status=projection_status,
            projected_at=projected_at,
            last_error=last_error,
            metadata={
                **dict(manifest.metadata),
                **dict(metadata or {}),
                "bucket": manifest.bucket,
            },
        )

    def _current_checkpoint(self, *, consumer_name: str) -> dict[str, object]:
        resolver = getattr(self.repository, "outbox_checkpoint", None)
        if not callable(resolver):
            return {}
        checkpoint = resolver(consumer_name=consumer_name, sink=self.sink)
        return {} if checkpoint is None else dict(checkpoint)

    def _update_checkpoint(
        self,
        *,
        consumer_name: str,
        last_outbox_id: int | None | object = _UNSET,
        last_event_id: str | None | object = _UNSET,
        last_manifest_id: str | None | object = _UNSET,
        last_claimed_at: str | None | object = _UNSET,
        last_delivered_at: str | None | object = _UNSET,
        status: str | object = _UNSET,
        lag_seconds: float | None | object = _UNSET,
        last_error: str | None | object = _UNSET,
        metadata: Mapping[str, object] | None | object = _UNSET,
        updated_at: str | None = None,
    ) -> None:
        existing = self._current_checkpoint(consumer_name=consumer_name)
        payload = {
            "consumer_name": consumer_name,
            "sink": self.sink,
            "last_outbox_id": existing.get("last_outbox_id"),
            "last_event_id": existing.get("last_event_id"),
            "last_manifest_id": existing.get("last_manifest_id"),
            "last_claimed_at": existing.get("last_claimed_at"),
            "last_delivered_at": existing.get("last_delivered_at"),
            "status": existing.get("status") or "idle",
            "lag_seconds": existing.get("lag_seconds"),
            "last_error": existing.get("last_error"),
            "metadata": dict(existing.get("metadata") or {}),
            "updated_at": updated_at or _utc_now(),
        }
        for key, value in (
            ("last_outbox_id", last_outbox_id),
            ("last_event_id", last_event_id),
            ("last_manifest_id", last_manifest_id),
            ("last_claimed_at", last_claimed_at),
            ("last_delivered_at", last_delivered_at),
            ("status", status),
            ("lag_seconds", lag_seconds),
            ("last_error", last_error),
            ("metadata", metadata),
        ):
            if value is _UNSET:
                continue
            payload[key] = value
        self.repository.update_outbox_checkpoint(
            consumer_name=consumer_name,
            sink=self.sink,
            last_outbox_id=payload["last_outbox_id"],
            last_event_id=payload["last_event_id"],
            last_manifest_id=payload["last_manifest_id"],
            last_claimed_at=payload["last_claimed_at"],
            last_delivered_at=payload["last_delivered_at"],
            status=str(payload["status"] or "idle"),
            lag_seconds=None if payload["lag_seconds"] is None else float(payload["lag_seconds"]),
            last_error=None if payload["last_error"] is None else str(payload["last_error"]),
            metadata=dict(payload["metadata"] or {}),
            updated_at=payload["updated_at"],
        )


_UNSET = object()


def _manifest_entry(manifest: EvidenceManifest, *, logical_name: str) -> EvidenceManifestEntry:
    for entry in manifest.entries:
        if entry.logical_name == logical_name:
            return entry
    raise RuntimeError(
        f"Manifest {manifest.manifest_id} does not contain the expected '{logical_name}' entry."
    )


def _checkpoint_status(
    *,
    lag_seconds: float,
    claimed_count: int,
    limit: int,
    lagging_threshold_seconds: float,
) -> str:
    if lag_seconds > lagging_threshold_seconds:
        return "lagging"
    if claimed_count >= limit:
        return "running"
    return "idle"


def _lag_seconds(now: str, occurred_at: str) -> float:
    return max((_parse_timestamp(now) - _parse_timestamp(occurred_at)).total_seconds(), 0.0)


def _parse_timestamp(value: str) -> datetime:
    candidate = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _close_resource_quietly(resource: object) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            pass


def _connect_postgres(dsn: str):
    import psycopg

    return psycopg.connect(dsn)


__all__ = [
    "MutableTruthProjectedRecord",
    "MutableTruthProjectionReport",
    "MutableTruthProjectorService",
]
