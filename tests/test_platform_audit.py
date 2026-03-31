from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from wsgiref.util import setup_testing_defaults

from typer.testing import CliRunner

from tests.test_reconciliation import _cutover_config, _make_reconciliation_report
from vinted_radar.cli import app
from vinted_radar.dashboard import DashboardApplication, build_runtime_payload
from vinted_radar.services.lifecycle import (
    ClickHouseLifecycleSection,
    LifecycleReport,
    ObjectStorageLifecycleSection,
    PostgresLifecycleSection,
    StoragePostureSummary,
)
from vinted_radar.services.platform_audit import run_platform_audit


class _CheckpointRepository:
    def __init__(self) -> None:
        self._checkpoints = {
            ("postgres-current-state-projector", "postgres-current-state"): {
                "status": "idle",
                "last_event_id": "evt-current",
                "last_manifest_id": "manifest-current",
                "lag_seconds": 12.0,
                "last_error": None,
                "updated_at": "2026-03-31T11:00:00+00:00",
                "metadata": {"row_count": 2},
            },
            ("clickhouse-serving-ingest", "clickhouse"): {
                "status": "running",
                "last_event_id": "evt-analytical",
                "last_manifest_id": "manifest-analytical",
                "lag_seconds": 90.0,
                "last_error": None,
                "updated_at": "2026-03-31T11:00:00+00:00",
                "metadata": {"row_count": 2},
            },
        }

    def outbox_checkpoint(self, *, consumer_name: str, sink: str):
        payload = self._checkpoints.get((consumer_name, sink))
        return None if payload is None else dict(payload)


class _DummyWriter:
    object_store = SimpleNamespace(client=object())


class _RuntimeBackend:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def runtime_status(self, *, limit: int, now: str | None = None) -> dict[str, object]:
        return {
            "status": "scheduled",
            "phase": "waiting",
            "mode": "continuous",
            "updated_at": now or "2026-03-31T11:05:00+00:00",
            "paused_at": None,
            "next_resume_at": "2026-03-31T11:10:00+00:00",
            "elapsed_pause_seconds": None,
            "next_resume_in_seconds": 300.0,
            "last_error": None,
            "last_error_at": None,
            "requested_action": "none",
            "requested_at": None,
            "heartbeat": {"age_seconds": 5.0, "stale_after_seconds": 120.0, "is_stale": False},
            "active_cycle_id": None,
            "latest_cycle_id": "cycle-1",
            "controller": {"mode": "continuous"},
            "latest_cycle": {"cycle_id": "cycle-1", "mode": "continuous", "status": "completed", "phase": "completed"},
            "recent_cycles": [],
            "recent_failures": [],
            "acquisition": {"status": "healthy", "reasons": [], "latest_state_refresh_summary": {}},
            "totals": {"total_cycles": 1, "completed_cycles": 1, "failed_cycles": 0, "running_cycles": 0, "interrupted_cycles": 0},
        }

    def coverage_summary(self):
        return {"has_run": True}

    def overview_snapshot(self, *, now: str | None = None) -> dict[str, object]:
        return {"summary": {"inventory": {"tracked_listings": 2}}}


def _healthy_lifecycle_report() -> LifecycleReport:
    return LifecycleReport(
        generated_at="2026-03-31T11:00:00+00:00",
        apply=False,
        postgres_dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar",
        clickhouse_url="http://127.0.0.1:8123",
        clickhouse_database="vinted_radar",
        object_store_bucket="vinted-radar-test",
        clickhouse=ClickHouseLifecycleSection(status="ok", database="vinted_radar", actions=()),
        postgres=PostgresLifecycleSection(status="ok", actions=()),
        object_storage=ObjectStorageLifecycleSection(status="ok", bucket="vinted-radar-test", rules=()),
        posture=StoragePostureSummary(
            bounded=True,
            clickhouse_ttl_table_count=0,
            postgres_prune_target_count=0,
            object_storage_rule_count=0,
            archived_row_count=0,
            deleted_row_count=0,
        ),
    )


def _call_app(app_instance: DashboardApplication, path: str) -> dict[str, object]:
    environ: dict[str, str] = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(app_instance(environ, start_response))
    captured["body"] = body
    return captured


def test_run_platform_audit_reports_healthy_when_reconcile_and_paths_are_green(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "source.db.full-backfill-checkpoint.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "completed": True,
                "updated_at": "2026-03-31T11:00:00+00:00",
                "reference_now": "2026-03-31T11:00:00+00:00",
                "datasets": {"discoveries": {"completed_batches": 2}},
                "clickhouse": {"claimed_count": 2, "processed_count": 2, "skipped_count": 0},
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report = run_platform_audit(
        tmp_path / "source.db",
        config=_cutover_config(postgres=True, clickhouse=True, object_storage=True, polyglot_reads=True),
        checkpoint_path=checkpoint_path,
        repository=_CheckpointRepository(),
        lake_writer=_DummyWriter(),
        clickhouse_client=object(),
        reconciliation_report=_make_reconciliation_report(),
        lifecycle_report=_healthy_lifecycle_report(),
    )

    payload = report.as_dict()
    assert report.ok is True
    assert payload["overall_status"] == "healthy"
    assert payload["summary"]["reconciliation_status"] == "match"
    assert payload["paths"]["current_state"]["status"] == "healthy"
    assert payload["paths"]["analytical"]["status"] == "active"
    assert payload["paths"]["backfill"]["status"] == "complete"


def test_platform_audit_cli_emits_json(monkeypatch, tmp_path: Path) -> None:
    fake_config = _cutover_config(postgres=True, clickhouse=True, object_storage=True, polyglot_reads=True)
    fake_report = run_platform_audit(
        tmp_path / "source.db",
        config=fake_config,
        checkpoint_path=tmp_path / "source.db.full-backfill-checkpoint.json",
        repository=_CheckpointRepository(),
        lake_writer=_DummyWriter(),
        clickhouse_client=object(),
        reconciliation_report=_make_reconciliation_report(),
        lifecycle_report=_healthy_lifecycle_report(),
    )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    monkeypatch.setattr("vinted_radar.cli.run_platform_audit", lambda *args, **kwargs: fake_report)
    runner = CliRunner()

    result = runner.invoke(app, ["platform-audit", "--db", str(tmp_path / "source.db"), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "healthy"
    assert payload["summary"]["current_state_status"] == "healthy"


def test_runtime_payload_and_health_include_platform_audit(monkeypatch, tmp_path: Path) -> None:
    audit_payload = {
        "overall_status": "healthy",
        "summary": {
            "reconciliation_status": "match",
            "current_state_status": "healthy",
            "analytical_status": "active",
            "lifecycle_status": "healthy",
            "backfill_status": "complete",
        },
    }
    backend = _RuntimeBackend(tmp_path / "runtime.db")

    monkeypatch.setattr("vinted_radar.dashboard.load_platform_audit_snapshot", lambda *args, **kwargs: audit_payload)

    payload = build_runtime_payload(backend, now="2026-03-31T11:05:00+00:00")
    assert payload["platform_audit"]["overall_status"] == "healthy"
    assert payload["summary"]["platform_audit_status"] == "healthy"
    assert payload["summary"]["reconciliation_status"] == "match"

    app_instance = DashboardApplication(
        tmp_path / "runtime.db",
        now="2026-03-31T11:05:00+00:00",
        query_backend_factory=lambda _repository: backend,
    )
    response = _call_app(app_instance, "/health")
    assert response["status"] == "200 OK"
    body = json.loads(response["body"])
    assert body["platform_audit"]["overall_status"] == "healthy"
