from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.repository import RadarRepository
from vinted_radar.services.runtime import RadarRuntimeCycleReport


def test_batch_cli_reports_runtime_cycle_and_serves_dashboard(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeRuntimeService:
        def __init__(self, db_path: Path) -> None:
            captured["db_path"] = db_path

        def run_cycle(self, options, *, mode: str):
            captured["options"] = options
            captured["mode"] = mode
            return RadarRuntimeCycleReport(
                cycle_id="cycle-1",
                mode="batch",
                status="completed",
                phase="completed",
                started_at="2026-03-20T10:00:00+00:00",
                finished_at="2026-03-20T10:01:00+00:00",
                discovery_run_id="run-1",
                state_probed_count=2,
                tracked_listings=5,
                freshness_counts={
                    "first-pass-only": 3,
                    "fresh-followup": 2,
                    "aging-followup": 0,
                    "stale-followup": 0,
                },
                last_error=None,
                config={"state_refresh_limit": 4},
            )

    def fake_serve_dashboard(*, db_path: Path, host: str, port: int, now: str | None = None) -> None:
        captured["dashboard"] = {"db_path": db_path, "host": host, "port": port, "now": now}

    monkeypatch.setattr("vinted_radar.cli.RadarRuntimeService", FakeRuntimeService)
    monkeypatch.setattr("vinted_radar.cli.serve_dashboard", fake_serve_dashboard)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "batch",
            "--db",
            str(tmp_path / "runtime.db"),
            "--page-limit",
            "2",
            "--max-leaf-categories",
            "4",
            "--state-refresh-limit",
            "4",
            "--request-delay",
            "0.0",
            "--dashboard",
            "--host",
            "127.0.0.1",
            "--port",
            "8766",
        ],
    )

    assert result.exit_code == 0
    assert "Cycle: cycle-1" in result.stdout
    assert "State probes: 2 / 4" in result.stdout
    assert "Dashboard URL: http://127.0.0.1:8766" in result.stdout
    assert "Runtime API: http://127.0.0.1:8766/api/runtime" in result.stdout
    assert captured["db_path"] == tmp_path / "runtime.db"
    assert captured["mode"] == "batch"
    assert captured["dashboard"] == {
        "db_path": tmp_path / "runtime.db",
        "host": "127.0.0.1",
        "port": 8766,
        "now": None,
    }


def test_continuous_cli_starts_dashboard_and_prints_each_cycle(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {"stopped": False}

    class FakeDashboardHandle:
        def stop(self) -> None:
            captured["stopped"] = True

    class FakeRuntimeService:
        def __init__(self, db_path: Path) -> None:
            captured["db_path"] = db_path

        def run_continuous(self, options, *, interval_seconds: float, max_cycles: int | None, continue_on_error: bool, on_cycle_complete):
            captured["interval_seconds"] = interval_seconds
            captured["max_cycles"] = max_cycles
            captured["continue_on_error"] = continue_on_error
            on_cycle_complete(
                RadarRuntimeCycleReport(
                    cycle_id="cycle-1",
                    mode="continuous",
                    status="failed",
                    phase="discovery",
                    started_at="2026-03-20T10:00:00+00:00",
                    finished_at="2026-03-20T10:00:30+00:00",
                    discovery_run_id=None,
                    state_probed_count=0,
                    tracked_listings=0,
                    freshness_counts={
                        "first-pass-only": 0,
                        "fresh-followup": 0,
                        "aging-followup": 0,
                        "stale-followup": 0,
                    },
                    last_error="RuntimeError: boom",
                    config={"state_refresh_limit": 3},
                )
            )
            on_cycle_complete(
                RadarRuntimeCycleReport(
                    cycle_id="cycle-2",
                    mode="continuous",
                    status="completed",
                    phase="completed",
                    started_at="2026-03-20T10:01:00+00:00",
                    finished_at="2026-03-20T10:01:30+00:00",
                    discovery_run_id="run-2",
                    state_probed_count=1,
                    tracked_listings=4,
                    freshness_counts={
                        "first-pass-only": 2,
                        "fresh-followup": 2,
                        "aging-followup": 0,
                        "stale-followup": 0,
                    },
                    last_error=None,
                    config={"state_refresh_limit": 3},
                )
            )
            return []

    monkeypatch.setattr("vinted_radar.cli.RadarRuntimeService", FakeRuntimeService)
    monkeypatch.setattr("vinted_radar.cli.start_dashboard_server", lambda **kwargs: FakeDashboardHandle())
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "continuous",
            "--db",
            str(tmp_path / "runtime.db"),
            "--interval-seconds",
            "1",
            "--max-cycles",
            "2",
            "--state-refresh-limit",
            "3",
            "--dashboard",
            "--host",
            "127.0.0.1",
            "--port",
            "8770",
        ],
    )

    assert result.exit_code == 0
    assert "Dashboard URL: http://127.0.0.1:8770" in result.stdout
    assert "Cycle: cycle-1" in result.stdout
    assert "Last error: RuntimeError: boom" in result.stdout
    assert "Cycle: cycle-2" in result.stdout
    assert captured["interval_seconds"] == 1.0
    assert captured["max_cycles"] == 2
    assert captured["continue_on_error"] is True
    assert captured["stopped"] is True


def test_runtime_status_cli_emits_json_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    with RadarRepository(db_path) as repository:
        cycle_id = repository.start_runtime_cycle(
            mode="batch",
            phase="starting",
            interval_seconds=None,
            state_probe_limit=4,
            config={"state_refresh_limit": 4},
        )
        repository.complete_runtime_cycle(
            cycle_id,
            status="completed",
            phase="completed",
            discovery_run_id=None,
            state_probed_count=2,
            tracked_listings=5,
            freshness_counts={
                "first-pass-only": 3,
                "fresh-followup": 2,
                "aging-followup": 0,
                "stale-followup": 0,
            },
            last_error=None,
        )

    runner = CliRunner()
    result = runner.invoke(app, ["runtime-status", "--db", str(db_path), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["latest_cycle"]["cycle_id"] == cycle_id
    assert payload["latest_cycle"]["status"] == "completed"
    assert payload["totals"]["completed_cycles"] == 1
