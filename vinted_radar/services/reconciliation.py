from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from vinted_radar.domain.manifests import EvidenceManifest
from vinted_radar.platform.config import PlatformConfig, load_platform_config, redact_url_credentials
from vinted_radar.platform.health import CutoverStatusSnapshot, summarize_cutover_state
from vinted_radar.platform.lake_writer import ParquetLakeWriter
from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository
from vinted_radar.repository import RadarRepository

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_POSTGRES_DATASET_SPECS = (
    {
        "dataset": "discovery_runs",
        "source_key": "discovery_runs",
        "table_name": "platform_discovery_runs",
        "start_column": "started_at",
        "end_column": "started_at",
        "notes": (),
    },
    {
        "dataset": "catalogs",
        "source_key": "catalogs",
        "table_name": "platform_catalogs",
        "start_column": "synced_at",
        "end_column": "synced_at",
        "notes": (),
    },
    {
        "dataset": "listing_identity",
        "source_key": "listing_state",
        "table_name": "platform_listing_identity",
        "start_column": "first_seen_at",
        "end_column": "last_seen_at",
        "notes": (),
    },
    {
        "dataset": "listing_presence_summary",
        "source_key": "listing_state",
        "table_name": "platform_listing_presence_summary",
        "start_column": "first_seen_at",
        "end_column": "last_seen_at",
        "notes": (),
    },
    {
        "dataset": "listing_current_state",
        "source_key": "listing_state",
        "table_name": "platform_listing_current_state",
        "start_column": None,
        "end_column": None,
        "notes": (
            "Current-state rows reconcile by cardinality; projection timestamps are derivation time rather than the raw SQLite history window.",
        ),
    },
    {
        "dataset": "runtime_cycles",
        "source_key": "runtime_cycles",
        "table_name": "platform_runtime_cycles",
        "start_column": "started_at",
        "end_column": "started_at",
        "notes": (),
    },
    {
        "dataset": "runtime_controller",
        "source_key": "runtime_controller",
        "table_name": "platform_runtime_controller_state",
        "start_column": "updated_at",
        "end_column": "updated_at",
        "notes": (),
    },
)

_CLICKHOUSE_DATASET_SPECS = (
    {
        "dataset": "listing_seen_facts",
        "source_key": "discoveries",
        "table_name": "fact_listing_seen_events",
        "time_column": "observed_at",
    },
    {
        "dataset": "listing_probe_facts",
        "source_key": "probes",
        "table_name": "fact_listing_probe_events",
        "time_column": "probed_at",
    },
)

_OBJECT_STORAGE_DATASET_SPECS = (
    {
        "dataset": "discoveries",
        "source_key": "discoveries",
        "time_field": "observed_at",
    },
    {
        "dataset": "observations",
        "source_key": "observations",
        "time_field": "observed_at",
    },
    {
        "dataset": "probes",
        "source_key": "probes",
        "time_field": "probed_at",
    },
    {
        "dataset": "runtime-cycles",
        "source_key": "runtime_cycles",
        "time_field": "started_at",
    },
    {
        "dataset": "runtime-controller",
        "source_key": "runtime_controller",
        "time_field": "updated_at",
    },
)


@dataclass(frozen=True, slots=True)
class DatasetStoreSnapshot:
    row_count: int
    window_start: str | None
    window_end: str | None
    batch_count: int | None = None

    def as_dict(self) -> dict[str, object]:
        payload = {
            "row_count": self.row_count,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }
        if self.batch_count is not None:
            payload["batch_count"] = self.batch_count
        return payload


@dataclass(frozen=True, slots=True)
class DatasetReconciliation:
    dataset: str
    expected: DatasetStoreSnapshot
    actual: DatasetStoreSnapshot
    count_status: str
    window_status: str
    status: str
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset": self.dataset,
            "expected": self.expected.as_dict(),
            "actual": self.actual.as_dict(),
            "count_status": self.count_status,
            "window_status": self.window_status,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationSection:
    store: str
    status: str
    datasets: tuple[DatasetReconciliation, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "store": self.store,
            "status": self.status,
            "datasets": [dataset.as_dict() for dataset in self.datasets],
        }


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    sqlite_db_path: str
    postgres_dsn: str
    clickhouse_url: str
    clickhouse_database: str
    object_store_bucket: str
    generated_at: str
    cutover: CutoverStatusSnapshot
    postgres: ReconciliationSection
    clickhouse: ReconciliationSection
    object_storage: ReconciliationSection
    overall_status: str

    @property
    def ok(self) -> bool:
        return self.overall_status == "match"

    def as_dict(self) -> dict[str, object]:
        return {
            "sqlite_db_path": self.sqlite_db_path,
            "postgres_dsn": redact_url_credentials(self.postgres_dsn),
            "clickhouse_url": self.clickhouse_url,
            "clickhouse_database": self.clickhouse_database,
            "object_store_bucket": self.object_store_bucket,
            "generated_at": self.generated_at,
            "cutover": self.cutover.as_dict(),
            "postgres": self.postgres.as_dict(),
            "clickhouse": self.clickhouse.as_dict(),
            "object_storage": self.object_storage.as_dict(),
            "overall_status": self.overall_status,
            "ok": self.ok,
        }


class ReconciliationService:
    def __init__(
        self,
        sqlite_db_path: str | Path,
        *,
        config: PlatformConfig | None = None,
        reference_now: str | None = None,
        repository: PostgresMutableTruthRepository | object | None = None,
        lake_writer: ParquetLakeWriter | None = None,
        clickhouse_client: object | None = None,
        object_store_client: object | None = None,
    ) -> None:
        self.sqlite_db_path = Path(sqlite_db_path)
        self.config = load_platform_config() if config is None else config
        self.reference_now = reference_now
        self.repository = repository
        self.lake_writer = lake_writer
        self.clickhouse_client = clickhouse_client
        self._object_store_client = object_store_client
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

    def run(self) -> ReconciliationReport:
        self._ensure_runtime_dependencies()
        assert self.repository is not None
        assert self.lake_writer is not None
        assert self.clickhouse_client is not None

        sqlite_baselines = self._collect_sqlite_baselines()
        postgres_section = self._build_postgres_section(sqlite_baselines)
        clickhouse_section = self._build_clickhouse_section(sqlite_baselines)
        object_storage_section = self._build_object_storage_section(sqlite_baselines)
        overall_status = (
            "match"
            if all(section.status == "match" for section in (postgres_section, clickhouse_section, object_storage_section))
            else "mismatch"
        )
        return ReconciliationReport(
            sqlite_db_path=str(self.sqlite_db_path),
            postgres_dsn=self.config.postgres.dsn,
            clickhouse_url=self.config.clickhouse.url,
            clickhouse_database=self.config.clickhouse.database,
            object_store_bucket=self.config.object_storage.bucket,
            generated_at=_utc_now(),
            cutover=summarize_cutover_state(self.config),
            postgres=postgres_section,
            clickhouse=clickhouse_section,
            object_storage=object_storage_section,
            overall_status=overall_status,
        )

    def _ensure_runtime_dependencies(self) -> None:
        if self.repository is None:
            self.repository = PostgresMutableTruthRepository.from_dsn(self.config.postgres.dsn)
            self._owned_closeables.append(self.repository)
        if self.lake_writer is None:
            self.lake_writer = ParquetLakeWriter.from_config(self.config, client=self._object_store_client)
            if self._object_store_client is None:
                self._owned_closeables.append(self.lake_writer.object_store.client)
        if self.clickhouse_client is None:
            self.clickhouse_client = _get_clickhouse_client(self.config, database=self.config.clickhouse.database)
            self._owned_closeables.append(self.clickhouse_client)

    def _collect_sqlite_baselines(self) -> dict[str, DatasetStoreSnapshot]:
        reference_now = self.reference_now or _utc_now()
        with RadarRepository(self.sqlite_db_path) as source:
            listing_state_rows = source.listing_state_inputs(now=reference_now)
            runtime_controller = source.runtime_controller_state(now=reference_now)
            return {
                "discovery_runs": _query_generic_snapshot(
                    source.connection,
                    table_name="discovery_runs",
                    start_column="started_at",
                    end_column="started_at",
                ),
                "catalogs": _query_generic_snapshot(
                    source.connection,
                    table_name="catalogs",
                    start_column="synced_at",
                    end_column="synced_at",
                ),
                "listing_state": _snapshot_from_rows(
                    listing_state_rows,
                    start_field="first_seen_at",
                    end_field="last_seen_at",
                ),
                "runtime_cycles": _query_generic_snapshot(
                    source.connection,
                    table_name="runtime_cycles",
                    start_column="started_at",
                    end_column="started_at",
                ),
                "runtime_controller": _snapshot_from_optional_row(runtime_controller, time_field="updated_at"),
                "discoveries": _query_generic_snapshot(
                    source.connection,
                    table_name="listing_discoveries",
                    start_column="observed_at",
                    end_column="observed_at",
                ),
                "observations": _query_generic_snapshot(
                    source.connection,
                    table_name="listing_observations",
                    start_column="observed_at",
                    end_column="observed_at",
                ),
                "probes": _query_generic_snapshot(
                    source.connection,
                    table_name="item_page_probes",
                    start_column="probed_at",
                    end_column="probed_at",
                ),
            }

    def _build_postgres_section(self, sqlite_baselines: Mapping[str, DatasetStoreSnapshot]) -> ReconciliationSection:
        datasets = []
        for spec in _POSTGRES_DATASET_SPECS:
            expected = sqlite_baselines[spec["source_key"]]
            actual = self._postgres_table_snapshot(
                table_name=str(spec["table_name"]),
                start_column=_optional_str(spec.get("start_column")),
                end_column=_optional_str(spec.get("end_column")),
            )
            datasets.append(
                _build_dataset_reconciliation(
                    dataset=str(spec["dataset"]),
                    expected=expected,
                    actual=actual,
                    compare_window=spec.get("start_column") is not None,
                    notes=tuple(spec.get("notes") or ()),
                )
            )
        return _build_section(store="postgres", datasets=datasets)

    def _build_clickhouse_section(self, sqlite_baselines: Mapping[str, DatasetStoreSnapshot]) -> ReconciliationSection:
        datasets = []
        for spec in _CLICKHOUSE_DATASET_SPECS:
            datasets.append(
                _build_dataset_reconciliation(
                    dataset=str(spec["dataset"]),
                    expected=sqlite_baselines[str(spec["source_key"])],
                    actual=self._clickhouse_table_snapshot(
                        table_name=str(spec["table_name"]),
                        time_column=str(spec["time_column"]),
                    ),
                    compare_window=True,
                )
            )
        return _build_section(store="clickhouse", datasets=datasets)

    def _build_object_storage_section(self, sqlite_baselines: Mapping[str, DatasetStoreSnapshot]) -> ReconciliationSection:
        datasets = []
        for spec in _OBJECT_STORAGE_DATASET_SPECS:
            datasets.append(
                _build_dataset_reconciliation(
                    dataset=str(spec["dataset"]),
                    expected=sqlite_baselines[str(spec["source_key"])],
                    actual=self._object_storage_dataset_snapshot(
                        dataset=str(spec["dataset"]),
                        time_field=str(spec["time_field"]),
                    ),
                    compare_window=True,
                )
            )
        return _build_section(store="object-storage", datasets=datasets)

    def _postgres_table_snapshot(
        self,
        *,
        table_name: str,
        start_column: str | None,
        end_column: str | None,
    ) -> DatasetStoreSnapshot:
        resolver = getattr(self.repository, "reconciliation_table_snapshot", None)
        if callable(resolver):
            return _snapshot_from_mapping(
                resolver(table_name=table_name, start_column=start_column, end_column=end_column)
            )
        connection = getattr(self.repository, "connection", None)
        if connection is None:
            raise RuntimeError("Reconciliation repository is missing both a snapshot helper and a raw connection.")
        return _query_generic_snapshot(
            connection,
            table_name=table_name,
            start_column=start_column,
            end_column=end_column,
        )

    def _clickhouse_table_snapshot(self, *, table_name: str, time_column: str) -> DatasetStoreSnapshot:
        resolver = getattr(self.clickhouse_client, "reconciliation_table_snapshot", None)
        if callable(resolver):
            return _snapshot_from_mapping(
                resolver(table_name=table_name, time_column=time_column)
            )
        tables = getattr(self.clickhouse_client, "tables", None)
        if isinstance(tables, Mapping):
            rows = [dict(row) for row in list(tables.get(table_name, []) or []) if isinstance(row, Mapping)]
            return _snapshot_from_rows(rows, start_field=time_column, end_field=time_column)

        safe_table = _safe_identifier(table_name, field_name="ClickHouse table")
        safe_column = _safe_identifier(time_column, field_name="ClickHouse time column")
        sql = (
            f"SELECT COUNT(*) AS row_count, MIN({safe_column}) AS window_start, MAX({safe_column}) AS window_end "
            f"FROM {self.config.clickhouse.database}.{safe_table}"
        )
        result = self.clickhouse_client.query(sql)
        rows = getattr(result, "result_rows", ()) or ()
        first = None if not rows else rows[0]
        if first is None:
            return DatasetStoreSnapshot(row_count=0, window_start=None, window_end=None)
        return DatasetStoreSnapshot(
            row_count=int(_row_get(first, "row_count", 0) or 0),
            window_start=_normalize_timestamp(_row_get(first, "window_start", 1)),
            window_end=_normalize_timestamp(_row_get(first, "window_end", 2)),
        )

    def _object_storage_dataset_snapshot(self, *, dataset: str, time_field: str) -> DatasetStoreSnapshot:
        assert self.lake_writer is not None
        manifest_keys = self.lake_writer.object_store.list_keys(self.lake_writer.manifests_prefix)
        row_count = 0
        batch_count = 0
        window_start: str | None = None
        window_end: str | None = None

        for key in manifest_keys:
            if not key.endswith(".json"):
                continue
            manifest = EvidenceManifest.from_json(self.lake_writer.object_store.get_text(key))
            if str(manifest.metadata.get("capture_source") or "") != "sqlite_backfill":
                continue
            if str(manifest.metadata.get("legacy_dataset") or "") != dataset:
                continue
            parquet_entry = _manifest_entry(manifest, logical_name="parquet-batch")
            rows = self.lake_writer.read_rows(parquet_entry.object_key)
            batch_count += 1
            row_count += len(rows)
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                timestamp = _normalize_timestamp(row.get(time_field))
                if timestamp is None:
                    continue
                window_start = timestamp if window_start is None else min(window_start, timestamp)
                window_end = timestamp if window_end is None else max(window_end, timestamp)

        return DatasetStoreSnapshot(
            row_count=row_count,
            window_start=window_start,
            window_end=window_end,
            batch_count=batch_count,
        )


def run_reconciliation(
    sqlite_db_path: str | Path,
    *,
    config: PlatformConfig | None = None,
    reference_now: str | None = None,
    repository: PostgresMutableTruthRepository | object | None = None,
    lake_writer: ParquetLakeWriter | None = None,
    clickhouse_client: object | None = None,
    object_store_client: object | None = None,
) -> ReconciliationReport:
    service = ReconciliationService(
        sqlite_db_path,
        config=config,
        reference_now=reference_now,
        repository=repository,
        lake_writer=lake_writer,
        clickhouse_client=clickhouse_client,
        object_store_client=object_store_client,
    )
    try:
        return service.run()
    finally:
        service.close()


def _query_generic_snapshot(
    connection: object,
    *,
    table_name: str,
    start_column: str | None,
    end_column: str | None,
) -> DatasetStoreSnapshot:
    safe_table = _safe_identifier(table_name, field_name="table")
    safe_start = None if start_column is None else _safe_identifier(start_column, field_name="start column")
    safe_end = None if end_column is None else _safe_identifier(end_column, field_name="end column")
    select_clauses = ["COUNT(*) AS row_count"]
    select_clauses.append("NULL AS window_start" if safe_start is None else f"MIN({safe_start}) AS window_start")
    select_clauses.append("NULL AS window_end" if safe_end is None else f"MAX({safe_end}) AS window_end")
    row = _fetchone(connection.execute(f"SELECT {', '.join(select_clauses)} FROM {safe_table}"))
    if row is None:
        return DatasetStoreSnapshot(row_count=0, window_start=None, window_end=None)
    return DatasetStoreSnapshot(
        row_count=int(_row_get(row, "row_count", 0) or 0),
        window_start=_normalize_timestamp(_row_get(row, "window_start", 1)),
        window_end=_normalize_timestamp(_row_get(row, "window_end", 2)),
    )


def _snapshot_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    start_field: str,
    end_field: str,
    batch_count: int | None = None,
) -> DatasetStoreSnapshot:
    window_start: str | None = None
    window_end: str | None = None
    for row in rows:
        start = _normalize_timestamp(row.get(start_field))
        end = _normalize_timestamp(row.get(end_field))
        if start is not None:
            window_start = start if window_start is None else min(window_start, start)
        if end is not None:
            window_end = end if window_end is None else max(window_end, end)
    return DatasetStoreSnapshot(
        row_count=len(rows),
        window_start=window_start,
        window_end=window_end,
        batch_count=batch_count,
    )


def _snapshot_from_optional_row(row: Mapping[str, object] | None, *, time_field: str) -> DatasetStoreSnapshot:
    if row is None:
        return DatasetStoreSnapshot(row_count=0, window_start=None, window_end=None)
    timestamp = _normalize_timestamp(row.get(time_field))
    return DatasetStoreSnapshot(row_count=1, window_start=timestamp, window_end=timestamp)


def _snapshot_from_mapping(payload: Mapping[str, object]) -> DatasetStoreSnapshot:
    return DatasetStoreSnapshot(
        row_count=int(payload.get("row_count") or 0),
        window_start=_normalize_timestamp(payload.get("window_start")),
        window_end=_normalize_timestamp(payload.get("window_end")),
        batch_count=None if payload.get("batch_count") is None else int(payload.get("batch_count") or 0),
    )


def _build_dataset_reconciliation(
    *,
    dataset: str,
    expected: DatasetStoreSnapshot,
    actual: DatasetStoreSnapshot,
    compare_window: bool,
    notes: Sequence[str] = (),
) -> DatasetReconciliation:
    count_status = "match" if expected.row_count == actual.row_count else "mismatch"
    if not compare_window:
        window_status = "not-compared"
    elif all(
        value is None
        for value in (
            expected.window_start,
            expected.window_end,
            actual.window_start,
            actual.window_end,
        )
    ):
        window_status = "not-compared"
    else:
        window_status = (
            "match"
            if expected.window_start == actual.window_start and expected.window_end == actual.window_end
            else "mismatch"
        )
    status = "match" if count_status == "match" and window_status in {"match", "not-compared"} else "mismatch"
    return DatasetReconciliation(
        dataset=dataset,
        expected=expected,
        actual=actual,
        count_status=count_status,
        window_status=window_status,
        status=status,
        notes=tuple(str(note) for note in notes if str(note).strip()),
    )


def _build_section(*, store: str, datasets: Sequence[DatasetReconciliation]) -> ReconciliationSection:
    status = "match" if all(dataset.status == "match" for dataset in datasets) else "mismatch"
    return ReconciliationSection(store=store, status=status, datasets=tuple(datasets))


def _manifest_entry(manifest: EvidenceManifest, *, logical_name: str):
    for entry in manifest.entries:
        if entry.logical_name == logical_name:
            return entry
    raise RuntimeError(f"Manifest {manifest.manifest_id} does not contain the expected '{logical_name}' entry.")


def _fetchone(result: object) -> object | None:
    fetchone = getattr(result, "fetchone", None)
    return None if not callable(fetchone) else fetchone()


def _row_get(row: object, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
        return row[index]
    raise TypeError(f"Unsupported row type: {type(row).__name__}")


def _normalize_timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        candidate = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return candidate.astimezone(UTC).replace(microsecond=0).isoformat()
    candidate = str(value).strip()
    return None if not candidate else candidate.replace("Z", "+00:00")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _safe_identifier(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not _SAFE_IDENTIFIER_RE.fullmatch(candidate):
        raise ValueError(f"{field_name} must contain only letters, digits, and underscores")
    return candidate


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


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
    "DatasetReconciliation",
    "DatasetStoreSnapshot",
    "ReconciliationReport",
    "ReconciliationSection",
    "ReconciliationService",
    "run_reconciliation",
]
