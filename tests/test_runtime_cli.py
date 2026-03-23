from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.repository import RadarRepository
from vinted_radar.services.runtime import RadarRuntimeCycleReport
from vinted_radar.services.state_refresh import StateRefreshReport


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
                state_refresh_summary={
                    "status": "degraded",
                    "direct_signal_count": 1,
                    "inconclusive_probe_count": 0,
                    "degraded_probe_count": 1,
                    "anti_bot_challenge_count": 1,
                },
            )

    def fake_serve_dashboard(
        *,
        db_path: Path,
        host: str,
        port: int,
        now: str | None = None,
        base_path: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        captured["dashboard"] = {
            "db_path": db_path,
            "host": host,
            "port": port,
            "now": now,
            "base_path": base_path,
            "public_base_url": public_base_url,
        }

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
            "--min-price",
            "75",
            "--target-catalogs",
            "2001",
            "--target-catalogs",
            "3001",
            "--target-brands",
            "Chanel",
            "--target-brands",
            "Dior",
            "--state-refresh-limit",
            "4",
            "--request-delay",
            "0.0",
            "--proxy",
            "http://proxy-a:8080",
            "--proxy",
            "http://proxy-b:8080",
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
    assert "State refresh health: degraded | direct 1 | inconclusive 0 | degraded 1" in result.stdout
    assert "Anti-bot challenges: 1" in result.stdout
    assert "Dashboard URL: http://127.0.0.1:8766" in result.stdout
    assert "Runtime: http://127.0.0.1:8766/runtime" in result.stdout
    assert "Runtime API: http://127.0.0.1:8766/api/runtime" in result.stdout
    assert "Listing detail: http://127.0.0.1:8766/listings/<id>" in result.stdout
    assert captured["db_path"] == tmp_path / "runtime.db"
    assert captured["mode"] == "batch"
    assert captured["options"].min_price == 75.0
    assert captured["options"].target_catalogs == (2001, 3001)
    assert captured["options"].target_brands == ("Chanel", "Dior")
    assert tuple(captured["options"].proxies) == ("http://proxy-a:8080", "http://proxy-b:8080")
    assert captured["dashboard"] == {
        "db_path": tmp_path / "runtime.db",
        "host": "127.0.0.1",
        "port": 8766,
        "now": None,
        "base_path": "",
        "public_base_url": None,
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
            captured["options"] = options
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
                    state_refresh_summary={
                        "status": "degraded",
                        "direct_signal_count": 0,
                        "inconclusive_probe_count": 0,
                        "degraded_probe_count": 1,
                        "anti_bot_challenge_count": 1,
                    },
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
                    state_refresh_summary={
                        "status": "partial",
                        "direct_signal_count": 0,
                        "inconclusive_probe_count": 1,
                        "degraded_probe_count": 0,
                    },
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
            "--min-price",
            "120",
            "--target-catalogs",
            "4001",
            "--target-brands",
            "Hermès",
            "--state-refresh-limit",
            "3",
            "--proxy",
            "http://proxy-c:8080",
            "--dashboard",
            "--host",
            "127.0.0.1",
            "--port",
            "8770",
        ],
    )

    assert result.exit_code == 0
    assert "Dashboard URL: http://127.0.0.1:8770" in result.stdout
    assert "Runtime: http://127.0.0.1:8770/runtime" in result.stdout
    assert "Listing detail: http://127.0.0.1:8770/listings/<id>" in result.stdout
    assert "Cycle: cycle-1" in result.stdout
    assert "Last error: RuntimeError: boom" in result.stdout
    assert "State refresh health: degraded | direct 0 | inconclusive 0 | degraded 1" in result.stdout
    assert "Cycle: cycle-2" in result.stdout
    assert "State refresh health: partial | direct 0 | inconclusive 1 | degraded 0" in result.stdout
    assert captured["interval_seconds"] == 1.0
    assert captured["max_cycles"] == 2
    assert captured["options"].min_price == 120.0
    assert captured["options"].target_catalogs == (4001,)
    assert captured["options"].target_brands == ("Hermès",)
    assert tuple(captured["options"].proxies) == ("http://proxy-c:8080",)
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
            state_refresh_summary={
                "status": "degraded",
                "direct_signal_count": 1,
                "inconclusive_probe_count": 0,
                "degraded_probe_count": 1,
                "anti_bot_challenge_count": 1,
            },
        )

    runner = CliRunner()
    result = runner.invoke(app, ["runtime-status", "--db", str(db_path), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "idle"
    assert payload["controller"]["status"] == "idle"
    assert payload["latest_cycle"]["cycle_id"] == cycle_id
    assert payload["latest_cycle"]["status"] == "completed"
    assert payload["latest_cycle"]["state_refresh_summary"]["status"] == "degraded"
    assert payload["latest_cycle"]["state_refresh_summary"]["anti_bot_challenge_count"] == 1
    assert payload["totals"]["completed_cycles"] == 1



def test_state_refresh_cli_accepts_proxy_pool_and_emits_probe_summary(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeRepository:
        def close(self) -> None:
            captured["repository_closed"] = True

    class FakeStateRefreshService:
        def __init__(self) -> None:
            self.repository = FakeRepository()

        def refresh(self, *, limit: int = 10, listing_id: int | None = None, now: str | None = None) -> StateRefreshReport:
            captured["refresh"] = {"limit": limit, "listing_id": listing_id, "now": now}
            return StateRefreshReport(
                probed_count=1,
                probed_listing_ids=[9001],
                probe_summary={
                    "status": "degraded",
                    "requested_limit": limit,
                    "selected_target_count": 1,
                    "probed_count": 1,
                    "direct_signal_count": 0,
                    "inconclusive_probe_count": 0,
                    "degraded_probe_count": 1,
                    "anti_bot_challenge_count": 1,
                    "http_error_count": 0,
                    "transport_error_count": 0,
                    "outcome_counts": {"active": 0, "sold": 0, "unavailable": 0, "deleted": 0, "unknown": 1},
                    "reason_counts": {"anti_bot_challenge": 1},
                    "degraded_listing_ids": [9001],
                },
                state_summary={"generated_at": now or "2026-03-23T10:00:00+00:00", "overall": {"tracked_listings": 1}, "by_root": []},
            )

    def fake_factory(*, db_path: str, timeout_seconds: float, request_delay: float, proxies=None):
        captured["factory"] = {
            "db_path": db_path,
            "timeout_seconds": timeout_seconds,
            "request_delay": request_delay,
            "proxies": proxies,
        }
        return FakeStateRefreshService()

    monkeypatch.setattr("vinted_radar.cli.build_default_state_refresh_service", fake_factory)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "state-refresh",
            "--db",
            str(tmp_path / "runtime.db"),
            "--limit",
            "1",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
            "--proxy",
            "http://proxy-a:8080",
            "--proxy",
            "http://proxy-b:8080",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["probe_summary"]["status"] == "degraded"
    assert payload["probe_summary"]["anti_bot_challenge_count"] == 1
    assert captured["factory"] == {
        "db_path": str(tmp_path / "runtime.db"),
        "timeout_seconds": 5.0,
        "request_delay": 0.0,
        "proxies": ["http://proxy-a:8080", "http://proxy-b:8080"],
    }
    assert captured["refresh"] == {"limit": 1, "listing_id": None, "now": None}
    assert captured["repository_closed"] is True



def test_runtime_pause_and_resume_cli_mutate_controller_state(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    with RadarRepository(db_path) as repository:
        repository.set_runtime_controller_state(
            status="scheduled",
            phase="waiting",
            mode="continuous",
            active_cycle_id=None,
            latest_cycle_id=None,
            interval_seconds=300.0,
            updated_at="2026-03-23T09:00:00+00:00",
            paused_at=None,
            next_resume_at="2026-03-23T09:05:00+00:00",
            requested_action="none",
            requested_at=None,
            config={"state_refresh_limit": 2},
        )

    runner = CliRunner()
    pause_result = runner.invoke(app, ["runtime-pause", "--db", str(db_path)])
    assert pause_result.exit_code == 0
    assert "Runtime is now paused" in pause_result.stdout

    with RadarRepository(db_path) as repository:
        paused = repository.runtime_status(limit=3)
    assert paused["status"] == "paused"

    resume_result = runner.invoke(app, ["runtime-resume", "--db", str(db_path)])
    assert resume_result.exit_code == 0
    assert "Runtime resumed. Next cycle window" in resume_result.stdout

    with RadarRepository(db_path) as repository:
        resumed = repository.runtime_status(limit=3)
    assert resumed["status"] == "scheduled"
    assert resumed["next_resume_at"] is not None



def test_runtime_status_cli_table_shows_controller_timing(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    with RadarRepository(db_path) as repository:
        cycle_id = repository.start_runtime_cycle(
            mode="continuous",
            phase="starting",
            interval_seconds=300.0,
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
                "status": "partial",
                "direct_signal_count": 0,
                "inconclusive_probe_count": 1,
                "degraded_probe_count": 0,
            },
        )
        repository.set_runtime_controller_state(
            status="paused",
            phase="paused",
            mode="continuous",
            active_cycle_id=None,
            latest_cycle_id=cycle_id,
            interval_seconds=300.0,
            updated_at="2026-03-23T09:05:00+00:00",
            paused_at="2026-03-23T09:00:00+00:00",
            next_resume_at="2026-03-23T09:15:00+00:00",
            requested_action="none",
            requested_at=None,
            config={"state_refresh_limit": 2},
        )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "runtime-status",
            "--db",
            str(db_path),
            "--now",
            "2026-03-23T09:10:00+00:00",
        ],
    )

    assert result.exit_code == 0
    assert "Runtime now: paused (phase paused)" in result.stdout
    assert "Paused since: 2026-03-23T09:00:00+00:00 (10m 00s)" in result.stdout
    assert "Next resume: 2026-03-23T09:15:00+00:00 (5m 00s remaining)" in result.stdout
    assert "State refresh health: partial | direct 0 | inconclusive 1 | degraded 0" in result.stdout
