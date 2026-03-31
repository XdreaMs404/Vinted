from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from wsgiref.util import setup_testing_defaults

from typer.testing import CliRunner

from tests.platform_test_fakes import FakePostgresConnection, FakeS3Client
from tests.test_full_backfill import (
    ConstantNow,
    RecordingClickHouseClient,
    SpyMutableTruthRepository,
    _build_config,
    _build_writer,
    _seed_source_db,
)
from vinted_radar.cli import app
from vinted_radar.dashboard import DashboardApplication, build_runtime_payload
from vinted_radar.platform.clickhouse_ingest import ClickHouseIngestService
from vinted_radar.platform.health import render_platform_report_text, summarize_cutover_state
from vinted_radar.platform.outbox import PostgresOutbox
from vinted_radar.repository import RadarRepository
from vinted_radar.services.full_backfill import run_full_backfill
from vinted_radar.services.reconciliation import (
    DatasetReconciliation,
    DatasetStoreSnapshot,
    ReconciliationReport,
    ReconciliationSection,
    run_reconciliation,
)


class ReconciliationMutableTruthRepository(SpyMutableTruthRepository):
    def reconciliation_table_snapshot(
        self,
        *,
        table_name: str,
        start_column: str | None = None,
        end_column: str | None = None,
    ) -> dict[str, object]:
        rows: list[dict[str, object]]
        if table_name == "platform_discovery_runs":
            rows = list(self.discovery_runs.values())
        elif table_name == "platform_catalogs":
            rows = list(self.catalogs.values())
        elif table_name == "platform_listing_identity":
            rows = list(self.listing_identities.values())
        elif table_name == "platform_listing_presence_summary":
            rows = list(self.listing_presence_summaries.values())
        elif table_name == "platform_listing_current_state":
            rows = list(self.listing_current_states.values())
        elif table_name == "platform_runtime_cycles":
            rows = [dict(cycle) for cycle, _event_id in self.runtime_cycles]
        elif table_name == "platform_runtime_controller_state":
            rows = [] if not self.runtime_controllers else [dict(self.runtime_controllers[-1][0])]
        else:
            raise AssertionError(f"Unexpected table name: {table_name}")
        return _snapshot_rows(rows, start_column=start_column, end_column=end_column)


class FakeRuntimeBackend:
    def __init__(self, *, db_path: str | Path = "runtime.db") -> None:
        self.db_path = Path(db_path)

    def runtime_status(self, *, limit: int, now: str | None = None) -> dict[str, object]:
        return {
            "generated_at": now or "2026-03-23T09:10:00+00:00",
            "db_path": str(self.db_path),
            "controller": {"status": "paused", "phase": "paused", "mode": "continuous"},
            "status": "paused",
            "phase": "paused",
            "mode": "continuous",
            "updated_at": "2026-03-23T09:05:00+00:00",
            "paused_at": "2026-03-23T09:00:00+00:00",
            "next_resume_at": "2026-03-23T09:15:00+00:00",
            "elapsed_pause_seconds": 600.0,
            "next_resume_in_seconds": 300.0,
            "last_error": None,
            "last_error_at": None,
            "requested_action": "none",
            "requested_at": None,
            "active_cycle_id": None,
            "latest_cycle_id": "cycle-polyglot-1",
            "heartbeat": {"age_seconds": 10.0, "stale_after_seconds": 120.0, "is_stale": False},
            "latest_cycle": {
                "cycle_id": "cycle-polyglot-1",
                "mode": "continuous",
                "status": "completed",
                "phase": "completed",
                "started_at": "2026-03-23T09:00:00+00:00",
                "finished_at": "2026-03-23T09:05:00+00:00",
                "discovery_run_id": "run-polyglot-1",
                "state_probed_count": 1,
                "state_probe_limit": 2,
                "tracked_listings": 2,
                "first_pass_only": 1,
                "fresh_followup": 1,
                "aging_followup": 0,
                "stale_followup": 0,
                "state_refresh_summary": {
                    "status": "healthy",
                    "direct_signal_count": 1,
                    "inconclusive_probe_count": 0,
                    "degraded_probe_count": 0,
                },
            },
            "recent_cycles": [],
            "latest_failure": None,
            "recent_failures": [],
            "acquisition": {
                "status": "healthy",
                "latest_state_refresh_summary": {"status": "healthy"},
                "reasons": [],
            },
            "totals": {
                "total_cycles": 1,
                "completed_cycles": 1,
                "failed_cycles": 0,
                "running_cycles": 0,
                "interrupted_cycles": 0,
            },
        }

    def coverage_summary(self):
        return {"has_run": True}

    def overview_snapshot(self, *, now: str | None = None) -> dict[str, object]:
        return {"summary": {"inventory": {"tracked_listings": 2}}}


def _snapshot_rows(
    rows: list[dict[str, object]],
    *,
    start_column: str | None,
    end_column: str | None,
) -> dict[str, object]:
    starts = [str(row[start_column]) for row in rows if start_column is not None and row.get(start_column)]
    ends = [str(row[end_column]) for row in rows if end_column is not None and row.get(end_column)]
    return {
        "row_count": len(rows),
        "window_start": None if not starts else min(starts),
        "window_end": None if not ends else max(ends),
    }


def _cutover_config(*, postgres: bool, clickhouse: bool, object_storage: bool, polyglot_reads: bool):
    return SimpleNamespace(
        postgres=SimpleNamespace(dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"),
        cutover=SimpleNamespace(
            enable_postgres_writes=postgres,
            enable_clickhouse_writes=clickhouse,
            enable_object_storage_writes=object_storage,
            enable_polyglot_reads=polyglot_reads,
        ),
    )


def _make_reconciliation_report() -> ReconciliationReport:
    expected = DatasetStoreSnapshot(
        row_count=2,
        window_start="2026-03-20T10:05:00+00:00",
        window_end="2026-03-20T10:05:05+00:00",
    )
    actual = DatasetStoreSnapshot(
        row_count=2,
        window_start="2026-03-20T10:05:00+00:00",
        window_end="2026-03-20T10:05:05+00:00",
        batch_count=2,
    )
    dataset = DatasetReconciliation(
        dataset="discoveries",
        expected=expected,
        actual=actual,
        count_status="match",
        window_status="match",
        status="match",
    )
    return ReconciliationReport(
        sqlite_db_path="data/vinted-radar.db",
        postgres_dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar",
        clickhouse_url="http://127.0.0.1:8123",
        clickhouse_database="vinted_radar",
        object_store_bucket="vinted-radar-test",
        generated_at="2026-03-21T00:00:00+00:00",
        cutover=summarize_cutover_state(
            _cutover_config(postgres=True, clickhouse=True, object_storage=True, polyglot_reads=False)
        ),
        postgres=ReconciliationSection(store="postgres", status="match", datasets=(dataset,)),
        clickhouse=ReconciliationSection(store="clickhouse", status="match", datasets=(dataset,)),
        object_storage=ReconciliationSection(store="object-storage", status="match", datasets=(dataset,)),
        overall_status="match",
    )


def _call_app(app_instance: DashboardApplication, path: str) -> tuple[str, bytes, dict[str, str]]:
    environ: dict[str, str] = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    environ["QUERY_STRING"] = ""
    captured: dict[str, str] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        for key, value in headers:
            captured[key] = value

    body = b"".join(app_instance(environ, start_response))
    return captured["status"], body, captured


def test_run_reconciliation_matches_backfilled_postgres_clickhouse_and_object_storage(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_source_db(db_path)
    config = _build_config()
    repository = ReconciliationMutableTruthRepository()
    postgres_connection = FakePostgresConnection()
    outbox = PostgresOutbox(postgres_connection)
    s3_client = FakeS3Client()
    writer = _build_writer(s3_client)
    clickhouse_client = RecordingClickHouseClient()
    clickhouse_ingest = ClickHouseIngestService(
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_client=clickhouse_client,
        database=config.clickhouse.database,
        now_provider=ConstantNow("2026-03-20T10:09:00+00:00"),
    )

    run_full_backfill(
        db_path,
        config=config,
        reference_now="2026-03-21T00:00:00+00:00",
        batch_size=1,
        checkpoint_path=tmp_path / "full-backfill-checkpoint.json",
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_ingest=clickhouse_ingest,
    )

    report = run_reconciliation(
        db_path,
        config=config,
        reference_now="2026-03-21T00:00:00+00:00",
        repository=repository,
        lake_writer=writer,
        clickhouse_client=clickhouse_client,
    )

    assert report.ok is True
    assert report.overall_status == "match"
    assert report.cutover.mode == "sqlite-primary"
    assert report.postgres.status == "match"
    assert report.clickhouse.status == "match"
    assert report.object_storage.status == "match"

    postgres_datasets = {dataset.dataset: dataset for dataset in report.postgres.datasets}
    clickhouse_datasets = {dataset.dataset: dataset for dataset in report.clickhouse.datasets}
    object_datasets = {dataset.dataset: dataset for dataset in report.object_storage.datasets}

    assert postgres_datasets["listing_identity"].actual.row_count == 2
    assert clickhouse_datasets["listing_probe_facts"].actual.row_count == 1
    assert object_datasets["discoveries"].actual.row_count == 2
    assert object_datasets["discoveries"].actual.batch_count == 2
    assert object_datasets["runtime-cycles"].actual.row_count == 1


def test_platform_reconcile_cli_emits_json_and_forwards_options(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    fake_config = _cutover_config(postgres=True, clickhouse=True, object_storage=True, polyglot_reads=False)
    fake_report = _make_reconciliation_report()

    def fake_run_reconciliation(db, *, config, reference_now=None, **_kwargs):
        captured["db"] = str(db)
        captured["config"] = config
        captured["reference_now"] = reference_now
        return fake_report

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    monkeypatch.setattr("vinted_radar.cli.run_reconciliation", fake_run_reconciliation)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "platform-reconcile",
            "--db",
            str(tmp_path / "source.db"),
            "--now",
            "2026-03-21T00:00:00+00:00",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "match"
    assert payload["cutover"]["mode"] == "dual-write-shadow"
    assert payload["object_storage"]["datasets"][0]["actual"]["batch_count"] == 2
    assert captured["db"] == str(tmp_path / "source.db")
    assert captured["config"] is fake_config
    assert captured["reference_now"] == "2026-03-21T00:00:00+00:00"


def test_platform_report_and_runtime_cli_surface_explicit_cutover_state(monkeypatch, tmp_path: Path) -> None:
    report = SimpleNamespace(
        mode="doctor",
        ok=True,
        check_writes=False,
        config={
            "postgres": {"dsn": "postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"},
            "clickhouse": {"url": "http://127.0.0.1:8123", "database": "vinted_radar"},
            "object_storage": {"endpoint_url": "http://127.0.0.1:9000", "bucket": "vinted-radar-test"},
            "cutover": {
                "enable_postgres_writes": False,
                "enable_clickhouse_writes": True,
                "enable_object_storage_writes": False,
                "enable_polyglot_reads": True,
            },
        },
        postgres=SimpleNamespace(
            ok=True,
            endpoint="postgresql://127.0.0.1:5432/vinted_radar",
            migration_dir="postgres",
            expected_version=3,
            current_version=3,
            available_version=3,
            applied_this_run=(),
            pending_versions=(),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail="ok",
            error=None,
        ),
        clickhouse=SimpleNamespace(
            ok=True,
            endpoint="http://127.0.0.1:8123",
            migration_dir="clickhouse",
            expected_version=2,
            current_version=2,
            available_version=2,
            applied_this_run=(),
            pending_versions=(),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail="ok",
            error=None,
        ),
        object_storage=SimpleNamespace(
            ok=True,
            endpoint_url="http://127.0.0.1:9000",
            bucket="vinted-radar-test",
            region="us-east-1",
            bucket_exists=True,
            bucket_created=False,
            prefixes={"raw_events": "tenant/events/raw", "manifests": "tenant/manifests", "parquet": "tenant/parquet"},
            ensured_marker_keys=(),
            write_checked_prefixes=(),
            detail="ok",
            error=None,
        ),
    )
    rendered = render_platform_report_text(report)
    assert "Cutover state:" in rendered
    assert "- mode: polyglot-cutover" in rendered
    assert "- warnings: ClickHouse writes are enabled without PostgreSQL writes" in rendered

    db_path = tmp_path / "runtime.db"
    with RadarRepository(db_path) as repository:
        cycle_id = repository.start_runtime_cycle(
            mode="batch",
            phase="starting",
            interval_seconds=None,
            state_probe_limit=2,
            config={"state_refresh_limit": 2},
        )
        repository.complete_runtime_cycle(
            cycle_id,
            status="completed",
            phase="completed",
            discovery_run_id=None,
            state_probed_count=1,
            tracked_listings=2,
            freshness_counts={
                "first-pass-only": 1,
                "fresh-followup": 1,
                "aging-followup": 0,
                "stale-followup": 0,
            },
            last_error=None,
            state_refresh_summary={
                "status": "healthy",
                "direct_signal_count": 1,
                "inconclusive_probe_count": 0,
                "degraded_probe_count": 0,
            },
        )

    fake_config = _cutover_config(postgres=True, clickhouse=True, object_storage=True, polyglot_reads=False)
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    runner = CliRunner()
    result = runner.invoke(app, ["runtime-status", "--db", str(db_path)])

    assert result.exit_code == 0
    assert "Cutover mode: dual-write-shadow" in result.stdout
    assert "Cutover read path: sqlite" in result.stdout
    assert "Cutover write targets: sqlite, postgres, clickhouse, object-storage" in result.stdout


def test_runtime_payload_and_dashboard_health_include_cutover_snapshot(monkeypatch, tmp_path: Path) -> None:
    fake_config = _cutover_config(postgres=True, clickhouse=True, object_storage=True, polyglot_reads=True)
    backend = FakeRuntimeBackend(db_path=tmp_path / "runtime.db")

    monkeypatch.setattr("vinted_radar.dashboard.load_platform_config", lambda: fake_config)

    payload = build_runtime_payload(backend, now="2026-03-23T09:10:00+00:00")
    assert payload["cutover"]["mode"] == "polyglot-cutover"
    assert payload["summary"]["cutover_mode"] == "polyglot-cutover"
    assert payload["summary"]["cutover_read_path"] == "polyglot-platform"
    assert payload["summary"]["cutover_write_targets"] == ["sqlite", "postgres", "clickhouse", "object-storage"]

    app_instance = DashboardApplication(
        tmp_path / "dashboard.db",
        now="2026-03-23T09:10:00+00:00",
        query_backend_factory=lambda _repository: backend,
    )

    runtime_status, runtime_body, runtime_headers = _call_app(app_instance, "/api/runtime")
    health_status, health_body, health_headers = _call_app(app_instance, "/health")

    assert runtime_status == "200 OK"
    assert runtime_headers["Content-Type"].startswith("application/json")
    runtime_payload = json.loads(runtime_body)
    assert runtime_payload["cutover"]["mode"] == "polyglot-cutover"
    assert runtime_payload["cutover"]["read_path"] == "polyglot-platform"

    assert health_status == "200 OK"
    assert health_headers["Content-Type"].startswith("application/json")
    health_payload = json.loads(health_body)
    assert health_payload["cutover"]["mode"] == "polyglot-cutover"
    assert health_payload["cutover"]["dual_write_active"] is True
    assert health_payload["tracked_listings"] == 2
