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
from vinted_radar.state_machine import evaluate_listing_state

CLICKHOUSE_OUTBOX_SINK = "clickhouse"
CLICKHOUSE_INGEST_CONSUMER = "clickhouse-serving-ingest"
CLICKHOUSE_INGEST_PRODUCER = "platform.clickhouse_ingest"

_FACT_LISTING_SEEN_TABLE = "fact_listing_seen_events"
_FACT_LISTING_PROBE_TABLE = "fact_listing_probe_events"
_FACT_LISTING_CHANGE_TABLE = "fact_listing_change_events"

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

_LISTING_CHANGE_COLUMNS = (
    "event_id",
    "manifest_id",
    "source_event_id",
    "source_event_type",
    "schema_version",
    "occurred_at",
    "producer",
    "listing_id",
    "change_kind",
    "previous_state_code",
    "current_state_code",
    "previous_basis_kind",
    "current_basis_kind",
    "previous_confidence_label",
    "current_confidence_label",
    "previous_confidence_score",
    "current_confidence_score",
    "previous_price_amount_cents",
    "current_price_amount_cents",
    "previous_total_price_amount_cents",
    "current_total_price_amount_cents",
    "previous_favourite_count",
    "current_favourite_count",
    "previous_view_count",
    "current_view_count",
    "follow_up_miss_count",
    "probe_outcome",
    "response_status",
    "primary_catalog_id",
    "primary_root_catalog_id",
    "root_title",
    "category_path",
    "brand",
    "condition_label",
    "change_summary",
    "change_json",
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
    change_row_count: int = 0
    change_inserted_row_count: int = 0
    change_existing_row_count: int = 0
    change_target_table: str | None = None
    projection_status: str = "skipped"

    def as_dict(self) -> dict[str, object]:
        return {
            "source_event_id": self.source_event_id,
            "event_type": self.event_type,
            "manifest_id": self.manifest_id,
            "row_count": self.row_count,
            "inserted_row_count": self.inserted_row_count,
            "existing_row_count": self.existing_row_count,
            "target_table": self.target_table,
            "change_row_count": self.change_row_count,
            "change_inserted_row_count": self.change_inserted_row_count,
            "change_existing_row_count": self.change_existing_row_count,
            "change_target_table": self.change_target_table,
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


@dataclass(frozen=True, slots=True)
class _DerivedListingSnapshot:
    listing_id: int
    occurred_at: str
    state_code: str | None
    basis_kind: str | None
    confidence_label: str | None
    confidence_score: float | None
    price_amount_cents: int | None
    total_price_amount_cents: int | None
    favourite_count: int | None
    view_count: int | None
    follow_up_miss_count: int
    probe_outcome: str | None
    response_status: int | None
    primary_catalog_id: int | None
    primary_root_catalog_id: int | None
    root_title: str | None
    category_path: str | None
    brand: str | None
    condition_label: str | None
    last_seen_at: str | None
    latest_primary_scan_run_id: str | None
    seen_in_latest_primary_scan: bool
    latest_probe: dict[str, object] | None
    state_explanation: dict[str, object]


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
                        "change_row_count": result.change_row_count,
                        "change_inserted_row_count": result.change_inserted_row_count,
                        "change_existing_row_count": result.change_existing_row_count,
                        "change_target_table": result.change_target_table,
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

        change_rows = self._derive_change_rows(record=record, manifest=manifest, mapped_rows=mapped_rows)

        expected_event_ids = {str(row["event_id"]) for row in mapped_rows}
        existing_event_ids = self._existing_row_event_ids(table=target_table, source_event_id=record.event.event_id)
        existing_known_ids = existing_event_ids & expected_event_ids
        missing_rows = [row for row in mapped_rows if str(row["event_id"]) not in existing_known_ids]
        if missing_rows:
            self._insert_rows(table=target_table, column_names=column_names, rows=missing_rows)

        expected_change_event_ids = {str(row["event_id"]) for row in change_rows}
        existing_change_event_ids = self._existing_row_event_ids(
            table=_FACT_LISTING_CHANGE_TABLE,
            source_event_id=record.event.event_id,
        )
        existing_known_change_ids = existing_change_event_ids & expected_change_event_ids
        missing_change_rows = [row for row in change_rows if str(row["event_id"]) not in existing_known_change_ids]
        if missing_change_rows:
            self._insert_rows(
                table=_FACT_LISTING_CHANGE_TABLE,
                column_names=_LISTING_CHANGE_COLUMNS,
                rows=missing_change_rows,
            )

        projection_status = "skipped" if not missing_rows and not missing_change_rows else "projected"
        return ClickHouseIngestedRecord(
            source_event_id=record.event.event_id,
            event_type=record.event.event_type,
            manifest_id=manifest.manifest_id,
            row_count=len(mapped_rows),
            inserted_row_count=len(missing_rows),
            existing_row_count=len(existing_known_ids),
            target_table=target_table,
            change_row_count=len(change_rows),
            change_inserted_row_count=len(missing_change_rows),
            change_existing_row_count=len(existing_known_change_ids),
            change_target_table=None if not change_rows else _FACT_LISTING_CHANGE_TABLE,
            projection_status=projection_status,
        )

    def _derive_change_rows(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        mapped_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if not mapped_rows:
            return []
        if record.event.event_type == "vinted.discovery.listing-seen.batch":
            return self._derive_listing_seen_change_rows(record=record, manifest=manifest, mapped_rows=mapped_rows)
        if record.event.event_type == "vinted.state-refresh.probe.batch":
            return self._derive_probe_change_rows(record=record, manifest=manifest, mapped_rows=mapped_rows)
        return []

    def _derive_listing_seen_change_rows(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        mapped_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        occurred_at = record.event.occurred_at
        listing_ids = sorted({int(row["listing_id"]) for row in mapped_rows})
        previous_snapshots = self._previous_snapshots(listing_ids=listing_ids, as_of=occurred_at)
        rows_by_listing = {
            int(row["listing_id"]): dict(row)
            for row in sorted(mapped_rows, key=lambda item: (str(item["observed_at"]), str(item["event_id"])))
        }
        change_rows: list[dict[str, object]] = []
        for listing_id, row in rows_by_listing.items():
            previous = previous_snapshots.get(listing_id)
            current = self._build_seen_snapshot(row=row, previous=previous, run_id=_optional_str(row.get("run_id")))
            change_rows.extend(
                self._build_change_rows(
                    record=record,
                    manifest=manifest,
                    previous=previous,
                    current=current,
                    metadata={
                        "capture_source": _optional_str(record.event.metadata.get("capture_source")),
                        "run_id": _optional_str(row.get("run_id")),
                        "catalog_id": _optional_int(row.get("primary_catalog_id")),
                        "page_number": _optional_int(row.get("source_page_number")),
                        "card_position": _optional_int(row.get("card_position")),
                        "catalog_scan_terminal": self._is_terminal_catalog_batch(record=record, manifest=manifest),
                    },
                )
            )

        if self._is_terminal_catalog_batch(record=record, manifest=manifest):
            catalog_id = _optional_int(record.event.payload.get("catalog_id")) or _optional_int(manifest.metadata.get("catalog_id"))
            run_id = _optional_str(record.event.payload.get("run_id"))
            if catalog_id is not None and run_id is not None:
                seen_in_run = self._listing_ids_seen_in_catalog_run(catalog_id=catalog_id, run_id=run_id)
                seen_in_run.update(listing_ids)
                previous_catalog_rows = self._latest_catalog_seen_rows_before(catalog_id=catalog_id, before=occurred_at)
                missing_listing_ids = sorted(set(previous_catalog_rows) - seen_in_run)
                missing_previous = self._previous_snapshots(
                    listing_ids=missing_listing_ids,
                    as_of=occurred_at,
                    latest_seen_rows=previous_catalog_rows,
                )
                for listing_id in missing_listing_ids:
                    previous = missing_previous.get(listing_id)
                    latest_seen_row = previous_catalog_rows.get(listing_id)
                    if previous is None or latest_seen_row is None:
                        continue
                    current = self._build_follow_up_miss_snapshot(
                        previous=previous,
                        latest_seen_row=latest_seen_row,
                        occurred_at=occurred_at,
                        run_id=run_id,
                    )
                    change_rows.extend(
                        self._build_change_rows(
                            record=record,
                            manifest=manifest,
                            previous=previous,
                            current=current,
                            metadata={
                                "capture_source": _optional_str(record.event.metadata.get("capture_source")),
                                "run_id": run_id,
                                "catalog_id": catalog_id,
                                "catalog_scan_terminal": True,
                                "missing_from_scan": True,
                            },
                        )
                    )
        return change_rows

    def _derive_probe_change_rows(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        mapped_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        occurred_at = record.event.occurred_at
        listing_ids = sorted({int(row["listing_id"]) for row in mapped_rows})
        previous_snapshots = self._previous_snapshots(listing_ids=listing_ids, as_of=occurred_at)
        change_rows: list[dict[str, object]] = []
        rows_by_listing = {
            int(row["listing_id"]): dict(row)
            for row in sorted(mapped_rows, key=lambda item: (str(item["probed_at"]), str(item["event_id"])))
        }
        for listing_id, row in rows_by_listing.items():
            previous = previous_snapshots.get(listing_id)
            current = self._build_probe_snapshot(row=row, previous=previous)
            change_rows.extend(
                self._build_change_rows(
                    record=record,
                    manifest=manifest,
                    previous=previous,
                    current=current,
                    metadata={
                        "capture_source": _optional_str(record.event.metadata.get("capture_source")),
                        "mode": _optional_str(record.event.metadata.get("mode")),
                        "targeted_listing_id": _optional_int(record.event.payload.get("targeted_listing_id")),
                        "requested_limit": _optional_int(manifest.metadata.get("requested_limit")),
                    },
                )
            )
        return change_rows

    def _previous_snapshots(
        self,
        *,
        listing_ids: Sequence[int],
        as_of: str,
        latest_seen_rows: Mapping[int, Mapping[str, object]] | None = None,
    ) -> dict[int, _DerivedListingSnapshot]:
        normalized_listing_ids = sorted({int(listing_id) for listing_id in listing_ids})
        if not normalized_listing_ids:
            return {}
        seen_rows = (
            {int(key): dict(value) for key, value in latest_seen_rows.items()}
            if latest_seen_rows is not None
            else self._latest_seen_rows_before(listing_ids=normalized_listing_ids, before=as_of)
        )
        probe_rows = self._latest_probe_rows_before(listing_ids=normalized_listing_ids, before=as_of)
        change_rows = self._latest_change_rows_before(listing_ids=normalized_listing_ids, before=as_of)
        snapshots: dict[int, _DerivedListingSnapshot] = {}
        for listing_id in normalized_listing_ids:
            snapshot = self._build_previous_snapshot(
                listing_id=listing_id,
                latest_seen_row=seen_rows.get(listing_id),
                latest_probe_row=probe_rows.get(listing_id),
                latest_change_row=change_rows.get(listing_id),
            )
            if snapshot is not None:
                snapshots[listing_id] = snapshot
        return snapshots

    def _build_previous_snapshot(
        self,
        *,
        listing_id: int,
        latest_seen_row: Mapping[str, object] | None,
        latest_probe_row: Mapping[str, object] | None,
        latest_change_row: Mapping[str, object] | None,
    ) -> _DerivedListingSnapshot | None:
        if latest_seen_row is None and latest_probe_row is None and latest_change_row is None:
            return None
        latest_probe = self._probe_payload_from_row(latest_probe_row)
        if latest_change_row is not None and latest_change_row.get("current_state_code") is not None:
            return _DerivedListingSnapshot(
                listing_id=listing_id,
                occurred_at=_required_str(latest_change_row.get("occurred_at"), field_name="occurred_at"),
                state_code=_optional_str(latest_change_row.get("current_state_code")),
                basis_kind=_optional_str(latest_change_row.get("current_basis_kind")),
                confidence_label=_optional_str(latest_change_row.get("current_confidence_label")),
                confidence_score=None if latest_change_row.get("current_confidence_score") is None else float(latest_change_row.get("current_confidence_score") or 0.0),
                price_amount_cents=_coalesce_int(latest_change_row.get("current_price_amount_cents"), latest_seen_row, "price_amount_cents"),
                total_price_amount_cents=_coalesce_int(latest_change_row.get("current_total_price_amount_cents"), latest_seen_row, "total_price_amount_cents"),
                favourite_count=_coalesce_int(latest_change_row.get("current_favourite_count"), latest_seen_row, "favourite_count"),
                view_count=_coalesce_int(latest_change_row.get("current_view_count"), latest_seen_row, "view_count"),
                follow_up_miss_count=int(latest_change_row.get("follow_up_miss_count") or 0),
                probe_outcome=_optional_str(_coalesce(latest_change_row.get("probe_outcome"), (latest_probe or {}).get("probe_outcome"))),
                response_status=_optional_int(_coalesce(latest_change_row.get("response_status"), (latest_probe or {}).get("response_status"))),
                primary_catalog_id=_coalesce_int(latest_change_row.get("primary_catalog_id"), latest_seen_row, "primary_catalog_id"),
                primary_root_catalog_id=_coalesce_int(latest_change_row.get("primary_root_catalog_id"), latest_seen_row, "primary_root_catalog_id"),
                root_title=_coalesce_str(latest_change_row.get("root_title"), None if latest_seen_row is None else latest_seen_row.get("root_title"), None),
                category_path=_coalesce_str(latest_change_row.get("category_path"), None if latest_seen_row is None else latest_seen_row.get("category_path"), None),
                brand=_coalesce_str(latest_change_row.get("brand"), None if latest_seen_row is None else latest_seen_row.get("brand"), None),
                condition_label=_coalesce_str(latest_change_row.get("condition_label"), None if latest_seen_row is None else latest_seen_row.get("condition_label"), None),
                last_seen_at=None if latest_seen_row is None else _optional_str(latest_seen_row.get("observed_at")),
                latest_primary_scan_run_id=None if latest_seen_row is None else _optional_str(latest_seen_row.get("run_id")),
                seen_in_latest_primary_scan=int(latest_change_row.get("follow_up_miss_count") or 0) == 0 and latest_seen_row is not None,
                latest_probe=latest_probe,
                state_explanation={},
            )

        reference_now = _coalesce_str(
            None if latest_probe_row is None else latest_probe_row.get("probed_at"),
            None if latest_seen_row is None else latest_seen_row.get("observed_at"),
            _utc_now(),
        )
        evidence = self._snapshot_evidence(
            listing_id=listing_id,
            occurred_at=reference_now,
            previous=None,
            latest_seen_row=latest_seen_row,
            latest_probe=latest_probe,
            follow_up_miss_count=0,
            latest_primary_scan_run_id=None if latest_seen_row is None else _optional_str(latest_seen_row.get("run_id")),
            seen_in_latest_primary_scan=latest_seen_row is not None,
            latest_price_amount_cents=None if latest_seen_row is None else _optional_int(latest_seen_row.get("price_amount_cents")),
            latest_total_price_amount_cents=None if latest_seen_row is None else _optional_int(latest_seen_row.get("total_price_amount_cents")),
            latest_favourite_count=None if latest_seen_row is None else _optional_int(latest_seen_row.get("favourite_count")),
            latest_view_count=None if latest_seen_row is None else _optional_int(latest_seen_row.get("view_count")),
            primary_catalog_id=None if latest_seen_row is None else _optional_int(latest_seen_row.get("primary_catalog_id")),
            primary_root_catalog_id=None if latest_seen_row is None else _optional_int(latest_seen_row.get("primary_root_catalog_id")),
            root_title=None if latest_seen_row is None else _optional_str(latest_seen_row.get("root_title")),
            category_path=None if latest_seen_row is None else _optional_str(latest_seen_row.get("category_path")),
            brand=None if latest_seen_row is None else _optional_str(latest_seen_row.get("brand")),
            condition_label=None if latest_seen_row is None else _optional_str(latest_seen_row.get("condition_label")),
        )
        evaluation = evaluate_listing_state(evidence, now=reference_now)
        return self._snapshot_from_evaluation(
            listing_id=listing_id,
            occurred_at=reference_now,
            evaluation=evaluation,
            price_amount_cents=evidence.get("price_amount_cents"),
            total_price_amount_cents=evidence.get("total_price_amount_cents"),
            favourite_count=evidence.get("favourite_count"),
            view_count=evidence.get("view_count"),
            follow_up_miss_count=int(evidence.get("follow_up_miss_count") or 0),
            probe_outcome=(latest_probe or {}).get("probe_outcome"),
            response_status=(latest_probe or {}).get("response_status"),
            primary_catalog_id=evidence.get("primary_catalog_id"),
            primary_root_catalog_id=evidence.get("primary_root_catalog_id"),
            root_title=evidence.get("root_title"),
            category_path=evidence.get("category_path"),
            brand=evidence.get("brand"),
            condition_label=evidence.get("condition_label"),
            last_seen_at=evidence.get("last_seen_at"),
            latest_primary_scan_run_id=evidence.get("latest_primary_scan_run_id"),
            seen_in_latest_primary_scan=bool(evidence.get("seen_in_latest_primary_scan")),
            latest_probe=latest_probe,
        )

    def _build_seen_snapshot(
        self,
        *,
        row: Mapping[str, object],
        previous: _DerivedListingSnapshot | None,
        run_id: str | None,
    ) -> _DerivedListingSnapshot:
        occurred_at = _required_str(row.get("observed_at"), field_name="observed_at")
        evidence = self._snapshot_evidence(
            listing_id=_required_int(row.get("listing_id"), field_name="listing_id"),
            occurred_at=occurred_at,
            previous=previous,
            latest_seen_row=row,
            latest_probe=None if previous is None else previous.latest_probe,
            follow_up_miss_count=0,
            latest_primary_scan_run_id=run_id,
            seen_in_latest_primary_scan=True,
            latest_price_amount_cents=_optional_int(row.get("price_amount_cents")),
            latest_total_price_amount_cents=_optional_int(row.get("total_price_amount_cents")),
            latest_favourite_count=_optional_int(row.get("favourite_count")),
            latest_view_count=_optional_int(row.get("view_count")),
            primary_catalog_id=_optional_int(row.get("primary_catalog_id")),
            primary_root_catalog_id=_optional_int(row.get("primary_root_catalog_id")),
            root_title=_optional_str(row.get("root_title")),
            category_path=_optional_str(row.get("category_path")),
            brand=_optional_str(row.get("brand")),
            condition_label=_optional_str(row.get("condition_label")),
        )
        evaluation = evaluate_listing_state(evidence, now=occurred_at)
        return self._snapshot_from_evaluation(
            listing_id=int(row["listing_id"]),
            occurred_at=occurred_at,
            evaluation=evaluation,
            price_amount_cents=evidence.get("price_amount_cents"),
            total_price_amount_cents=evidence.get("total_price_amount_cents"),
            favourite_count=evidence.get("favourite_count"),
            view_count=evidence.get("view_count"),
            follow_up_miss_count=0,
            probe_outcome=(evidence.get("latest_probe") or {}).get("probe_outcome") if isinstance(evidence.get("latest_probe"), Mapping) else None,
            response_status=(evidence.get("latest_probe") or {}).get("response_status") if isinstance(evidence.get("latest_probe"), Mapping) else None,
            primary_catalog_id=evidence.get("primary_catalog_id"),
            primary_root_catalog_id=evidence.get("primary_root_catalog_id"),
            root_title=evidence.get("root_title"),
            category_path=evidence.get("category_path"),
            brand=evidence.get("brand"),
            condition_label=evidence.get("condition_label"),
            last_seen_at=evidence.get("last_seen_at"),
            latest_primary_scan_run_id=run_id,
            seen_in_latest_primary_scan=True,
            latest_probe=evidence.get("latest_probe") if isinstance(evidence.get("latest_probe"), Mapping) else None,
        )

    def _build_follow_up_miss_snapshot(
        self,
        *,
        previous: _DerivedListingSnapshot,
        latest_seen_row: Mapping[str, object],
        occurred_at: str,
        run_id: str,
    ) -> _DerivedListingSnapshot:
        next_follow_up_miss_count = max(int(previous.follow_up_miss_count or 0) + 1, 1)
        evidence = self._snapshot_evidence(
            listing_id=previous.listing_id,
            occurred_at=occurred_at,
            previous=previous,
            latest_seen_row=latest_seen_row,
            latest_probe=previous.latest_probe,
            follow_up_miss_count=next_follow_up_miss_count,
            latest_primary_scan_run_id=run_id,
            seen_in_latest_primary_scan=False,
            latest_price_amount_cents=previous.price_amount_cents,
            latest_total_price_amount_cents=previous.total_price_amount_cents,
            latest_favourite_count=previous.favourite_count,
            latest_view_count=previous.view_count,
            primary_catalog_id=previous.primary_catalog_id,
            primary_root_catalog_id=previous.primary_root_catalog_id,
            root_title=previous.root_title,
            category_path=previous.category_path,
            brand=previous.brand,
            condition_label=previous.condition_label,
        )
        evaluation = evaluate_listing_state(evidence, now=occurred_at)
        return self._snapshot_from_evaluation(
            listing_id=previous.listing_id,
            occurred_at=occurred_at,
            evaluation=evaluation,
            price_amount_cents=previous.price_amount_cents,
            total_price_amount_cents=previous.total_price_amount_cents,
            favourite_count=previous.favourite_count,
            view_count=previous.view_count,
            follow_up_miss_count=next_follow_up_miss_count,
            probe_outcome=previous.probe_outcome,
            response_status=previous.response_status,
            primary_catalog_id=previous.primary_catalog_id,
            primary_root_catalog_id=previous.primary_root_catalog_id,
            root_title=previous.root_title,
            category_path=previous.category_path,
            brand=previous.brand,
            condition_label=previous.condition_label,
            last_seen_at=evidence.get("last_seen_at"),
            latest_primary_scan_run_id=run_id,
            seen_in_latest_primary_scan=False,
            latest_probe=previous.latest_probe,
        )

    def _build_probe_snapshot(
        self,
        *,
        row: Mapping[str, object],
        previous: _DerivedListingSnapshot | None,
    ) -> _DerivedListingSnapshot:
        occurred_at = _required_str(row.get("probed_at"), field_name="probed_at")
        latest_probe = self._probe_payload_from_row(row)
        evidence = self._snapshot_evidence(
            listing_id=_required_int(row.get("listing_id"), field_name="listing_id"),
            occurred_at=occurred_at,
            previous=previous,
            latest_seen_row=None,
            latest_probe=latest_probe,
            follow_up_miss_count=0 if previous is None else int(previous.follow_up_miss_count),
            latest_primary_scan_run_id=None if previous is None else previous.latest_primary_scan_run_id,
            seen_in_latest_primary_scan=False if previous is None else previous.seen_in_latest_primary_scan,
            latest_price_amount_cents=_coalesce(_optional_int(row.get("price_amount_cents")), None if previous is None else previous.price_amount_cents),
            latest_total_price_amount_cents=_coalesce(_optional_int(row.get("total_price_amount_cents")), None if previous is None else previous.total_price_amount_cents),
            latest_favourite_count=_coalesce(_optional_int(row.get("favourite_count")), None if previous is None else previous.favourite_count),
            latest_view_count=_coalesce(_optional_int(row.get("view_count")), None if previous is None else previous.view_count),
            primary_catalog_id=_coalesce(_optional_int(row.get("primary_catalog_id")), None if previous is None else previous.primary_catalog_id),
            primary_root_catalog_id=_coalesce(_optional_int(row.get("primary_root_catalog_id")), None if previous is None else previous.primary_root_catalog_id),
            root_title=_coalesce(_optional_str(row.get("root_title")), None if previous is None else previous.root_title),
            category_path=_coalesce(_optional_str(row.get("category_path")), None if previous is None else previous.category_path),
            brand=_coalesce(_optional_str(row.get("brand")), None if previous is None else previous.brand),
            condition_label=_coalesce(_optional_str(row.get("condition_label")), None if previous is None else previous.condition_label),
        )
        evaluation = evaluate_listing_state(evidence, now=occurred_at)
        return self._snapshot_from_evaluation(
            listing_id=int(row["listing_id"]),
            occurred_at=occurred_at,
            evaluation=evaluation,
            price_amount_cents=evidence.get("price_amount_cents"),
            total_price_amount_cents=evidence.get("total_price_amount_cents"),
            favourite_count=evidence.get("favourite_count"),
            view_count=evidence.get("view_count"),
            follow_up_miss_count=int(evidence.get("follow_up_miss_count") or 0),
            probe_outcome=latest_probe.get("probe_outcome") if latest_probe is not None else None,
            response_status=latest_probe.get("response_status") if latest_probe is not None else None,
            primary_catalog_id=evidence.get("primary_catalog_id"),
            primary_root_catalog_id=evidence.get("primary_root_catalog_id"),
            root_title=evidence.get("root_title"),
            category_path=evidence.get("category_path"),
            brand=evidence.get("brand"),
            condition_label=evidence.get("condition_label"),
            last_seen_at=evidence.get("last_seen_at"),
            latest_primary_scan_run_id=evidence.get("latest_primary_scan_run_id"),
            seen_in_latest_primary_scan=bool(evidence.get("seen_in_latest_primary_scan")),
            latest_probe=latest_probe,
        )

    def _snapshot_evidence(
        self,
        *,
        listing_id: int,
        occurred_at: str,
        previous: _DerivedListingSnapshot | None,
        latest_seen_row: Mapping[str, object] | None,
        latest_probe: Mapping[str, object] | None,
        follow_up_miss_count: int,
        latest_primary_scan_run_id: str | None,
        seen_in_latest_primary_scan: bool,
        latest_price_amount_cents: object,
        latest_total_price_amount_cents: object,
        latest_favourite_count: object,
        latest_view_count: object,
        primary_catalog_id: object,
        primary_root_catalog_id: object,
        root_title: object,
        category_path: object,
        brand: object,
        condition_label: object,
    ) -> dict[str, object]:
        last_seen_at = _coalesce(
            None if latest_seen_row is None else _optional_str(latest_seen_row.get("observed_at")),
            None if previous is None else previous.last_seen_at,
        )
        return {
            "listing_id": listing_id,
            "observation_count": 1 if last_seen_at is not None else 0,
            "total_sightings": 1 if last_seen_at is not None else 0,
            "first_seen_at": last_seen_at,
            "last_seen_at": last_seen_at,
            "average_revisit_hours": None,
            "canonical_url": None if latest_seen_row is None else _optional_str(latest_seen_row.get("canonical_url")),
            "title": None if latest_seen_row is None else _optional_str(latest_seen_row.get("title")),
            "brand": _optional_str(brand),
            "size_label": None if latest_seen_row is None else _optional_str(latest_seen_row.get("size_label")),
            "condition_label": _optional_str(condition_label),
            "price_amount_cents": _optional_int(latest_price_amount_cents),
            "price_currency": None if latest_seen_row is None else _optional_str(latest_seen_row.get("price_currency")),
            "total_price_amount_cents": _optional_int(latest_total_price_amount_cents),
            "total_price_currency": None if latest_seen_row is None else _optional_str(latest_seen_row.get("total_price_currency")),
            "image_url": None if latest_seen_row is None else _optional_str(latest_seen_row.get("image_url")),
            "favourite_count": _optional_int(latest_favourite_count),
            "view_count": _optional_int(latest_view_count),
            "user_id": None if latest_seen_row is None else _optional_int(latest_seen_row.get("user_id")),
            "user_login": None if latest_seen_row is None else _optional_str(latest_seen_row.get("user_login")),
            "user_profile_url": None if latest_seen_row is None else _optional_str(latest_seen_row.get("user_profile_url")),
            "created_at_ts": None if latest_seen_row is None else _optional_int(latest_seen_row.get("created_at_ts")),
            "primary_catalog_id": _optional_int(primary_catalog_id),
            "primary_root_catalog_id": _optional_int(primary_root_catalog_id),
            "root_title": _optional_str(root_title),
            "category_path": _optional_str(category_path),
            "last_observed_run_id": None if latest_seen_row is None else _optional_str(latest_seen_row.get("run_id")),
            "latest_primary_scan_run_id": latest_primary_scan_run_id,
            "latest_primary_scan_at": occurred_at if latest_primary_scan_run_id is not None else None,
            "follow_up_miss_count": int(follow_up_miss_count),
            "latest_follow_up_miss_at": None if follow_up_miss_count == 0 or seen_in_latest_primary_scan else occurred_at,
            "seen_in_latest_primary_scan": seen_in_latest_primary_scan,
            "latest_probe": None if latest_probe is None else dict(latest_probe),
            "last_seen_age_hours": 0.0 if last_seen_at is None else round(_age_hours(last_seen_at, occurred_at), 2),
            "signal_completeness": 0,
            "freshness_bucket": "first-pass-only",
        }

    def _snapshot_from_evaluation(
        self,
        *,
        listing_id: int,
        occurred_at: str,
        evaluation: Mapping[str, object],
        price_amount_cents: object,
        total_price_amount_cents: object,
        favourite_count: object,
        view_count: object,
        follow_up_miss_count: int,
        probe_outcome: object,
        response_status: object,
        primary_catalog_id: object,
        primary_root_catalog_id: object,
        root_title: object,
        category_path: object,
        brand: object,
        condition_label: object,
        last_seen_at: object,
        latest_primary_scan_run_id: object,
        seen_in_latest_primary_scan: bool,
        latest_probe: Mapping[str, object] | None,
    ) -> _DerivedListingSnapshot:
        return _DerivedListingSnapshot(
            listing_id=listing_id,
            occurred_at=occurred_at,
            state_code=_optional_str(evaluation.get("state_code")),
            basis_kind=_optional_str(evaluation.get("basis_kind")),
            confidence_label=_optional_str(evaluation.get("confidence_label")),
            confidence_score=None if evaluation.get("confidence_score") is None else float(evaluation.get("confidence_score") or 0.0),
            price_amount_cents=_optional_int(price_amount_cents),
            total_price_amount_cents=_optional_int(total_price_amount_cents),
            favourite_count=_optional_int(favourite_count),
            view_count=_optional_int(view_count),
            follow_up_miss_count=int(follow_up_miss_count),
            probe_outcome=_optional_str(probe_outcome),
            response_status=_optional_int(response_status),
            primary_catalog_id=_optional_int(primary_catalog_id),
            primary_root_catalog_id=_optional_int(primary_root_catalog_id),
            root_title=_optional_str(root_title),
            category_path=_optional_str(category_path),
            brand=_optional_str(brand),
            condition_label=_optional_str(condition_label),
            last_seen_at=_optional_str(last_seen_at),
            latest_primary_scan_run_id=_optional_str(latest_primary_scan_run_id),
            seen_in_latest_primary_scan=seen_in_latest_primary_scan,
            latest_probe=None if latest_probe is None else dict(latest_probe),
            state_explanation=dict(evaluation.get("state_explanation") or {}),
        )

    def _build_change_rows(
        self,
        *,
        record: ClaimedOutboxRecord,
        manifest: EvidenceManifest,
        previous: _DerivedListingSnapshot | None,
        current: _DerivedListingSnapshot,
        metadata: Mapping[str, object],
    ) -> list[dict[str, object]]:
        change_kinds: list[str] = []
        if previous is None:
            change_kinds.append("state_transition")
        else:
            if any(
                (
                    previous.state_code != current.state_code,
                    previous.basis_kind != current.basis_kind,
                    previous.confidence_label != current.confidence_label,
                    previous.confidence_score != current.confidence_score,
                )
            ):
                change_kinds.append("state_transition")
            if previous.price_amount_cents != current.price_amount_cents or previous.total_price_amount_cents != current.total_price_amount_cents:
                change_kinds.append("price_change")
            if previous.favourite_count != current.favourite_count or previous.view_count != current.view_count:
                change_kinds.append("engagement_shift")
            if previous.follow_up_miss_count != current.follow_up_miss_count:
                change_kinds.append("follow_up_miss_transition")

        rows: list[dict[str, object]] = []
        for change_kind in change_kinds:
            rows.append(
                {
                    "event_id": deterministic_uuid(
                        "clickhouse.fact-listing-change",
                        {
                            "source_event_id": record.event.event_id,
                            "manifest_id": manifest.manifest_id,
                            "listing_id": current.listing_id,
                            "change_kind": change_kind,
                            "occurred_at": current.occurred_at,
                        },
                    ),
                    "manifest_id": manifest.manifest_id,
                    "source_event_id": record.event.event_id,
                    "source_event_type": record.event.event_type,
                    "schema_version": record.event.schema_version,
                    "occurred_at": current.occurred_at,
                    "producer": CLICKHOUSE_INGEST_PRODUCER,
                    "listing_id": current.listing_id,
                    "change_kind": change_kind,
                    "previous_state_code": None if previous is None else previous.state_code,
                    "current_state_code": current.state_code,
                    "previous_basis_kind": None if previous is None else previous.basis_kind,
                    "current_basis_kind": current.basis_kind,
                    "previous_confidence_label": None if previous is None else previous.confidence_label,
                    "current_confidence_label": current.confidence_label,
                    "previous_confidence_score": None if previous is None else previous.confidence_score,
                    "current_confidence_score": current.confidence_score,
                    "previous_price_amount_cents": None if previous is None else previous.price_amount_cents,
                    "current_price_amount_cents": current.price_amount_cents,
                    "previous_total_price_amount_cents": None if previous is None else previous.total_price_amount_cents,
                    "current_total_price_amount_cents": current.total_price_amount_cents,
                    "previous_favourite_count": None if previous is None else previous.favourite_count,
                    "current_favourite_count": current.favourite_count,
                    "previous_view_count": None if previous is None else previous.view_count,
                    "current_view_count": current.view_count,
                    "follow_up_miss_count": current.follow_up_miss_count,
                    "probe_outcome": current.probe_outcome,
                    "response_status": current.response_status,
                    "primary_catalog_id": current.primary_catalog_id,
                    "primary_root_catalog_id": current.primary_root_catalog_id,
                    "root_title": current.root_title,
                    "category_path": current.category_path,
                    "brand": current.brand,
                    "condition_label": current.condition_label,
                    "change_summary": self._change_summary(change_kind=change_kind, previous=previous, current=current),
                    "change_json": canonical_json(
                        {
                            "change_kind": change_kind,
                            "previous": None if previous is None else self._snapshot_change_payload(previous),
                            "current": self._snapshot_change_payload(current),
                            "state_explanation": dict(current.state_explanation),
                        }
                    ),
                    "metadata_json": canonical_json(
                        {
                            key: value
                            for key, value in {
                                **dict(metadata),
                                "capture_source": _optional_str(record.event.metadata.get("capture_source")),
                                "manifest_type": manifest.manifest_type,
                            }.items()
                            if value is not None
                        }
                    ),
                }
            )
        return rows

    def _change_summary(
        self,
        *,
        change_kind: str,
        previous: _DerivedListingSnapshot | None,
        current: _DerivedListingSnapshot,
    ) -> str:
        if change_kind == "state_transition":
            if previous is None:
                return f"Initial state projected as {current.state_code or 'unknown'}."
            return f"State {previous.state_code or 'unknown'} → {current.state_code or 'unknown'}."
        if change_kind == "price_change":
            return (
                f"Price {self._format_change_value(None if previous is None else previous.price_amount_cents)}"
                f" → {self._format_change_value(current.price_amount_cents)}."
            )
        if change_kind == "engagement_shift":
            return (
                f"Engagement likes {self._format_change_value(None if previous is None else previous.favourite_count)}"
                f" → {self._format_change_value(current.favourite_count)}, views {self._format_change_value(None if previous is None else previous.view_count)}"
                f" → {self._format_change_value(current.view_count)}."
            )
        return (
            f"Follow-up misses {self._format_change_value(None if previous is None else previous.follow_up_miss_count)}"
            f" → {self._format_change_value(current.follow_up_miss_count)}."
        )

    def _snapshot_change_payload(self, snapshot: _DerivedListingSnapshot) -> dict[str, object]:
        return {
            "occurred_at": snapshot.occurred_at,
            "state_code": snapshot.state_code,
            "basis_kind": snapshot.basis_kind,
            "confidence_label": snapshot.confidence_label,
            "confidence_score": snapshot.confidence_score,
            "price_amount_cents": snapshot.price_amount_cents,
            "total_price_amount_cents": snapshot.total_price_amount_cents,
            "favourite_count": snapshot.favourite_count,
            "view_count": snapshot.view_count,
            "follow_up_miss_count": snapshot.follow_up_miss_count,
            "probe_outcome": snapshot.probe_outcome,
            "response_status": snapshot.response_status,
            "primary_catalog_id": snapshot.primary_catalog_id,
            "primary_root_catalog_id": snapshot.primary_root_catalog_id,
            "root_title": snapshot.root_title,
            "category_path": snapshot.category_path,
            "brand": snapshot.brand,
            "condition_label": snapshot.condition_label,
            "last_seen_at": snapshot.last_seen_at,
            "latest_primary_scan_run_id": snapshot.latest_primary_scan_run_id,
            "seen_in_latest_primary_scan": snapshot.seen_in_latest_primary_scan,
        }

    def _probe_payload_from_row(self, row: Mapping[str, object] | None) -> dict[str, object] | None:
        if row is None:
            return None
        detail_json = row.get("detail_json") if "detail_json" in row else row.get("detail")
        return {
            "probed_at": _optional_str(row.get("probed_at")),
            "requested_url": _optional_str(row.get("requested_url")),
            "final_url": _optional_str(row.get("final_url")),
            "response_status": _optional_int(row.get("response_status")),
            "probe_outcome": _optional_str(row.get("probe_outcome")),
            "detail": _load_json_payload(detail_json),
            "error_message": _optional_str(row.get("error_message")),
        }

    def _is_terminal_catalog_batch(self, *, record: ClaimedOutboxRecord, manifest: EvidenceManifest) -> bool:
        if record.event.event_type != "vinted.discovery.listing-seen.batch":
            return False
        current_page = _optional_int(manifest.metadata.get("pagination_current_page")) or _optional_int(record.event.payload.get("page_number"))
        total_pages = _optional_int(manifest.metadata.get("pagination_total_pages"))
        next_page_url = _optional_str(manifest.metadata.get("next_page_url"))
        chunk_index = _optional_int(manifest.metadata.get("page_chunk_index")) or 0
        chunk_count = _optional_int(manifest.metadata.get("page_chunk_count")) or 1
        final_chunk = chunk_index >= max(chunk_count - 1, 0)
        if current_page is None:
            return False
        terminal_page = (total_pages is not None and current_page >= total_pages) or next_page_url is None
        return terminal_page and final_chunk

    def _latest_seen_rows_before(self, *, listing_ids: Sequence[int], before: str) -> dict[int, dict[str, object]]:
        ids_sql = ", ".join(str(int(listing_id)) for listing_id in listing_ids)
        sql = f"""
        /* clickhouse-ingest: latest-seen-before listing_ids={','.join(str(int(listing_id)) for listing_id in listing_ids)} before={before} */
        SELECT *
        FROM (
            SELECT
                listing_id,
                observed_at,
                run_id,
                canonical_url,
                source_url,
                title,
                brand,
                size_label,
                condition_label,
                price_amount_cents,
                price_currency,
                total_price_amount_cents,
                total_price_currency,
                image_url,
                favourite_count,
                view_count,
                user_id,
                user_login,
                user_profile_url,
                created_at_ts,
                primary_catalog_id,
                primary_root_catalog_id,
                root_title,
                category_path,
                event_id,
                row_number() OVER (PARTITION BY listing_id ORDER BY observed_at DESC, event_id DESC) AS row_rank
            FROM {self.database}.fact_listing_seen_events
            WHERE listing_id IN ({ids_sql}) AND observed_at < {_sql_string(before)}
        )
        WHERE row_rank = 1
        """
        return {int(row["listing_id"]): row for row in _query_rows(self.clickhouse_client, sql)}

    def _latest_probe_rows_before(self, *, listing_ids: Sequence[int], before: str) -> dict[int, dict[str, object]]:
        ids_sql = ", ".join(str(int(listing_id)) for listing_id in listing_ids)
        sql = f"""
        /* clickhouse-ingest: latest-probe-before listing_ids={','.join(str(int(listing_id)) for listing_id in listing_ids)} before={before} */
        SELECT *
        FROM (
            SELECT
                listing_id,
                probed_at,
                requested_url,
                final_url,
                response_status,
                probe_outcome,
                reason,
                error_message,
                detail_json,
                event_id,
                row_number() OVER (PARTITION BY listing_id ORDER BY probed_at DESC, event_id DESC) AS row_rank
            FROM {self.database}.fact_listing_probe_events
            WHERE listing_id IN ({ids_sql}) AND probed_at < {_sql_string(before)}
        )
        WHERE row_rank = 1
        """
        return {int(row["listing_id"]): row for row in _query_rows(self.clickhouse_client, sql)}

    def _latest_change_rows_before(self, *, listing_ids: Sequence[int], before: str) -> dict[int, dict[str, object]]:
        ids_sql = ", ".join(str(int(listing_id)) for listing_id in listing_ids)
        sql = f"""
        /* clickhouse-ingest: latest-change-before listing_ids={','.join(str(int(listing_id)) for listing_id in listing_ids)} before={before} */
        SELECT *
        FROM (
            SELECT
                listing_id,
                occurred_at,
                change_kind,
                current_state_code,
                current_basis_kind,
                current_confidence_label,
                current_confidence_score,
                current_price_amount_cents,
                current_total_price_amount_cents,
                current_favourite_count,
                current_view_count,
                follow_up_miss_count,
                probe_outcome,
                response_status,
                primary_catalog_id,
                primary_root_catalog_id,
                root_title,
                category_path,
                brand,
                condition_label,
                event_id,
                row_number() OVER (PARTITION BY listing_id ORDER BY occurred_at DESC, event_id DESC) AS row_rank
            FROM {self.database}.fact_listing_change_events
            WHERE listing_id IN ({ids_sql}) AND occurred_at < {_sql_string(before)}
        )
        WHERE row_rank = 1
        """
        return {int(row["listing_id"]): row for row in _query_rows(self.clickhouse_client, sql)}

    def _latest_catalog_seen_rows_before(self, *, catalog_id: int, before: str) -> dict[int, dict[str, object]]:
        sql = f"""
        /* clickhouse-ingest: catalog-latest-seen-before catalog_id={int(catalog_id)} before={before} */
        SELECT *
        FROM (
            SELECT
                listing_id,
                observed_at,
                run_id,
                canonical_url,
                source_url,
                title,
                brand,
                size_label,
                condition_label,
                price_amount_cents,
                price_currency,
                total_price_amount_cents,
                total_price_currency,
                image_url,
                favourite_count,
                view_count,
                user_id,
                user_login,
                user_profile_url,
                created_at_ts,
                primary_catalog_id,
                primary_root_catalog_id,
                root_title,
                category_path,
                event_id,
                row_number() OVER (PARTITION BY listing_id ORDER BY observed_at DESC, event_id DESC) AS row_rank
            FROM {self.database}.fact_listing_seen_events
            WHERE primary_catalog_id = {int(catalog_id)} AND observed_at < {_sql_string(before)}
        )
        WHERE row_rank = 1
        """
        return {int(row["listing_id"]): row for row in _query_rows(self.clickhouse_client, sql)}

    def _listing_ids_seen_in_catalog_run(self, *, catalog_id: int, run_id: str) -> set[int]:
        sql = f"""
        /* clickhouse-ingest: run-catalog-listing-ids catalog_id={int(catalog_id)} run_id={run_id} */
        SELECT DISTINCT listing_id
        FROM {self.database}.fact_listing_seen_events
        WHERE primary_catalog_id = {int(catalog_id)} AND run_id = {_sql_string(run_id)}
        """
        return {int(row["listing_id"]) for row in _query_rows(self.clickhouse_client, sql)}

    def _format_change_value(self, value: object) -> str:
        return "n/a" if value is None else str(value)

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


def _coalesce(primary: object, fallback: object | None = None) -> object | None:
    if primary is not None:
        return primary
    return fallback



def _coalesce_str(primary: object, fallback: object | None = None, default: str | None = None) -> str | None:
    value = _optional_str(primary)
    if value is not None:
        return value
    value = _optional_str(fallback)
    if value is not None:
        return value
    return default



def _coalesce_int(primary: object, fallback_row: Mapping[str, object] | None, fallback_key: str) -> int | None:
    value = _optional_int(primary)
    if value is not None:
        return value
    if fallback_row is None:
        return None
    return _optional_int(fallback_row.get(fallback_key))



def _age_hours(timestamp: str, now: str) -> float:
    return max((_parse_timestamp(now) - _parse_timestamp(timestamp)).total_seconds() / 3600.0, 0.0)



def _load_json_payload(value: object) -> dict[str, object]:
    if value in {None, ""}:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}



def _query_rows(clickhouse_client: object, sql: str) -> list[dict[str, object]]:
    result = clickhouse_client.query(sql)
    rows = getattr(result, "result_rows", ()) or ()
    if not rows:
        return []
    if isinstance(rows[0], Mapping):
        return [{str(key): _normalize_value(value) for key, value in dict(row).items()} for row in rows]
    column_names = getattr(result, "column_names", None)
    if not column_names:
        raise RuntimeError("ClickHouse query result is missing column_names.")
    normalized_column_names = [str(name) for name in column_names]
    return [
        {
            normalized_column_names[index]: _normalize_value(value)
            for index, value in enumerate(row)
        }
        for row in rows
    ]



def _normalize_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_value(item) for item in value)
    return value



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
