from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlsplit

from vinted_radar.domain.events import EventEnvelope
from vinted_radar.platform.clickhouse_ingest import CLICKHOUSE_OUTBOX_SINK, ClickHouseIngestReport, ClickHouseIngestService
from vinted_radar.platform.config import PlatformConfig, load_platform_config, redact_url_credentials
from vinted_radar.platform.lake_writer import LakeWriteResult, ParquetLakeWriter
from vinted_radar.platform.outbox import OutboxPublishResult, PostgresOutbox
from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository
from vinted_radar.repository import RadarRepository
from vinted_radar.services.evidence_export import (
    _hydrate_discovery_row,
    _hydrate_observation_row,
    _hydrate_probe_row,
)
from vinted_radar.services.postgres_backfill import PostgresBackfillReport, backfill_postgres_mutable_truth

_FULL_BACKFILL_CHECKPOINT_VERSION = 1
_DEFAULT_DATASET_ORDER = (
    "discoveries",
    "observations",
    "probes",
    "runtime-cycles",
    "runtime-controller",
)


@dataclass(frozen=True, slots=True)
class FullBackfillDatasetReport:
    dataset: str
    completed_batches: int
    completed_rows: int
    skipped_batches: int
    skipped_rows: int
    last_group_key: str | None
    last_event_id: str | None
    last_manifest_id: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset": self.dataset,
            "completed_batches": self.completed_batches,
            "completed_rows": self.completed_rows,
            "skipped_batches": self.skipped_batches,
            "skipped_rows": self.skipped_rows,
            "last_group_key": self.last_group_key,
            "last_event_id": self.last_event_id,
            "last_manifest_id": self.last_manifest_id,
        }


@dataclass(frozen=True, slots=True)
class FullBackfillReport:
    sqlite_db_path: str
    postgres_dsn: str
    clickhouse_url: str
    clickhouse_database: str
    object_store_bucket: str
    reference_now: str
    dry_run: bool
    resumed_from_checkpoint: bool
    checkpoint_path: str | None
    checkpoint_completed: bool
    postgres_backfill: PostgresBackfillReport
    datasets: tuple[FullBackfillDatasetReport, ...]
    clickhouse_claimed_count: int
    clickhouse_processed_count: int
    clickhouse_skipped_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "sqlite_db_path": self.sqlite_db_path,
            "postgres_dsn": redact_url_credentials(self.postgres_dsn),
            "clickhouse_url": self.clickhouse_url,
            "clickhouse_database": self.clickhouse_database,
            "object_store_bucket": self.object_store_bucket,
            "reference_now": self.reference_now,
            "dry_run": self.dry_run,
            "resumed_from_checkpoint": self.resumed_from_checkpoint,
            "checkpoint_path": self.checkpoint_path,
            "checkpoint_completed": self.checkpoint_completed,
            "postgres_backfill": self.postgres_backfill.as_dict(),
            "datasets": [dataset.as_dict() for dataset in self.datasets],
            "clickhouse_claimed_count": self.clickhouse_claimed_count,
            "clickhouse_processed_count": self.clickhouse_processed_count,
            "clickhouse_skipped_count": self.clickhouse_skipped_count,
        }


@dataclass(frozen=True, slots=True)
class _PreparedBatch:
    dataset: str
    group_key: str
    rows: tuple[dict[str, object], ...]
    batch_event: EventEnvelope
    publish_clickhouse: bool
    manifest_metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class _DeliveredBatch:
    lake_write: LakeWriteResult
    outbox_publish: OutboxPublishResult | None
    clickhouse_ingest: ClickHouseIngestReport | None


class FullBackfillService:
    def __init__(
        self,
        sqlite_db_path: str | Path,
        *,
        config: PlatformConfig | None = None,
        reference_now: str | None = None,
        repository: PostgresMutableTruthRepository | object | None = None,
        outbox: PostgresOutbox | None = None,
        lake_writer: ParquetLakeWriter | None = None,
        clickhouse_ingest: ClickHouseIngestService | None = None,
        postgres_connection: object | None = None,
        object_store_client: object | None = None,
        clickhouse_client: object | None = None,
    ) -> None:
        self.sqlite_db_path = Path(sqlite_db_path)
        self.config = load_platform_config() if config is None else config
        self.reference_now = reference_now
        self.repository = repository
        self.outbox = outbox
        self.lake_writer = lake_writer
        self.clickhouse_ingest = clickhouse_ingest
        self._postgres_connection = postgres_connection
        self._object_store_client = object_store_client
        self._clickhouse_client = clickhouse_client
        self._owned_closeables: list[object] = []

    def close(self) -> None:
        for resource in reversed(self._owned_closeables):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass
        self._owned_closeables.clear()

    def run(
        self,
        *,
        batch_size: int = 500,
        dry_run: bool = False,
        sync_runtime_control: bool = True,
        checkpoint_path: str | Path | None = None,
        reset_checkpoint: bool = False,
        clickhouse_lease_seconds: int = 60,
    ) -> FullBackfillReport:
        resolved_checkpoint_path = None if checkpoint_path is None else Path(checkpoint_path)
        resumed_from_checkpoint = False

        if resolved_checkpoint_path is not None and resolved_checkpoint_path.exists() and not reset_checkpoint:
            checkpoint = _load_checkpoint(resolved_checkpoint_path)
            reference_now = self.reference_now or str(checkpoint.get("reference_now") or _utc_now())
            _validate_checkpoint(
                checkpoint=checkpoint,
                sqlite_db_path=self.sqlite_db_path,
                reference_now=reference_now,
                sync_runtime_control=sync_runtime_control,
            )
            resumed_from_checkpoint = True
            if checkpoint.get("completed") and not dry_run:
                return self._report_from_checkpoint(
                    checkpoint=checkpoint,
                    checkpoint_path=resolved_checkpoint_path,
                    dry_run=False,
                    resumed_from_checkpoint=True,
                )
        else:
            reference_now = self.reference_now or _utc_now()
            checkpoint = _default_checkpoint(
                sqlite_db_path=self.sqlite_db_path,
                reference_now=reference_now,
                sync_runtime_control=sync_runtime_control,
            )

        self._checkpoint_state = checkpoint

        if dry_run:
            return self._run_dry(
                batch_size=max(int(batch_size), 1),
                reference_now=reference_now,
                sync_runtime_control=sync_runtime_control,
                checkpoint=checkpoint,
                checkpoint_path=resolved_checkpoint_path,
                resumed_from_checkpoint=resumed_from_checkpoint,
            )

        self._ensure_runtime_dependencies()
        assert self.repository is not None
        assert self.outbox is not None
        assert self.lake_writer is not None

        self.lake_writer.object_store.ensure_bucket()

        if not bool((checkpoint.get("postgres_backfill") or {}).get("completed")):
            postgres_report = backfill_postgres_mutable_truth(
                self.sqlite_db_path,
                config=self.config,
                repository=self.repository,
                reference_now=reference_now,
                sync_runtime_control=sync_runtime_control,
            )
            checkpoint["postgres_backfill"] = {
                "completed": True,
                "report": postgres_report.as_dict(),
            }
            self._write_checkpoint(resolved_checkpoint_path, checkpoint)
        else:
            postgres_report = PostgresBackfillReport(**dict((checkpoint.get("postgres_backfill") or {}).get("report") or {}))

        clickhouse_claimed_count = 0
        clickhouse_processed_count = 0
        clickhouse_skipped_count = 0
        dataset_reports: list[FullBackfillDatasetReport] = []

        with RadarRepository(self.sqlite_db_path) as source:
            for dataset in self._dataset_order(sync_runtime_control=sync_runtime_control):
                state = _dataset_state(checkpoint, dataset)
                completed_batches = int(state.get("completed_batches") or 0)
                completed_rows = int(state.get("completed_rows") or 0)
                skipped_batches = 0
                skipped_rows = 0
                last_group_key = _optional_str(state.get("last_group_key"))
                last_event_id = _optional_str(state.get("last_event_id"))
                last_manifest_id = _optional_str(state.get("last_manifest_id"))

                for batch_index, prepared in enumerate(self._iter_dataset_batches(source, dataset=dataset, batch_size=max(int(batch_size), 1), reference_now=reference_now)):
                    row_count = len(prepared.rows)
                    if batch_index < completed_batches:
                        skipped_batches += 1
                        skipped_rows += row_count
                        continue

                    delivered = self._deliver_batch(
                        prepared,
                        clickhouse_lease_seconds=max(int(clickhouse_lease_seconds), 1),
                    )
                    completed_batches += 1
                    completed_rows += row_count
                    last_group_key = prepared.group_key
                    last_event_id = prepared.batch_event.event_id
                    last_manifest_id = delivered.lake_write.manifest.manifest_id
                    if delivered.clickhouse_ingest is not None:
                        clickhouse_claimed_count += delivered.clickhouse_ingest.claimed_count
                        clickhouse_processed_count += delivered.clickhouse_ingest.processed_count
                        clickhouse_skipped_count += delivered.clickhouse_ingest.skipped_count
                    state.update(
                        {
                            "completed_batches": completed_batches,
                            "completed_rows": completed_rows,
                            "last_group_key": last_group_key,
                            "last_event_id": last_event_id,
                            "last_manifest_id": last_manifest_id,
                        }
                    )
                    self._write_checkpoint(resolved_checkpoint_path, checkpoint)

                dataset_reports.append(
                    FullBackfillDatasetReport(
                        dataset=dataset,
                        completed_batches=completed_batches,
                        completed_rows=completed_rows,
                        skipped_batches=skipped_batches,
                        skipped_rows=skipped_rows,
                        last_group_key=last_group_key,
                        last_event_id=last_event_id,
                        last_manifest_id=last_manifest_id,
                    )
                )

        checkpoint["completed"] = True
        checkpoint["updated_at"] = _utc_now()
        self._write_checkpoint(resolved_checkpoint_path, checkpoint)
        return FullBackfillReport(
            sqlite_db_path=str(self.sqlite_db_path),
            postgres_dsn=self.config.postgres.dsn,
            clickhouse_url=self.config.clickhouse.url,
            clickhouse_database=self.config.clickhouse.database,
            object_store_bucket=self.config.object_storage.bucket,
            reference_now=reference_now,
            dry_run=False,
            resumed_from_checkpoint=resumed_from_checkpoint,
            checkpoint_path=None if resolved_checkpoint_path is None else str(resolved_checkpoint_path),
            checkpoint_completed=True,
            postgres_backfill=postgres_report,
            datasets=tuple(dataset_reports),
            clickhouse_claimed_count=clickhouse_claimed_count,
            clickhouse_processed_count=clickhouse_processed_count,
            clickhouse_skipped_count=clickhouse_skipped_count,
        )

    def _run_dry(
        self,
        *,
        batch_size: int,
        reference_now: str,
        sync_runtime_control: bool,
        checkpoint: dict[str, object],
        checkpoint_path: Path | None,
        resumed_from_checkpoint: bool,
    ) -> FullBackfillReport:
        postgres_report = self._inspect_postgres_backfill(reference_now=reference_now, sync_runtime_control=sync_runtime_control)
        dataset_reports: list[FullBackfillDatasetReport] = []
        with RadarRepository(self.sqlite_db_path) as source:
            for dataset in self._dataset_order(sync_runtime_control=sync_runtime_control):
                state = _dataset_state(checkpoint, dataset)
                completed_batches = int(state.get("completed_batches") or 0)
                completed_rows = int(state.get("completed_rows") or 0)
                skipped_batches = 0
                skipped_rows = 0
                last_group_key = _optional_str(state.get("last_group_key"))
                last_event_id = _optional_str(state.get("last_event_id"))
                last_manifest_id = _optional_str(state.get("last_manifest_id"))
                for batch_index, prepared in enumerate(self._iter_dataset_batches(source, dataset=dataset, batch_size=batch_size, reference_now=reference_now)):
                    if batch_index < completed_batches:
                        skipped_batches += 1
                        skipped_rows += len(prepared.rows)
                dataset_reports.append(
                    FullBackfillDatasetReport(
                        dataset=dataset,
                        completed_batches=completed_batches,
                        completed_rows=completed_rows,
                        skipped_batches=skipped_batches,
                        skipped_rows=skipped_rows,
                        last_group_key=last_group_key,
                        last_event_id=last_event_id,
                        last_manifest_id=last_manifest_id,
                    )
                )
        return FullBackfillReport(
            sqlite_db_path=str(self.sqlite_db_path),
            postgres_dsn=self.config.postgres.dsn,
            clickhouse_url=self.config.clickhouse.url,
            clickhouse_database=self.config.clickhouse.database,
            object_store_bucket=self.config.object_storage.bucket,
            reference_now=reference_now,
            dry_run=True,
            resumed_from_checkpoint=resumed_from_checkpoint,
            checkpoint_path=None if checkpoint_path is None else str(checkpoint_path),
            checkpoint_completed=bool(checkpoint.get("completed")),
            postgres_backfill=postgres_report,
            datasets=tuple(dataset_reports),
            clickhouse_claimed_count=0,
            clickhouse_processed_count=0,
            clickhouse_skipped_count=0,
        )

    def _report_from_checkpoint(
        self,
        *,
        checkpoint: Mapping[str, object],
        checkpoint_path: Path | None,
        dry_run: bool,
        resumed_from_checkpoint: bool,
    ) -> FullBackfillReport:
        postgres_report = PostgresBackfillReport(**dict((checkpoint.get("postgres_backfill") or {}).get("report") or {}))
        dataset_reports = tuple(
            FullBackfillDatasetReport(
                dataset=dataset,
                completed_batches=int(state.get("completed_batches") or 0),
                completed_rows=int(state.get("completed_rows") or 0),
                skipped_batches=0,
                skipped_rows=0,
                last_group_key=_optional_str(state.get("last_group_key")),
                last_event_id=_optional_str(state.get("last_event_id")),
                last_manifest_id=_optional_str(state.get("last_manifest_id")),
            )
            for dataset, state in sorted(dict(checkpoint.get("datasets") or {}).items())
        )
        clickhouse = dict(checkpoint.get("clickhouse") or {})
        return FullBackfillReport(
            sqlite_db_path=str(self.sqlite_db_path),
            postgres_dsn=self.config.postgres.dsn,
            clickhouse_url=self.config.clickhouse.url,
            clickhouse_database=self.config.clickhouse.database,
            object_store_bucket=self.config.object_storage.bucket,
            reference_now=str(checkpoint.get("reference_now") or self.reference_now or _utc_now()),
            dry_run=dry_run,
            resumed_from_checkpoint=resumed_from_checkpoint,
            checkpoint_path=None if checkpoint_path is None else str(checkpoint_path),
            checkpoint_completed=bool(checkpoint.get("completed")),
            postgres_backfill=postgres_report,
            datasets=dataset_reports,
            clickhouse_claimed_count=int(clickhouse.get("claimed_count") or 0),
            clickhouse_processed_count=int(clickhouse.get("processed_count") or 0),
            clickhouse_skipped_count=int(clickhouse.get("skipped_count") or 0),
        )

    def _ensure_runtime_dependencies(self) -> None:
        if self.repository is not None and self.outbox is not None and self.lake_writer is not None:
            if self.clickhouse_ingest is None:
                client = self._clickhouse_client
                if client is None:
                    client = _get_clickhouse_client(self.config, database=self.config.clickhouse.database)
                    self._clickhouse_client = client
                    self._owned_closeables.append(client)
                self.clickhouse_ingest = ClickHouseIngestService(
                    repository=self.repository,
                    outbox=self.outbox,
                    lake_writer=self.lake_writer,
                    clickhouse_client=client,
                    database=self.config.clickhouse.database,
                )
            return

        if self._postgres_connection is None:
            self._postgres_connection = _connect_postgres(self.config.postgres.dsn)
            self._owned_closeables.append(self._postgres_connection)
        if self.repository is None:
            self.repository = PostgresMutableTruthRepository(self._postgres_connection)
        if self.outbox is None:
            self.outbox = PostgresOutbox(self._postgres_connection)
        if self.lake_writer is None:
            self.lake_writer = ParquetLakeWriter.from_config(self.config, client=self._object_store_client)
            if self._object_store_client is None:
                self._owned_closeables.append(self.lake_writer.object_store.client)
        if self.clickhouse_ingest is None:
            client = self._clickhouse_client
            if client is None:
                client = _get_clickhouse_client(self.config, database=self.config.clickhouse.database)
                self._clickhouse_client = client
                self._owned_closeables.append(client)
            self.clickhouse_ingest = ClickHouseIngestService(
                repository=self.repository,
                outbox=self.outbox,
                lake_writer=self.lake_writer,
                clickhouse_client=client,
                database=self.config.clickhouse.database,
            )

    def _deliver_batch(
        self,
        prepared: _PreparedBatch,
        *,
        clickhouse_lease_seconds: int,
    ) -> _DeliveredBatch:
        assert self.lake_writer is not None
        lake_write = self.lake_writer.write_batch(
            batch_event=prepared.batch_event,
            rows=prepared.rows,
            manifest_type=_manifest_type(prepared.dataset),
            manifest_metadata={
                **prepared.manifest_metadata,
                "legacy_dataset": prepared.dataset,
                "group_key": prepared.group_key,
                "capture_source": "sqlite_backfill",
                "row_count": len(prepared.rows),
            },
        )
        outbox_publish: OutboxPublishResult | None = None
        clickhouse_report: ClickHouseIngestReport | None = None
        if prepared.publish_clickhouse:
            assert self.outbox is not None
            assert self.clickhouse_ingest is not None
            outbox_publish = self.outbox.publish(
                prepared.batch_event,
                sinks=[CLICKHOUSE_OUTBOX_SINK],
                manifest=lake_write.manifest,
            )
            clickhouse_report = self.clickhouse_ingest.ingest_available(
                limit=1,
                lease_seconds=clickhouse_lease_seconds,
                now=_utc_now(),
            )
            # Persist cumulative worker progress in the resume checkpoint for no-op reruns.
            checkpoint_bucket = {
                "claimed_count": int(clickhouse_report.claimed_count),
                "processed_count": int(clickhouse_report.processed_count),
                "skipped_count": int(clickhouse_report.skipped_count),
            }
            state = self._current_checkpoint_mutation_target()
            state["claimed_count"] = int(state.get("claimed_count") or 0) + checkpoint_bucket["claimed_count"]
            state["processed_count"] = int(state.get("processed_count") or 0) + checkpoint_bucket["processed_count"]
            state["skipped_count"] = int(state.get("skipped_count") or 0) + checkpoint_bucket["skipped_count"]
        return _DeliveredBatch(
            lake_write=lake_write,
            outbox_publish=outbox_publish,
            clickhouse_ingest=clickhouse_report,
        )

    def _inspect_postgres_backfill(self, *, reference_now: str, sync_runtime_control: bool) -> PostgresBackfillReport:
        with RadarRepository(self.sqlite_db_path) as source:
            discovery_runs = int(
                source.connection.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()[0]
            )
            catalogs = int(source.connection.execute("SELECT COUNT(*) FROM catalogs").fetchone()[0])
            listing_rows = len(source.listing_state_inputs(now=reference_now))
            runtime_cycles = 0
            runtime_controller_rows = 0
            if sync_runtime_control:
                runtime_cycles = int(source.connection.execute("SELECT COUNT(*) FROM runtime_cycles").fetchone()[0])
                runtime_controller_rows = 0 if source.runtime_controller_state(now=reference_now) is None else 1
        return PostgresBackfillReport(
            sqlite_db_path=str(self.sqlite_db_path),
            postgres_dsn=self.config.postgres.dsn,
            reference_now=reference_now,
            discovery_runs=discovery_runs,
            catalogs=catalogs,
            listing_identities=listing_rows,
            listing_presence_summaries=listing_rows,
            listing_current_states=listing_rows,
            runtime_cycles=runtime_cycles,
            runtime_controller_rows=runtime_controller_rows,
        )

    def _dataset_order(self, *, sync_runtime_control: bool) -> tuple[str, ...]:
        if sync_runtime_control:
            return _DEFAULT_DATASET_ORDER
        return tuple(dataset for dataset in _DEFAULT_DATASET_ORDER if not dataset.startswith("runtime-"))

    def _iter_dataset_batches(
        self,
        source: RadarRepository,
        *,
        dataset: str,
        batch_size: int,
        reference_now: str,
    ) -> Iterator[_PreparedBatch]:
        if dataset == "discoveries":
            yield from self._iter_discovery_batches(source, batch_size=batch_size)
            return
        if dataset == "observations":
            yield from self._iter_observation_batches(source, batch_size=batch_size)
            return
        if dataset == "probes":
            yield from self._iter_probe_batches(source, batch_size=batch_size, reference_now=reference_now)
            return
        if dataset == "runtime-cycles":
            yield from self._iter_runtime_cycle_batches(source, batch_size=batch_size)
            return
        if dataset == "runtime-controller":
            yield from self._iter_runtime_controller_batches(source, reference_now=reference_now)
            return
        raise ValueError(f"Unsupported backfill dataset: {dataset}")

    def _iter_discovery_batches(self, source: RadarRepository, *, batch_size: int) -> Iterator[_PreparedBatch]:
        cursor = source.connection.execute(
            """
            SELECT
                discoveries.run_id,
                discoveries.listing_id,
                discoveries.observed_at,
                discoveries.source_catalog_id,
                discoveries.source_page_number,
                discoveries.source_url,
                discoveries.card_position,
                discoveries.raw_card_payload_json,
                listings.canonical_url AS listing_canonical_url,
                listings.title AS listing_title,
                listings.brand AS listing_brand,
                listings.size_label AS listing_size_label,
                listings.condition_label AS listing_condition_label,
                listings.price_amount_cents AS listing_price_amount_cents,
                listings.price_currency AS listing_price_currency,
                listings.total_price_amount_cents AS listing_total_price_amount_cents,
                listings.total_price_currency AS listing_total_price_currency,
                listings.image_url AS listing_image_url,
                listings.primary_catalog_id AS listing_primary_catalog_id,
                listings.primary_root_catalog_id AS listing_primary_root_catalog_id,
                source_catalog.root_catalog_id AS source_root_catalog_id,
                source_catalog.root_title AS source_root_title,
                source_catalog.title AS source_catalog_title,
                source_catalog.path AS source_catalog_path,
                primary_catalog.title AS primary_catalog_title,
                primary_catalog.path AS primary_catalog_path,
                resolved_root.title AS resolved_root_title,
                scans.pagination_total_pages AS scan_pagination_total_pages,
                scans.next_page_url AS scan_next_page_url
            FROM listing_discoveries AS discoveries
            LEFT JOIN listings ON listings.listing_id = discoveries.listing_id
            LEFT JOIN catalogs AS source_catalog ON source_catalog.catalog_id = discoveries.source_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN catalogs AS resolved_root
              ON resolved_root.catalog_id = COALESCE(source_catalog.root_catalog_id, primary_catalog.root_catalog_id, listings.primary_root_catalog_id)
            LEFT JOIN catalog_scans AS scans
              ON scans.run_id = discoveries.run_id
             AND scans.catalog_id = discoveries.source_catalog_id
             AND scans.page_number = discoveries.source_page_number
            ORDER BY
                discoveries.run_id ASC,
                discoveries.source_catalog_id ASC,
                discoveries.source_page_number ASC,
                discoveries.observed_at ASC,
                discoveries.listing_id ASC
            """
        )
        current_group: tuple[str, int | None, int | None] | None = None
        current_rows: list[dict[str, object]] = []
        for row in cursor:
            hydrated = _hydrate_discovery_row(row)
            hydrated["pagination_total_pages"] = _optional_int(row["scan_pagination_total_pages"])
            hydrated["next_page_url"] = _optional_str(row["scan_next_page_url"])
            group = (
                str(hydrated["run_id"]),
                _optional_int(hydrated.get("catalog_id")),
                _optional_int(hydrated.get("page_number")),
            )
            if current_group is None:
                current_group = group
            elif group != current_group:
                chunk_count = max((len(current_rows) - 1) // max(batch_size, 1) + 1, 1)
                for chunk_index in range(chunk_count):
                    start = chunk_index * max(batch_size, 1)
                    yield self._prepare_discovery_batch(
                        current_group,
                        current_rows[start : start + max(batch_size, 1)],
                        chunk_index=chunk_index,
                        chunk_count=chunk_count,
                    )
                current_group = group
                current_rows = []
            current_rows.append(hydrated)
        if current_group is not None and current_rows:
            chunk_count = max((len(current_rows) - 1) // max(batch_size, 1) + 1, 1)
            for chunk_index in range(chunk_count):
                start = chunk_index * max(batch_size, 1)
                yield self._prepare_discovery_batch(
                    current_group,
                    current_rows[start : start + max(batch_size, 1)],
                    chunk_index=chunk_index,
                    chunk_count=chunk_count,
                )

    def _prepare_discovery_batch(
        self,
        group: tuple[str, int | None, int | None],
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
        chunk_count: int,
    ) -> _PreparedBatch:
        run_id, catalog_id, page_number = group
        first = rows[0]
        group_key = (
            f"run_id={run_id}/catalog_id={catalog_id if catalog_id is not None else 'none'}"
            f"/page_number={page_number if page_number is not None else 'none'}/chunk={chunk_index}"
        )
        batch_event = EventEnvelope.create(
            schema_version=self.config.schema_versions.events,
            event_type="vinted.discovery.listing-seen.batch",
            aggregate_type="discovery-run",
            aggregate_id=run_id,
            occurred_at=str(first["observed_at"]),
            producer="vinted_radar.services.full_backfill",
            partition_key=first.get("root_catalog_id") or catalog_id or run_id,
            payload={
                "run_id": run_id,
                "catalog_id": catalog_id,
                "root_catalog_id": first.get("root_catalog_id"),
                "page_number": page_number,
                "chunk_index": chunk_index,
                "page_chunk_count": chunk_count,
                "row_count": len(rows),
                "listing_ids": [int(row["listing_id"]) for row in rows],
            },
            metadata={
                "capture_source": "sqlite_backfill",
                "root_title": first.get("root_title"),
                "catalog_title": first.get("catalog_title"),
                "catalog_path": first.get("catalog_path"),
                "pagination_current_page": page_number,
                "pagination_total_pages": first.get("pagination_total_pages"),
                "next_page_url": first.get("next_page_url"),
            },
            identity={
                "capture_source": "sqlite_backfill",
                "run_id": run_id,
                "catalog_id": catalog_id,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "observed_at": first["observed_at"],
            },
        )
        return _PreparedBatch(
            dataset="discoveries",
            group_key=group_key,
            rows=tuple(dict(row) for row in rows),
            batch_event=batch_event,
            publish_clickhouse=True,
            manifest_metadata={
                "run_id": run_id,
                "catalog_id": catalog_id,
                "root_catalog_id": first.get("root_catalog_id"),
                "catalog_path": first.get("catalog_path"),
                "page_number": page_number,
                "page_chunk_index": chunk_index,
                "page_chunk_count": chunk_count,
                "pagination_current_page": page_number,
                "pagination_total_pages": first.get("pagination_total_pages"),
                "next_page_url": first.get("next_page_url"),
                "first_observed_at": rows[0].get("observed_at"),
                "last_observed_at": rows[-1].get("observed_at"),
            },
        )

    def _iter_observation_batches(self, source: RadarRepository, *, batch_size: int) -> Iterator[_PreparedBatch]:
        cursor = source.connection.execute(
            """
            SELECT
                observations.run_id,
                observations.listing_id,
                observations.observed_at,
                observations.canonical_url,
                observations.source_url,
                observations.source_catalog_id,
                observations.source_page_number,
                observations.first_card_position,
                observations.sighting_count,
                observations.title AS observation_title,
                observations.brand AS observation_brand,
                observations.size_label AS observation_size_label,
                observations.condition_label AS observation_condition_label,
                observations.price_amount_cents AS observation_price_amount_cents,
                observations.price_currency AS observation_price_currency,
                observations.total_price_amount_cents AS observation_total_price_amount_cents,
                observations.total_price_currency AS observation_total_price_currency,
                observations.image_url AS observation_image_url,
                observations.raw_card_payload_json,
                listings.primary_catalog_id AS listing_primary_catalog_id,
                listings.primary_root_catalog_id AS listing_primary_root_catalog_id,
                source_catalog.root_catalog_id AS source_root_catalog_id,
                source_catalog.root_title AS source_root_title,
                source_catalog.title AS source_catalog_title,
                source_catalog.path AS source_catalog_path,
                primary_catalog.title AS primary_catalog_title,
                primary_catalog.path AS primary_catalog_path,
                resolved_root.title AS resolved_root_title
            FROM listing_observations AS observations
            LEFT JOIN listings ON listings.listing_id = observations.listing_id
            LEFT JOIN catalogs AS source_catalog ON source_catalog.catalog_id = observations.source_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN catalogs AS resolved_root
              ON resolved_root.catalog_id = COALESCE(source_catalog.root_catalog_id, primary_catalog.root_catalog_id, listings.primary_root_catalog_id)
            ORDER BY
                observations.run_id ASC,
                observations.observed_at ASC,
                observations.listing_id ASC
            """
        )
        current_run_id: str | None = None
        current_rows: list[dict[str, object]] = []
        chunk_index = 0
        for row in cursor:
            hydrated = _hydrate_observation_row(row)
            run_id = str(hydrated["run_id"])
            if current_run_id is None:
                current_run_id = run_id
            if run_id != current_run_id or len(current_rows) >= batch_size:
                yield self._prepare_observation_batch(current_run_id, current_rows, chunk_index=chunk_index)
                if run_id != current_run_id:
                    current_run_id = run_id
                    current_rows = []
                    chunk_index = 0
                else:
                    current_rows = []
                    chunk_index += 1
            current_rows.append(hydrated)
        if current_run_id is not None and current_rows:
            yield self._prepare_observation_batch(current_run_id, current_rows, chunk_index=chunk_index)

    def _prepare_observation_batch(
        self,
        run_id: str,
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
    ) -> _PreparedBatch:
        first = rows[0]
        group_key = f"run_id={run_id}/chunk={chunk_index}"
        batch_event = EventEnvelope.create(
            schema_version=self.config.schema_versions.events,
            event_type="vinted.backfill.observation.batch",
            aggregate_type="discovery-run",
            aggregate_id=run_id,
            occurred_at=str(first["observed_at"]),
            producer="vinted_radar.services.full_backfill",
            partition_key=first.get("root_catalog_id") or run_id,
            payload={
                "run_id": run_id,
                "chunk_index": chunk_index,
                "row_count": len(rows),
                "listing_ids": [int(row["listing_id"]) for row in rows],
            },
            metadata={
                "capture_source": "sqlite_backfill",
                "root_titles": sorted({str(row["root_title"]) for row in rows if row.get("root_title")}),
            },
            identity={
                "capture_source": "sqlite_backfill",
                "run_id": run_id,
                "chunk_index": chunk_index,
                "observed_at": first["observed_at"],
            },
        )
        return _PreparedBatch(
            dataset="observations",
            group_key=group_key,
            rows=tuple(dict(row) for row in rows),
            batch_event=batch_event,
            publish_clickhouse=False,
            manifest_metadata={
                "run_id": run_id,
                "chunk_index": chunk_index,
                "first_observed_at": rows[0].get("observed_at"),
                "last_observed_at": rows[-1].get("observed_at"),
            },
        )

    def _iter_probe_batches(
        self,
        source: RadarRepository,
        *,
        batch_size: int,
        reference_now: str,
    ) -> Iterator[_PreparedBatch]:
        cursor = source.connection.execute(
            """
            SELECT
                probes.probe_id,
                probes.listing_id,
                probes.probed_at,
                probes.requested_url,
                probes.final_url,
                probes.response_status,
                probes.probe_outcome,
                probes.detail_json,
                probes.error_message,
                listings.title AS listing_title,
                listings.brand AS listing_brand,
                listings.condition_label AS listing_condition_label,
                listings.price_amount_cents AS listing_price_amount_cents,
                listings.price_currency AS listing_price_currency,
                listings.total_price_amount_cents AS listing_total_price_amount_cents,
                listings.total_price_currency AS listing_total_price_currency,
                listings.favourite_count AS listing_favourite_count,
                listings.view_count AS listing_view_count,
                listings.primary_catalog_id AS listing_primary_catalog_id,
                listings.primary_root_catalog_id AS listing_primary_root_catalog_id,
                primary_catalog.title AS primary_catalog_title,
                primary_catalog.path AS primary_catalog_path,
                resolved_root.title AS resolved_root_title
            FROM item_page_probes AS probes
            LEFT JOIN listings ON listings.listing_id = probes.listing_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN catalogs AS resolved_root ON resolved_root.catalog_id = listings.primary_root_catalog_id
            ORDER BY
                substr(probes.probed_at, 1, 10) ASC,
                probes.probed_at ASC,
                probes.probe_id ASC
            """
        )
        current_day: str | None = None
        current_rows: list[dict[str, object]] = []
        chunk_index = 0
        for row in cursor:
            hydrated = _hydrate_probe_row(row)
            hydrated["reference_now"] = reference_now
            hydrated["reason"] = _optional_str((hydrated.get("detail") or {}).get("reason"))
            hydrated["primary_catalog_id"] = _optional_int(row["listing_primary_catalog_id"])
            hydrated["primary_root_catalog_id"] = _optional_int(row["listing_primary_root_catalog_id"])
            hydrated["root_title"] = _optional_str(row["resolved_root_title"])
            hydrated["category_path"] = _optional_str(row["primary_catalog_path"])
            hydrated["brand"] = _optional_str(row["listing_brand"])
            hydrated["condition_label"] = _optional_str(row["listing_condition_label"])
            hydrated["price_amount_cents"] = _optional_int(row["listing_price_amount_cents"])
            hydrated["price_currency"] = _optional_str(row["listing_price_currency"])
            hydrated["total_price_amount_cents"] = _optional_int(row["listing_total_price_amount_cents"])
            hydrated["total_price_currency"] = _optional_str(row["listing_total_price_currency"])
            hydrated["favourite_count"] = _optional_int(row["listing_favourite_count"])
            hydrated["view_count"] = _optional_int(row["listing_view_count"])
            probed_on = str(hydrated["probed_at"])[:10]
            if current_day is None:
                current_day = probed_on
            if probed_on != current_day or len(current_rows) >= batch_size:
                yield self._prepare_probe_batch(current_day, current_rows, chunk_index=chunk_index)
                if probed_on != current_day:
                    current_day = probed_on
                    current_rows = []
                    chunk_index = 0
                else:
                    current_rows = []
                    chunk_index += 1
            current_rows.append(hydrated)
        if current_day is not None and current_rows:
            yield self._prepare_probe_batch(current_day, current_rows, chunk_index=chunk_index)

    def _prepare_probe_batch(
        self,
        probed_on: str,
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
    ) -> _PreparedBatch:
        first = rows[0]
        group_key = f"probed_on={probed_on}/chunk={chunk_index}"
        batch_event = EventEnvelope.create(
            schema_version=self.config.schema_versions.events,
            event_type="vinted.state-refresh.probe.batch",
            aggregate_type="state-refresh",
            aggregate_id=f"probe-day:{probed_on}",
            occurred_at=str(first["probed_at"]),
            producer="vinted_radar.services.full_backfill",
            partition_key=first.get("listing_id") or probed_on,
            payload={
                "reference_now": first.get("reference_now"),
                "probed_on": probed_on,
                "chunk_index": chunk_index,
                "row_count": len(rows),
                "probed_listing_ids": [int(row["listing_id"]) for row in rows],
            },
            metadata={
                "capture_source": "sqlite_backfill",
                "mode": "historical",
            },
            identity={
                "capture_source": "sqlite_backfill",
                "probed_on": probed_on,
                "chunk_index": chunk_index,
                "first_probed_at": first["probed_at"],
            },
        )
        return _PreparedBatch(
            dataset="probes",
            group_key=group_key,
            rows=tuple(dict(row) for row in rows),
            batch_event=batch_event,
            publish_clickhouse=True,
            manifest_metadata={
                "probed_on": probed_on,
                "chunk_index": chunk_index,
                "reference_now": first.get("reference_now"),
                "first_probed_at": rows[0].get("probed_at"),
                "last_probed_at": rows[-1].get("probed_at"),
            },
        )

    def _iter_runtime_cycle_batches(self, source: RadarRepository, *, batch_size: int) -> Iterator[_PreparedBatch]:
        rows = [
            _hydrate_runtime_cycle_row(dict(row))
            for row in source.connection.execute(
                "SELECT * FROM runtime_cycles ORDER BY started_at ASC, cycle_id ASC"
            ).fetchall()
        ]
        if not rows:
            return
        current_started_on: str | None = None
        current_rows: list[dict[str, object]] = []
        chunk_index = 0
        for row in rows:
            started_on = str(row["started_at"])[:10]
            if current_started_on is None:
                current_started_on = started_on
            if started_on != current_started_on or len(current_rows) >= batch_size:
                yield self._prepare_runtime_cycle_batch(current_started_on, current_rows, chunk_index=chunk_index)
                if started_on != current_started_on:
                    current_started_on = started_on
                    current_rows = []
                    chunk_index = 0
                else:
                    current_rows = []
                    chunk_index += 1
            current_rows.append(row)
        if current_started_on is not None and current_rows:
            yield self._prepare_runtime_cycle_batch(current_started_on, current_rows, chunk_index=chunk_index)

    def _prepare_runtime_cycle_batch(
        self,
        started_on: str,
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
    ) -> _PreparedBatch:
        first = rows[0]
        group_key = f"started_on={started_on}/chunk={chunk_index}"
        batch_event = EventEnvelope.create(
            schema_version=self.config.schema_versions.events,
            event_type="vinted.backfill.runtime-cycle.batch",
            aggregate_type="runtime-cycle-day",
            aggregate_id=started_on,
            occurred_at=str(first["started_at"]),
            producer="vinted_radar.services.full_backfill",
            partition_key=first.get("cycle_id") or started_on,
            payload={
                "started_on": started_on,
                "chunk_index": chunk_index,
                "row_count": len(rows),
                "cycle_ids": [str(row["cycle_id"]) for row in rows],
            },
            metadata={
                "capture_source": "sqlite_backfill",
            },
            identity={
                "capture_source": "sqlite_backfill",
                "started_on": started_on,
                "chunk_index": chunk_index,
                "first_cycle_id": first["cycle_id"],
            },
        )
        return _PreparedBatch(
            dataset="runtime-cycles",
            group_key=group_key,
            rows=tuple(dict(row) for row in rows),
            batch_event=batch_event,
            publish_clickhouse=False,
            manifest_metadata={
                "started_on": started_on,
                "chunk_index": chunk_index,
                "first_cycle_id": rows[0].get("cycle_id"),
                "last_cycle_id": rows[-1].get("cycle_id"),
            },
        )

    def _iter_runtime_controller_batches(
        self,
        source: RadarRepository,
        *,
        reference_now: str,
    ) -> Iterator[_PreparedBatch]:
        controller = source.runtime_controller_state(now=reference_now)
        if controller is None:
            return
        row = dict(controller)
        row["reference_now"] = reference_now
        group_key = "controller_id=1"
        batch_event = EventEnvelope.create(
            schema_version=self.config.schema_versions.events,
            event_type="vinted.backfill.runtime-controller.batch",
            aggregate_type="runtime-controller",
            aggregate_id="1",
            occurred_at=str(row.get("updated_at") or reference_now),
            producer="vinted_radar.services.full_backfill",
            partition_key="runtime-controller",
            payload={
                "controller_id": 1,
                "row_count": 1,
                "reference_now": reference_now,
            },
            metadata={
                "capture_source": "sqlite_backfill",
            },
            identity={
                "capture_source": "sqlite_backfill",
                "updated_at": row.get("updated_at"),
                "reference_now": reference_now,
            },
        )
        yield _PreparedBatch(
            dataset="runtime-controller",
            group_key=group_key,
            rows=(row,),
            batch_event=batch_event,
            publish_clickhouse=False,
            manifest_metadata={
                "controller_id": 1,
                "reference_now": reference_now,
                "updated_at": row.get("updated_at"),
            },
        )

    def _current_checkpoint_mutation_target(self) -> dict[str, object]:
        if not hasattr(self, "_checkpoint_state"):
            self._checkpoint_state = {}
        clickhouse = self._checkpoint_state.get("clickhouse")
        if not isinstance(clickhouse, dict):
            clickhouse = {}
            self._checkpoint_state["clickhouse"] = clickhouse
        return clickhouse

    def _write_checkpoint(self, checkpoint_path: Path | None, checkpoint: dict[str, object]) -> None:
        if checkpoint_path is None:
            return
        checkpoint["updated_at"] = _utc_now()
        self._checkpoint_state = checkpoint
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", delete=False, dir=str(checkpoint_path.parent), encoding="utf-8") as handle:
            json.dump(checkpoint, handle, ensure_ascii=False, indent=2, sort_keys=True)
            temp_path = Path(handle.name)
        temp_path.replace(checkpoint_path)


def run_full_backfill(
    sqlite_db_path: str | Path,
    *,
    config: PlatformConfig | None = None,
    reference_now: str | None = None,
    batch_size: int = 500,
    dry_run: bool = False,
    sync_runtime_control: bool = True,
    checkpoint_path: str | Path | None = None,
    reset_checkpoint: bool = False,
    clickhouse_lease_seconds: int = 60,
    repository: PostgresMutableTruthRepository | object | None = None,
    outbox: PostgresOutbox | None = None,
    lake_writer: ParquetLakeWriter | None = None,
    clickhouse_ingest: ClickHouseIngestService | None = None,
    postgres_connection: object | None = None,
    object_store_client: object | None = None,
    clickhouse_client: object | None = None,
) -> FullBackfillReport:
    service = FullBackfillService(
        sqlite_db_path,
        config=config,
        reference_now=reference_now,
        repository=repository,
        outbox=outbox,
        lake_writer=lake_writer,
        clickhouse_ingest=clickhouse_ingest,
        postgres_connection=postgres_connection,
        object_store_client=object_store_client,
        clickhouse_client=clickhouse_client,
    )
    try:
        return service.run(
            batch_size=batch_size,
            dry_run=dry_run,
            sync_runtime_control=sync_runtime_control,
            checkpoint_path=checkpoint_path,
            reset_checkpoint=reset_checkpoint,
            clickhouse_lease_seconds=clickhouse_lease_seconds,
        )
    finally:
        service.close()


def _default_checkpoint(
    *,
    sqlite_db_path: Path,
    reference_now: str,
    sync_runtime_control: bool,
) -> dict[str, object]:
    return {
        "version": _FULL_BACKFILL_CHECKPOINT_VERSION,
        "sqlite_db_path": str(sqlite_db_path),
        "reference_now": reference_now,
        "sync_runtime_control": sync_runtime_control,
        "updated_at": None,
        "completed": False,
        "postgres_backfill": {
            "completed": False,
            "report": None,
        },
        "datasets": {},
        "clickhouse": {
            "claimed_count": 0,
            "processed_count": 0,
            "skipped_count": 0,
        },
    }


def _dataset_state(checkpoint: dict[str, object], dataset: str) -> dict[str, object]:
    datasets = checkpoint.setdefault("datasets", {})
    assert isinstance(datasets, dict)
    state = datasets.get(dataset)
    if isinstance(state, dict):
        return state
    state = {
        "completed_batches": 0,
        "completed_rows": 0,
        "last_group_key": None,
        "last_event_id": None,
        "last_manifest_id": None,
    }
    datasets[dataset] = state
    return state


def _load_checkpoint(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Full backfill checkpoint {path} must decode to an object.")
    return payload


def _validate_checkpoint(
    *,
    checkpoint: Mapping[str, object],
    sqlite_db_path: Path,
    reference_now: str,
    sync_runtime_control: bool,
) -> None:
    if int(checkpoint.get("version") or 0) != _FULL_BACKFILL_CHECKPOINT_VERSION:
        raise ValueError("Checkpoint schema version does not match the current full backfill service.")
    if str(checkpoint.get("sqlite_db_path") or "") != str(sqlite_db_path):
        raise ValueError("Checkpoint was created for a different SQLite source path. Use --reset-checkpoint to restart.")
    if str(checkpoint.get("reference_now") or "") != reference_now:
        raise ValueError("Checkpoint was created with a different --now value. Use --reset-checkpoint to restart.")
    if bool(checkpoint.get("sync_runtime_control")) != bool(sync_runtime_control):
        raise ValueError("Checkpoint runtime-control mode does not match the current command. Use --reset-checkpoint to restart.")


def _manifest_type(dataset: str) -> str:
    return {
        "discoveries": "sqlite-discovery-evidence-batch",
        "observations": "sqlite-observation-evidence-batch",
        "probes": "sqlite-probe-evidence-batch",
        "runtime-cycles": "sqlite-runtime-cycle-evidence-batch",
        "runtime-controller": "sqlite-runtime-controller-evidence-batch",
    }[dataset]


def _hydrate_runtime_cycle_row(row: Mapping[str, object]) -> dict[str, object]:
    record = dict(row)
    record["state_refresh_summary"] = _load_json_object(record.pop("state_refresh_summary_json", "{}"))
    record["config"] = _load_json_object(record.pop("config_json", "{}"))
    return record


def _load_json_object(value: object) -> dict[str, object]:
    if value in {None, ""}:
        return {}
    decoded = json.loads(str(value))
    if not isinstance(decoded, dict):
        raise ValueError("Expected JSON object payload.")
    return {str(key): decoded[key] for key in decoded}


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


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


__all__ = [
    "FullBackfillDatasetReport",
    "FullBackfillReport",
    "FullBackfillService",
    "run_full_backfill",
]
