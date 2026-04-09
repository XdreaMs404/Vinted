from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

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


def test_batch_cli_defaults_to_bounded_price_filter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeRuntimeService:
        def __init__(self, db_path: Path) -> None:
            captured["db_path"] = db_path

        def run_cycle(self, options, *, mode: str):
            captured["options"] = options
            captured["mode"] = mode
            return RadarRuntimeCycleReport(
                cycle_id="cycle-default-batch",
                mode="batch",
                status="completed",
                phase="completed",
                started_at="2026-03-20T10:00:00+00:00",
                finished_at="2026-03-20T10:01:00+00:00",
                discovery_run_id="run-default-batch",
                state_probed_count=0,
                tracked_listings=0,
                freshness_counts={
                    "first-pass-only": 0,
                    "fresh-followup": 0,
                    "aging-followup": 0,
                    "stale-followup": 0,
                },
                last_error=None,
                config={"state_refresh_limit": 10},
                state_refresh_summary=None,
            )

    monkeypatch.setattr("vinted_radar.cli.RadarRuntimeService", FakeRuntimeService)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "batch",
            "--db",
            str(tmp_path / "runtime.db"),
            "--page-limit",
            "1",
            "--max-leaf-categories",
            "1",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
        ],
    )

    assert result.exit_code == 0
    assert captured["mode"] == "batch"
    assert captured["options"].min_price == 30.0
    assert captured["options"].max_price == 0.0


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


def test_continuous_cli_defaults_to_bounded_price_filter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeRuntimeService:
        def __init__(self, db_path: Path) -> None:
            captured["db_path"] = db_path

        def run_continuous(self, options, *, interval_seconds: float, max_cycles: int | None, continue_on_error: bool, on_cycle_complete):
            captured["options"] = options
            captured["interval_seconds"] = interval_seconds
            captured["max_cycles"] = max_cycles
            captured["continue_on_error"] = continue_on_error
            return []

    monkeypatch.setattr("vinted_radar.cli.RadarRuntimeService", FakeRuntimeService)
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
            "1",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
        ],
    )

    assert result.exit_code == 0
    assert captured["options"].min_price == 30.0
    assert captured["options"].max_price == 0.0


def test_runtime_status_cli_emits_json_payload(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    captured: dict[str, object] = {}
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

    def fake_load_platform_audit_snapshot(*args, **kwargs):
        captured["embedded"] = kwargs.get("embedded")
        return {
            "overall_status": "lagging",
            "summary": {
                "reconciliation_status": "deferred",
                "current_state_status": "never-run",
                "analytical_status": "never-run",
                "lifecycle_status": "healthy",
                "backfill_status": "not-run",
            },
        }

    monkeypatch.setattr("vinted_radar.cli.load_platform_audit_snapshot", fake_load_platform_audit_snapshot)
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
    assert payload["platform_audit"]["summary"]["reconciliation_status"] == "deferred"
    assert captured["embedded"] is True



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
    assert payload["transport"]["mode"] == "proxy-pool"
    assert payload["transport"]["proxy_pool_size"] == 2
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



def test_state_refresh_cli_loads_proxy_file(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text(
        "\n".join(
            [
                "45.39.4.37:5462:alice:secret",
                "216.173.80.190:6447:bob:token",
            ]
        ),
        encoding="utf-8",
    )

    class FakeRepository:
        def close(self) -> None:
            return None

    class FakeStateRefreshService:
        def __init__(self) -> None:
            self.repository = FakeRepository()

        def refresh(self, *, limit: int = 10, listing_id: int | None = None, now: str | None = None) -> StateRefreshReport:
            return StateRefreshReport(
                probed_count=0,
                probed_listing_ids=[],
                probe_summary={},
                state_summary={"generated_at": now or "2026-03-23T10:00:00+00:00", "overall": {"tracked_listings": 0}, "by_root": []},
            )

    def fake_factory(*, db_path: str, timeout_seconds: float, request_delay: float, proxies=None):
        captured["proxies"] = proxies
        return FakeStateRefreshService()

    monkeypatch.setattr("vinted_radar.cli.build_default_state_refresh_service", fake_factory)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "state-refresh",
            "--db",
            str(tmp_path / "runtime.db"),
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
            "--proxy-file",
            str(proxy_file),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["transport"]["proxy_pool_size"] == 2
    assert captured["proxies"] == [
        "http://alice:secret@45.39.4.37:5462",
        "http://bob:token@216.173.80.190:6447",
    ]



def test_proxy_preflight_cli_emits_safe_json_summary(monkeypatch, tmp_path: Path) -> None:
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("45.39.4.37:5462:alice:secret\n216.173.80.190:6447:bob:token\n", encoding="utf-8")

    async def fake_preflight(*, proxies: tuple[str, ...], sample_size: int, timeout_seconds: float):
        assert proxies == (
            "http://alice:secret@45.39.4.37:5462",
            "http://bob:token@216.173.80.190:6447",
        )
        assert sample_size == 2
        assert timeout_seconds == 5.0
        return {
            "summary": {
                "configured_proxy_count": 2,
                "sampled_routes": 2,
                "successful_routes": 2,
                "failed_routes": 0,
                "unique_exit_ip_count": 2,
                "vinted_success_count": 2,
                "vinted_challenge_count": 0,
            },
            "routes": [
                {
                    "route": "http://***@45.39.4.37:5462",
                    "exit_ip": "45.39.4.37",
                    "ip_echo_status": 200,
                    "vinted_status": 200,
                    "challenge_suspected": False,
                    "vinted_ok": True,
                    "ok": True,
                    "error": None,
                }
            ],
        }

    monkeypatch.setattr("vinted_radar.cli._run_proxy_preflight", fake_preflight)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "proxy-preflight",
            "--proxy-file",
            str(proxy_file),
            "--sample-size",
            "2",
            "--timeout-seconds",
            "5.0",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["unique_exit_ip_count"] == 2
    assert payload["routes"][0]["route"] == "http://***@45.39.4.37:5462"
    assert "alice:secret" not in result.stdout



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

def test_runtime_status_cli_stays_on_sqlite_in_shadow_mode(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    with RadarRepository(db_path) as repository:
        cycle_id = repository.start_runtime_cycle(
            mode="continuous",
            phase="waiting",
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
                "status": "healthy",
                "direct_signal_count": 1,
                "inconclusive_probe_count": 0,
                "degraded_probe_count": 0,
            },
        )

    fake_config = SimpleNamespace(
        cutover=SimpleNamespace(enable_postgres_writes=True, enable_polyglot_reads=False),
        postgres=SimpleNamespace(dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"),
    )
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)

    def fail_if_called(dsn: str):
        raise AssertionError("runtime-status should stay on SQLite in dual-write-shadow mode")

    monkeypatch.setattr("vinted_radar.cli.PostgresMutableTruthRepository.from_dsn", fail_if_called)
    monkeypatch.setattr(
        "vinted_radar.cli.load_platform_audit_snapshot",
        lambda *args, **kwargs: {
            "overall_status": "lagging",
            "summary": {
                "reconciliation_status": "deferred",
                "current_state_status": "never-run",
                "analytical_status": "never-run",
                "lifecycle_status": "healthy",
                "backfill_status": "not-run",
            },
        },
    )
    runner = CliRunner()

    result = runner.invoke(app, ["runtime-status", "--db", str(db_path), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["latest_cycle"]["cycle_id"] == cycle_id
    assert payload["status"] == "idle"



def test_runtime_status_cli_uses_polyglot_control_plane_when_enabled(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeControlPlaneRepository:
        def runtime_status(self, *, limit: int, now: str | None = None) -> dict[str, object]:
            captured["limit"] = limit
            captured["now"] = now
            return {
                "generated_at": "2026-03-23T09:10:00+00:00",
                "db_path": "postgres",
                "controller": {"status": "paused", "phase": "paused"},
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
                "latest_cycle_id": "cycle-pg-1",
                "heartbeat": {"age_seconds": 10.0, "stale_after_seconds": 120.0, "is_stale": False},
                "latest_cycle": {
                    "cycle_id": "cycle-pg-1",
                    "mode": "continuous",
                    "status": "completed",
                    "phase": "completed",
                    "started_at": "2026-03-23T09:00:00+00:00",
                    "finished_at": "2026-03-23T09:05:00+00:00",
                    "discovery_run_id": "run-pg-1",
                    "state_probed_count": 1,
                    "state_probe_limit": 2,
                    "tracked_listings": 2,
                    "first_pass_only": 1,
                    "fresh_followup": 1,
                    "aging_followup": 0,
                    "stale_followup": 0,
                    "state_refresh_summary": {"status": "partial", "direct_signal_count": 0, "inconclusive_probe_count": 1, "degraded_probe_count": 0},
                },
                "recent_cycles": [],
                "latest_failure": None,
                "recent_failures": [],
                "acquisition": {"status": "healthy", "latest_state_refresh_summary": {}},
                "totals": {"total_cycles": 1, "completed_cycles": 1, "failed_cycles": 0, "running_cycles": 0, "interrupted_cycles": 0},
            }

        def close(self) -> None:
            captured["closed"] = True

    fake_config = SimpleNamespace(
        cutover=SimpleNamespace(enable_polyglot_reads=True),
        postgres=SimpleNamespace(dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"),
    )
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    monkeypatch.setattr("vinted_radar.cli.PostgresMutableTruthRepository.from_dsn", lambda dsn: FakeControlPlaneRepository())
    runner = CliRunner()

    result = runner.invoke(app, ["runtime-status", "--db", str(tmp_path / "runtime.db"), "--format", "json", "--limit", "3"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "paused"
    assert payload["latest_cycle"]["cycle_id"] == "cycle-pg-1"
    assert captured["limit"] == 3
    assert captured["closed"] is True



def test_runtime_pause_and_resume_cli_use_polyglot_control_plane_when_enabled(monkeypatch, tmp_path: Path) -> None:
    state = {
        "status": "scheduled",
        "phase": "waiting",
        "next_resume_at": "2026-03-23T09:05:00+00:00",
    }
    captures = {"pause_calls": 0, "resume_calls": 0, "closed": 0}

    class FakeControlPlaneRepository:
        def request_runtime_pause(self) -> dict[str, object]:
            captures["pause_calls"] += 1
            state.update({"status": "paused", "phase": "paused", "next_resume_at": None})
            return {
                "status": state["status"],
                "phase": state["phase"],
                "requested_action": "none",
                "next_resume_at": state["next_resume_at"],
            }

        def request_runtime_resume(self) -> dict[str, object]:
            captures["resume_calls"] += 1
            state.update({"status": "scheduled", "phase": "waiting", "next_resume_at": "2026-03-23T09:06:00+00:00"})
            return {
                "status": state["status"],
                "phase": state["phase"],
                "requested_action": "none",
                "next_resume_at": state["next_resume_at"],
            }

        def close(self) -> None:
            captures["closed"] += 1

    fake_config = SimpleNamespace(
        cutover=SimpleNamespace(enable_polyglot_reads=True),
        postgres=SimpleNamespace(dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"),
    )
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    monkeypatch.setattr("vinted_radar.cli.PostgresMutableTruthRepository.from_dsn", lambda dsn: FakeControlPlaneRepository())
    runner = CliRunner()

    pause_result = runner.invoke(app, ["runtime-pause", "--db", str(tmp_path / "runtime.db")])
    resume_result = runner.invoke(app, ["runtime-resume", "--db", str(tmp_path / "runtime.db")])

    assert pause_result.exit_code == 0
    assert "Runtime is now paused" in pause_result.stdout
    assert resume_result.exit_code == 0
    assert "Runtime resumed. Next cycle window: 2026-03-23T09:06:00+00:00" in resume_result.stdout
    assert captures["pause_calls"] == 1
    assert captures["resume_calls"] == 1
    assert captures["closed"] == 2



def test_batch_cli_injects_polyglot_control_plane_repository_into_runtime_service(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    fake_repository = object()

    class FakeRuntimeService:
        def __init__(self, db_path: Path, *, control_plane_repository: object | None = None) -> None:
            captured["db_path"] = db_path
            captured["control_plane_repository"] = control_plane_repository

        def run_cycle(self, options, *, mode: str):
            captured["mode"] = mode
            return RadarRuntimeCycleReport(
                cycle_id="cycle-polyglot",
                mode="batch",
                status="completed",
                phase="completed",
                started_at="2026-03-20T10:00:00+00:00",
                finished_at="2026-03-20T10:01:00+00:00",
                discovery_run_id="run-polyglot",
                state_probed_count=0,
                tracked_listings=0,
                freshness_counts={"first-pass-only": 0, "fresh-followup": 0, "aging-followup": 0, "stale-followup": 0},
                last_error=None,
                config={"state_refresh_limit": 10},
                state_refresh_summary=None,
            )

        def close(self) -> None:
            captured["closed"] = True

    fake_config = SimpleNamespace(
        cutover=SimpleNamespace(enable_polyglot_reads=True),
        postgres=SimpleNamespace(dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"),
    )
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    monkeypatch.setattr("vinted_radar.cli.PostgresMutableTruthRepository.from_dsn", lambda dsn: fake_repository)
    monkeypatch.setattr("vinted_radar.cli.RadarRuntimeService", FakeRuntimeService)
    runner = CliRunner()

    result = runner.invoke(app, ["batch", "--db", str(tmp_path / "runtime.db"), "--request-delay", "0.0", "--timeout-seconds", "5.0"])

    assert result.exit_code == 0
    assert captured["control_plane_repository"] is fake_repository
    assert captured["mode"] == "batch"
    assert captured["closed"] is True



def test_batch_cli_keeps_sqlite_control_plane_in_shadow_mode(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeRuntimeService:
        def __init__(self, db_path: Path, *, control_plane_repository: object | None = None) -> None:
            captured["db_path"] = db_path
            captured["control_plane_repository"] = control_plane_repository

        def run_cycle(self, options, *, mode: str):
            captured["mode"] = mode
            return RadarRuntimeCycleReport(
                cycle_id="cycle-postgres-writes",
                mode="batch",
                status="completed",
                phase="completed",
                started_at="2026-03-20T10:00:00+00:00",
                finished_at="2026-03-20T10:01:00+00:00",
                discovery_run_id="run-postgres-writes",
                state_probed_count=0,
                tracked_listings=0,
                freshness_counts={"first-pass-only": 0, "fresh-followup": 0, "aging-followup": 0, "stale-followup": 0},
                last_error=None,
                config={"state_refresh_limit": 10},
                state_refresh_summary=None,
            )

        def close(self) -> None:
            captured["closed"] = True

    fake_config = SimpleNamespace(
        cutover=SimpleNamespace(enable_postgres_writes=True, enable_polyglot_reads=False),
        postgres=SimpleNamespace(dsn="postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"),
    )
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)

    def fail_if_called(dsn: str):
        raise AssertionError("Postgres control-plane repository should stay disabled in dual-write-shadow mode")

    monkeypatch.setattr("vinted_radar.cli.PostgresMutableTruthRepository.from_dsn", fail_if_called)
    monkeypatch.setattr("vinted_radar.cli.RadarRuntimeService", FakeRuntimeService)
    runner = CliRunner()

    result = runner.invoke(app, ["batch", "--db", str(tmp_path / "runtime.db"), "--request-delay", "0.0", "--timeout-seconds", "5.0"])

    assert result.exit_code == 0
    assert captured["control_plane_repository"] is None
    assert captured["mode"] == "batch"
    assert captured["closed"] is True
