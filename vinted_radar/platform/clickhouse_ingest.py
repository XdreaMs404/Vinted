from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import re
from typing import Any
from urllib.parse import urlsplit

from vinted_radar.domain.events import canonical_json, deterministic_uuid, ensure_json_object
from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry
from vinted_radar.platform.config import PlatformConfig, load_platform_config
from vinted_radar.platform.lake_writer import ParquetLakeWriter
from vinted_radar.platform.outbox import ClaimedOutboxRecord, PostgresOutbox
from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository

CLICKHOUSE_OUTBOX_SINK = "clickhouse"
CLICKHOUSE_INGEST_CONSUMER = "clickhouse-serving-ingest"
CLICKHOUSE_INGEST_PRODUCER = "platform.clickhouse_ingest"

_FACT_LISTING_SEEN_TABLE = "fact_listing_seen_events"
_FACT_LISTING_PROBE_TABLE = "fact_listing_probe_events"

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_LISTING_SEEN_COLUMNS = (
    "event_id",
    "manifest_id",
    "source_event_id",
    "source_event_type",
    "schema_version",
    "occurred_at",
    "observed_at",
    "producer",
    "partition_key",
    "run_id",
    "listing_id",
    "canonical_url",
    "source_url",
    "title",
    "brand",
    "size_label",
    "condition_label",
    "price_amount_cents",
    "price_currency",
    "total_price_amount_cents",
    "total_price_currency",
    "image_url",
    "favourite_count",
    "view_count",
    "user_id",
    "user_login",
    "user_profile_url",
    "created_at_ts",
    "primary_catalog_id",
    "primary_root_catalog_id",
    "source_catalog_id",
    "source_root_catalog_id",
    "source_page_number",
    "card_position",
    "root_title",
    "category_path",
    "raw_card_json",
    "metadata_json",
)

_LISTING_PROBE_COLUMNS = (
    "event_id",
    "manifest_id",
    "source_event_id",
    "source_event_type",
    "schema_version",
    "occurred_at",
    "probed_at",
    "producer",
    "listing_id",
    "requested_url",
    "final_url",
    "response_status",
    "probe_outcome",
    "reason",
    "error_message",
    "primary_catalog_id",
    "primary_root_catalog_id",
    "root_title",
    "category_path",
    "brand",
    "condition_label",
    "price_amount_cents",
    "price_currency",
    "total_price_amount_cents",
    "total_price_currency",
    "favourite_count",
    "view_count",
    "detail_json",
    "metadata_json",
)


@dataclass(frozen=True, slots=True)
class ClickHouseIngestedRecord:
    source_event_id: str
    event_type: str
    manifest_id: str | None
    row_count: int
    inserted_row_count: int
    existing_row_count: int
    target_table: str | None
    projection_status: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source_event_id": self.source_event_id,
            "event_type": self.event_type,
            "manifest_id": self.manifest_id,
            "row_count": self.row_count,
            "inserted_row_count": self.inserted_row_count,
            "existing_row_count": self.existing_row_count,
            "target_table": self.target_table,
            "projection_status": self.projection_status,
        }


@dataclass(frozen=True, slots=True)
class ClickHouseIngestReport:
    consumer_name: str
    sink: str
    claimed_count: int
    processed_count: int
    skipped_count: int
    records: tuple[ClickHouseIngestedRecord, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "consumer_name": self.consumer_name,
            "sink": self.sink,
            "claimed_count": self.claimed_count,
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "records": [record.as_dict() for record in self.records],
        }


@dataclass(frozen=True, slots=True)
class ClickHouseIngestStatusSnapshot:
    consumer_name: str
    sink: str
    checkpoint_exists: bool
    status: str
    updated_at: str | None
    last_outbox_id: int | None
    last_event_id: str | None
    last_manifest_id: str | None
    last_claimed_at: str | None
    last_delivered_at: str | None
    lag_seconds: float | None
    last_error: str | None
    metadata: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "consumer_name": self.consumer_name,
            "sink": self.sink,
            "checkpoint_exists": self.checkpoint_exists,
            "status": self.status,
            "updated_at": self.updated_at,
            "last_outbox_id": self.last_outbox_id,
            "last_event_id": self.last_event_id,
            "last_manifest_id": self.last_manifest_id,
            "last_claimed_at": self.last_claimed_at,
            "last_delivered_at": self.last_delivered_at,
            "lag_seconds": self.lag_seconds,
            "last_error": self.last_error,
            "metadata": dict(self.metadata),
        }


_UNSET = object()


class ClickHouseIngestService:
    def __init__(
        self,
        *,
        repository: PostgresMutableTruthRepository | object,
        outbox: PostgresOutbox,
        lake_writer: ParquetLakeWriter,
        clickhouse_client: object,
        database: str,
        sink: str = CLICKHOUSE_OUTBOX_SINK,
        consumer_name: str = CLICKHOUSE_INGEST_CONSUMER,
        retry_delay_seconds: float = 30.0,
        lagging_threshold_seconds: float = 300.0,
        now_provider: Callable[[], str] | None = None,
        closeables: Sequence[object] = (),
    ) -> None:
        self.repository = repository
        self.outbox = outbox
        self.lake_writer = lake_writer
        self.clickhouse_client = clickhouse_client
        self.database = _safe_identifier(database, field_name="ClickHouse database")
        self.sink = str(sink).strip() or CLICKHOUSE_OUTBOX_SINK
        self.consumer_name = str(consumer_name).strip() or CLICKHOUSE_INGEST_CONSUMER
        self.retry_delay_seconds = max(float(retry_delay_seconds), 1.0)
        self.lagging_threshold_seconds = max(float(lagging_threshold_seconds), 1.0)
        self.now_provider = now_provider or _utc_now
        self._closeables = tuple(closeables)

    @classmethod
    def from_environment(
        cls,
        *,
        config: PlatformConfig | None = None,
        postgres_connection: object | None = None,
        object_store_client: object | None = None,
        clickhouse_client: object | None = None,
        sink: str = CLICKHOUSE_OUTBOX_SINK,
        consumer_name: str = CLICKHOUSE_INGEST_CONSUMER,
        retry_delay_seconds: float = 30.0,
        lagging_threshold_seconds: float = 300.0,
        now_provider: Callable[[], str] | None = None,
    ) -> ClickHouseIngestService:
        resolved_config = load_platform_config() if config is None else config
        created_postgres_connection = postgres_connection is None
        created_object_store_client = object_store_client is None
        created_clickhouse_client = clickhouse_client is None

        connection = _connect_postgres(resolved_config.postgres.dsn) if postgres_connection is None else postgres_connection
        lake_writer = ParquetLakeWriter.from_config(resolved_config, client=object_store_client)
        client = _get_clickhouse_client(resolved_config, database=resolved_config.clickhouse.database) if clickhouse_client is None else clickhouse_client

        closeables: list[object] = []
        if created_postgres_connection:
            closeables.append(connection)
        if created_object_store_client:
            closeables.append(lake_writer.object_store.client)
        if created_clickhouse_client:
            closeables.append(client)

        return cls(
            repository=PostgresMutableTruthRepository(connection),
            outbox=PostgresOutbox(connection),
            lake_writer=lake_writer,
            clickhouse_client=client,
            database=resolved_config.clickhouse.database,
            sink=sink,
            consumer_name=consumer_name,
            retry_delay_seconds=retry_delay_seconds,
            lagging_threshold_seconds=lagging_threshold_seconds,
            now_provider=now_provider,
            closeables=closeables,
        )

    def close(self) -> None:
        repository_close = getattr(self.repository, "close", None)
        if callable(repository_close):
            repository_close()
        for resource in self._closeables:
            _close_resource_quietly(resource)

    def ingest_available(
        self,
        *,
        limit: int = 100,
        lease_seconds: int = 60,
        now: str | None = None,
        consumer_name: str | None = None,
    ) -> ClickHouseIngestReport:
        resolved_consumer = self.consumer_name if consumer_name is None else str(consumer_name)
        claimed_at = now or self.now_provider()
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
            return ClickHouseIngestReport(
                consumer_name=resolved_consumer,
                sink=self.sink,
                claimed_count=0,
                processed_count=0,
                skipped_count=0,
                records=(),
            )

        processed: list[ClickHouseIngestedRecord] = []
        skipped_count = 0
        for record in claimed:
            try:
                result = self._ingest_record(record)
                delivered_at = self.now_provider()
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
                        "inserted_row_count": result.inserted_row_count,
                        "existing_row_count": result.existing_row_count,
                        "target_table": result.target_table,
                        "projection_status": result.projection_status,
                    },
                    updated_at=delivered_at,
                )
            except Exception as exc:  # noqa: BLE001
                failed_at = self.now_provider()
                retry_at = _isoformat_utc(_parse_timestamp(failed_at) + timedelta(seconds=self.retry_delay_seconds))
                self.outbox.mark_failed(
                    event_id=record.event.event_id,
                    sink=self.sink,
                    error=f"{type(exc).__name__}: {exc}",
                    failed_at=failed_at,
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
                    lag_seconds=_lag_seconds(failed_at, record.event.occurred_at),
                    last_error=f"{type(exc).__name__}: {exc}",
                    metadata={"event_type": record.event.event_type, "retry_at": retry_at},
                    updated_at=failed_at,
                )
                raise

        return ClickHouseIngestReport(
            consumer_name=resolved_consumer,
            sink=self.sink,
            claimed_count=len(claimed),
            processed_count=len(processed),
            skipped_count=skipped_count,
            records=tuple(processed),
        )

    def current_status(self, *, consumer_name: str | None = None) -> ClickHouseIngestStatusSnapshot:
        resolved_consumer = self.consumer_name if consumer_name is None else str(consumer_name)
        return _status_snapshot_from_checkpoint(
            consumer_name=resolved_consumer,
            sink=self.sink,
            checkpoint=self._current_checkpoint(consumer_name=resolved_consumer),
        )

    def _ingest_record(self, record: ClaimedOutboxRecord) -> ClickHouseIngestedRecord:
        if record.event.event_type not in {
            "vinted.discovery.listing-seen.batch",
            "vinted.state-refresh.probe.batch",
        }:
            row_count = int(record.event.payload.get("row_count") or 0)
            return ClickHouseIngestedRecord(
                source_event_id=record.event.event_id,
                event_type=record.event.event_type,
                manifest_id=record.manifest_id,
                row_count=row_count,
                inserted_row_count=0,
                existing_row_count=0,
                target_table=None,
                projection_status="skipped",
            )

        manifest = self._fetch_manifest(record)
        rows = self._load_rows(manifest)
        if record.event.event_type == "vinted.discovery.listing-seen.batch":
            target_table = _FACT_LISTING_SEEN_TABLE
            mapped_rows = self._map_listing_seen_rows(record=record, manifest=manifest, rows=rows)
            column_names = _LISTING_SEEN_COLUMNS
        else:
            target_table = _FACT_LISTING_PROBE_TABLE
            mapped_rows = self._map_listing_probe_rows(record=record, manifest=manifest, rows=rows)
            column_names = _LISTING_PROBE_COLUMNS

        expected_event_ids = {str(row["event_id"]) for row in mapped_rows}
        existing_event_ids = self._existing_row_event_ids(table=target_table, source_event_id=record.event.event_id)
        existing_known_ids = existing_event_ids & expected_event_ids
        missing_rows = [row for row in mapped_rows if str(row["event_id"]) not in existing_known_ids]
        if missing_rows:
            self._insert_rows(table=target_table, column_names=column_names, rows=missing_rows)

        projection_status = "skipped" if not missing_rows else "projected"
        return ClickHouseIngestedRecord(
            source_event_id=record.event.event_id,
            event_type=record.event.event_type,
            manifest_id=manifest.manifest_id,
            row_count=len(mapped_rows),
            inserted_row_count=len(missing_rows),
            existing_row_count=len(existing_known_ids),
            target_table=target_table,
            projection_status=projection_status,
        )

    def _map_listing_seen_rows(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, object]]:
        mapped: list[dict[str, object]] = []
        for index, row in enumerate(rows):
            row_index = int(row.get("row_index") if row.get("row_index") is not None else index)
            listing_id = _required_int(row.get("listing_id"), field_name="listing_id")
            observed_at = _required_str(row.get("observed_at"), field_name="observed_at")
            metadata_json = canonical_json(
                {
                    key: value
                    for key, value in {
                        "source_producer": _optional_str(row.get("batch_event_producer")) or record.event.producer,
                        "source_partition_key": _optional_str(row.get("batch_event_partition_key")) or record.event.partition_key,
                        "batch_event_occurred_on": _optional_str(row.get("batch_event_occurred_on")),
                        "capture_source": _optional_str(record.event.metadata.get("capture_source")),
                        "catalog_title": _optional_str(row.get("catalog_title")),
                        "row_index": row_index,
                    }.items()
                    if value is not None
                }
            )
            mapped.append(
                {
                    "event_id": deterministic_uuid(
                        "clickhouse.fact-listing-seen",
                        {
                            "source_event_id": record.event.event_id,
                            "manifest_id": manifest.manifest_id,
                            "row_index": row_index,
                            "listing_id": listing_id,
                            "observed_at": observed_at,
                        },
                    ),
                    "manifest_id": manifest.manifest_id,
                    "source_event_id": record.event.event_id,
                    "source_event_type": record.event.event_type,
                    "schema_version": int(row.get("batch_event_schema_version") or record.event.schema_version),
                    "occurred_at": _required_str(
                        row.get("batch_event_occurred_at") or record.event.occurred_at,
                        field_name="batch_event_occurred_at",
                    ),
                    "observed_at": observed_at,
                    "producer": CLICKHOUSE_INGEST_PRODUCER,
                    "partition_key": _optional_str(row.get("batch_event_partition_key")) or record.event.partition_key,
                    "run_id": _optional_str(row.get("run_id")) or _optional_str(record.event.payload.get("run_id")),
                    "listing_id": listing_id,
                    "canonical_url": _required_str(row.get("canonical_url"), field_name="canonical_url"),
                    "source_url": _required_str(row.get("source_url"), field_name="source_url"),
                    "title": _optional_str(row.get("title")),
                    "brand": _optional_str(row.get("brand")),
                    "size_label": _optional_str(row.get("size_label")),
                    "condition_label": _optional_str(row.get("condition_label")),
                    "price_amount_cents": _optional_int(row.get("price_amount_cents")),
                    "price_currency": _optional_str(row.get("price_currency")),
                    "total_price_amount_cents": _optional_int(row.get("total_price_amount_cents")),
                    "total_price_currency": _optional_str(row.get("total_price_currency")),
                    "image_url": _optional_str(row.get("image_url")),
                    "favourite_count": _optional_int(row.get("favourite_count")),
                    "view_count": _optional_int(row.get("view_count")),
                    "user_id": _optional_int(row.get("user_id")),
                    "user_login": _optional_str(row.get("user_login")),
                    "user_profile_url": _optional_str(row.get("user_profile_url")),
                    "created_at_ts": _optional_int(row.get("created_at_ts")),
                    "primary_catalog_id": _optional_int(row.get("catalog_id")),
                    "primary_root_catalog_id": _optional_int(row.get("root_catalog_id")),
                    "source_catalog_id": _optional_int(row.get("catalog_id")),
                    "source_root_catalog_id": _optional_int(row.get("root_catalog_id")),
                    "source_page_number": _optional_int(row.get("page_number")),
                    "card_position": _optional_int(row.get("card_position")),
                    "root_title": _optional_str(row.get("root_title")),
                    "category_path": _optional_str(row.get("catalog_path")),
                    "raw_card_json": _canonical_json_string(row.get("raw_card"), field_name="raw_card"),
                    "metadata_json": metadata_json,
                }
            )
        return mapped

    def _map_listing_probe_rows(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, object]]:
        mapped: list[dict[str, object]] = []
        for index, row in enumerate(rows):
            row_index = int(row.get("row_index") if row.get("row_index") is not None else index)
            listing_id = _required_int(row.get("listing_id"), field_name="listing_id")
            probed_at = _required_str(row.get("probed_at"), field_name="probed_at")
            metadata_json = canonical_json(
                {
                    key: value
                    for key, value in {
                        "source_producer": _optional_str(row.get("batch_event_producer")) or record.event.producer,
                        "capture_source": _optional_str(record.event.metadata.get("capture_source")),
                        "mode": _optional_str(record.event.metadata.get("mode")),
                        "reference_now": _optional_str(row.get("reference_now")),
                        "targeted_listing_id": _optional_int(row.get("targeted_listing_id")),
                        "row_index": row_index,
                    }.items()
                    if value is not None
                }
            )
            mapped.append(
                {
                    "event_id": deterministic_uuid(
                        "clickhouse.fact-listing-probe",
                        {
                            "source_event_id": record.event.event_id,
                            "manifest_id": manifest.manifest_id,
                            "row_index": row_index,
                            "listing_id": listing_id,
                            "probed_at": probed_at,
                        },
                    ),
                    "manifest_id": manifest.manifest_id,
                    "source_event_id": record.event.event_id,
                    "source_event_type": record.event.event_type,
                    "schema_version": int(row.get("batch_event_schema_version") or record.event.schema_version),
                    "occurred_at": _required_str(
                        row.get("batch_event_occurred_at") or record.event.occurred_at,
                        field_name="batch_event_occurred_at",
                    ),
                    "probed_at": probed_at,
                    "producer": CLICKHOUSE_INGEST_PRODUCER,
                    "listing_id": listing_id,
                    "requested_url": _required_str(row.get("requested_url"), field_name="requested_url"),
                    "final_url": _optional_str(row.get("final_url")),
                    "response_status": _optional_int(row.get("response_status")),
                    "probe_outcome": _optional_str(row.get("probe_outcome")) or "unknown",
                    "reason": _optional_str(row.get("reason")),
                    "error_message": _optional_str(row.get("error_message")),
                    "primary_catalog_id": _optional_int(row.get("primary_catalog_id")),
                    "primary_root_catalog_id": _optional_int(row.get("primary_root_catalog_id")),
                    "root_title": _optional_str(row.get("root_title")),
                    "category_path": _optional_str(row.get("category_path")),
                    "brand": _optional_str(row.get("brand")),
                    "condition_label": _optional_str(row.get("condition_label")),
                    "price_amount_cents": _optional_int(row.get("price_amount_cents")),
                    "price_currency": _optional_str(row.get("price_currency")),
                    "total_price_amount_cents": _optional_int(row.get("total_price_amount_cents")),
                    "total_price_currency": _optional_str(row.get("total_price_currency")),
                    "favourite_count": _optional_int(row.get("favourite_count")),
                    "view_count": _optional_int(row.get("view_count")),
                    "detail_json": _canonical_json_string(row.get("detail"), field_name="detail"),
                    "metadata_json": metadata_json,
                }
            )
        return mapped

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

    def _existing_row_event_ids(self, *, table: str, source_event_id: str) -> set[str]:
        qualified_table = self._qualified_table(table)
        result = self.clickhouse_client.query(
            f"SELECT event_id FROM {qualified_table} WHERE source_event_id = {_sql_string(source_event_id)}"
        )
        rows = getattr(result, "result_rows", ()) or ()
        return {str(row[0]) for row in rows}

    def _insert_rows(self, *, table: str, column_names: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
        if not rows:
            return
        payload = [tuple(row.get(column) for column in column_names) for row in rows]
        self.clickhouse_client.insert(
            table=table,
            data=payload,
            column_names=list(column_names),
            database=self.database,
        )

    def _qualified_table(self, table: str) -> str:
        return f"{self.database}.{_safe_identifier(table, field_name='ClickHouse table')}"

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
            "updated_at": updated_at or self.now_provider(),
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


def load_clickhouse_ingest_status(
    *,
    config: PlatformConfig | None = None,
    postgres_connection: object | None = None,
    sink: str = CLICKHOUSE_OUTBOX_SINK,
    consumer_name: str = CLICKHOUSE_INGEST_CONSUMER,
) -> ClickHouseIngestStatusSnapshot:
    resolved_config = load_platform_config() if config is None else config
    created_postgres_connection = postgres_connection is None
    connection = _connect_postgres(resolved_config.postgres.dsn) if postgres_connection is None else postgres_connection
    repository = PostgresMutableTruthRepository(connection)
    try:
        checkpoint = repository.outbox_checkpoint(consumer_name=consumer_name, sink=sink)
    finally:
        if created_postgres_connection:
            repository.close()
    return _status_snapshot_from_checkpoint(consumer_name=consumer_name, sink=sink, checkpoint=checkpoint)


def _status_snapshot_from_checkpoint(
    *,
    consumer_name: str,
    sink: str,
    checkpoint: Mapping[str, object] | None,
) -> ClickHouseIngestStatusSnapshot:
    if checkpoint is None:
        return ClickHouseIngestStatusSnapshot(
            consumer_name=consumer_name,
            sink=sink,
            checkpoint_exists=False,
            status="never-run",
            updated_at=None,
            last_outbox_id=None,
            last_event_id=None,
            last_manifest_id=None,
            last_claimed_at=None,
            last_delivered_at=None,
            lag_seconds=None,
            last_error=None,
            metadata={},
        )
    return ClickHouseIngestStatusSnapshot(
        consumer_name=consumer_name,
        sink=sink,
        checkpoint_exists=True,
        status=str(checkpoint.get("status") or "idle"),
        updated_at=_optional_str(checkpoint.get("updated_at")),
        last_outbox_id=_optional_int(checkpoint.get("last_outbox_id")),
        last_event_id=_optional_str(checkpoint.get("last_event_id")),
        last_manifest_id=_optional_str(checkpoint.get("last_manifest_id")),
        last_claimed_at=_optional_str(checkpoint.get("last_claimed_at")),
        last_delivered_at=_optional_str(checkpoint.get("last_delivered_at")),
        lag_seconds=None if checkpoint.get("lag_seconds") is None else float(checkpoint.get("lag_seconds") or 0.0),
        last_error=_optional_str(checkpoint.get("last_error")),
        metadata=dict(checkpoint.get("metadata") or {}),
    )


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


def _canonical_json_string(value: object, *, field_name: str) -> str:
    if value is None or value == "":
        return canonical_json({})
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, Mapping):
            return canonical_json(ensure_json_object(decoded, field_name=field_name))
        if isinstance(decoded, list):
            return canonical_json(decoded)
        return canonical_json(decoded)
    if isinstance(value, Mapping):
        return canonical_json(ensure_json_object(value, field_name=field_name))
    if isinstance(value, (list, tuple)):
        return canonical_json(list(value))
    raise ValueError(f"{field_name} must be JSON-serializable")


def _required_str(value: object, *, field_name: str) -> str:
    candidate = _optional_str(value)
    if candidate is None:
        raise RuntimeError(f"{field_name} is required for ClickHouse ingest.")
    return candidate


def _required_int(value: object, *, field_name: str) -> int:
    candidate = _optional_int(value)
    if candidate is None:
        raise RuntimeError(f"{field_name} is required for ClickHouse ingest.")
    return candidate


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value)
    return candidate if candidate != "" else None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


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


def _connect_postgres(dsn: str):
    import psycopg

    return psycopg.connect(dsn)


def _get_clickhouse_client(config: PlatformConfig, *, database: str):
    import clickhouse_connect

    parts = urlsplit(config.clickhouse.url)
    return clickhouse_connect.get_client(
        host=parts.hostname or "127.0.0.1",
        port=parts.port or (8443 if parts.scheme == "https" else 8123),
        username=config.clickhouse.username,
        password=config.clickhouse.password,
        database=database,
        secure=parts.scheme == "https",
    )


def _close_resource_quietly(resource: object) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            pass


def _safe_identifier(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not _SAFE_IDENTIFIER_RE.fullmatch(candidate):
        raise ValueError(f"{field_name} must contain only letters, digits, and underscores")
    return candidate


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


__all__ = [
    "CLICKHOUSE_INGEST_CONSUMER",
    "CLICKHOUSE_INGEST_PRODUCER",
    "CLICKHOUSE_OUTBOX_SINK",
    "ClickHouseIngestReport",
    "ClickHouseIngestService",
    "ClickHouseIngestStatusSnapshot",
    "ClickHouseIngestedRecord",
    "load_clickhouse_ingest_status",
]
