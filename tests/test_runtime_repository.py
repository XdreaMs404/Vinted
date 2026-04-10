from __future__ import annotations

from pathlib import Path
import sqlite3

from vinted_radar.db import connect_database
from vinted_radar.repository import RadarRepository


def test_runtime_cycle_methods_keep_controller_snapshot_in_sync(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"

    with RadarRepository(db_path) as repository:
        cycle_id = repository.start_runtime_cycle(
            mode="batch",
            phase="starting",
            interval_seconds=None,
            state_probe_limit=4,
            config={"state_refresh_limit": 4},
        )
        controller = repository.runtime_controller_state()
        assert controller is not None
        assert controller["status"] == "running"
        assert controller["phase"] == "starting"
        assert controller["active_cycle_id"] == cycle_id
        assert controller["latest_cycle_id"] == cycle_id
        assert controller["requested_action"] == "none"

        repository.update_runtime_cycle_phase(cycle_id, phase="discovery")
        controller = repository.runtime_controller_state()
        assert controller is not None
        assert controller["phase"] == "discovery"

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
                "status": "partial",
                "probed_count": 2,
                "direct_signal_count": 1,
                "inconclusive_probe_count": 1,
                "degraded_probe_count": 0,
            },
        )
        status = repository.runtime_status(limit=5)

    assert status["status"] == "idle"
    assert status["phase"] == "idle"
    assert status["latest_cycle"]["cycle_id"] == cycle_id
    assert status["latest_cycle"]["status"] == "completed"
    assert status["latest_cycle"]["state_refresh_summary"]["status"] == "partial"
    assert status["latest_cycle"]["state_refresh_summary"]["inconclusive_probe_count"] == 1
    assert status["controller"]["latest_cycle_id"] == cycle_id
    assert status["controller"]["active_cycle_id"] is None
    assert status["totals"]["completed_cycles"] == 1



def test_runtime_status_aggregates_top_level_truth_from_active_lane_views(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"

    with RadarRepository(db_path) as repository:
        repository.set_runtime_controller_state(
            lane_name="frontier",
            status="idle",
            phase="idle",
            mode="continuous",
            active_cycle_id=None,
            latest_cycle_id=None,
            interval_seconds=900.0,
            updated_at="2026-03-23T09:00:00+00:00",
            paused_at=None,
            next_resume_at=None,
            requested_action="none",
            requested_at=None,
            config={"state_refresh_limit": 1},
        )
        expansion_cycle = repository.start_runtime_cycle(
            mode="continuous",
            phase="discovery",
            interval_seconds=900.0,
            state_probe_limit=1,
            config={"state_refresh_limit": 1},
            lane_name="expansion",
            benchmark_label="expansion-smoke",
        )
        status = repository.runtime_status(limit=5, now="2026-03-23T09:05:00+00:00")

    assert status["controller"] is not None
    assert status["controller"]["status"] == "idle"
    assert status["lanes"]["frontier"]["status"] == "idle"
    assert status["lanes"]["expansion"]["status"] == "running"
    assert status["status"] == "running"
    assert status["phase"] == "discovery"
    assert status["active_cycle_id"] == expansion_cycle
    assert status["latest_cycle_id"] == expansion_cycle



def test_connect_database_migrates_legacy_runtime_cycles_before_creating_lane_index(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-runtime.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE runtime_cycles (
                cycle_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                phase TEXT NOT NULL,
                interval_seconds REAL,
                state_probe_limit INTEGER NOT NULL DEFAULT 0,
                discovery_run_id TEXT,
                state_probed_count INTEGER NOT NULL DEFAULT 0,
                tracked_listings INTEGER NOT NULL DEFAULT 0,
                first_pass_only INTEGER NOT NULL DEFAULT 0,
                fresh_followup INTEGER NOT NULL DEFAULT 0,
                aging_followup INTEGER NOT NULL DEFAULT 0,
                stale_followup INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                state_refresh_summary_json TEXT NOT NULL DEFAULT '{}',
                config_json TEXT NOT NULL DEFAULT '{}'
            );
            INSERT INTO runtime_cycles (
                cycle_id, started_at, finished_at, mode, status, phase, interval_seconds, state_probe_limit,
                discovery_run_id, state_probed_count, tracked_listings, first_pass_only, fresh_followup,
                aging_followup, stale_followup, last_error, state_refresh_summary_json, config_json
            ) VALUES (
                'legacy-cycle', '2026-04-09T15:00:00+00:00', '2026-04-09T15:05:00+00:00', 'continuous', 'completed',
                'completed', 900.0, 1, NULL, 0, 0, 0, 0, 0, 0, NULL, '{}', '{}'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    migrated = connect_database(db_path)
    try:
        lane_columns = {
            row[1]
            for row in migrated.execute("PRAGMA table_info(runtime_cycles)").fetchall()
        }
        assert "lane_name" in lane_columns
        index_names = {
            row[1]
            for row in migrated.execute("PRAGMA index_list(runtime_cycles)").fetchall()
        }
        assert "idx_runtime_cycles_lane_started_at" in index_names
        lane_value = migrated.execute(
            "SELECT lane_name FROM runtime_cycles WHERE cycle_id = ?",
            ("legacy-cycle",),
        ).fetchone()[0]
        assert lane_value == "frontier"
    finally:
        migrated.close()



def test_runtime_status_exposes_controller_timing_recent_failures_and_redacts_config(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"

    with RadarRepository(db_path) as repository:
        failed_cycle = repository.start_runtime_cycle(
            mode="continuous",
            phase="starting",
            interval_seconds=900.0,
            state_probe_limit=2,
            config={"state_refresh_limit": 2},
        )
        repository.complete_runtime_cycle(
            failed_cycle,
            status="failed",
            phase="discovery",
            discovery_run_id=None,
            state_probed_count=0,
            tracked_listings=0,
            freshness_counts={},
            last_error="RuntimeError: boom",
        )

        completed_cycle = repository.start_runtime_cycle(
            mode="continuous",
            phase="starting",
            interval_seconds=900.0,
            state_probe_limit=2,
            config={"state_refresh_limit": 2},
        )
        repository.complete_runtime_cycle(
            completed_cycle,
            status="completed",
            phase="completed",
            discovery_run_id=None,
            state_probed_count=1,
            tracked_listings=4,
            freshness_counts={
                "first-pass-only": 1,
                "fresh-followup": 2,
                "aging-followup": 1,
                "stale-followup": 0,
            },
            last_error=None,
            state_refresh_summary={
                "status": "degraded",
                "probed_count": 1,
                "direct_signal_count": 0,
                "inconclusive_probe_count": 0,
                "degraded_probe_count": 1,
                "anti_bot_challenge_count": 1,
            },
        )

        repository.set_runtime_controller_state(
            status="paused",
            phase="paused",
            mode="continuous",
            active_cycle_id=None,
            latest_cycle_id=completed_cycle,
            interval_seconds=900.0,
            updated_at="2026-03-23T09:05:00+00:00",
            paused_at="2026-03-23T09:00:00+00:00",
            next_resume_at="2026-03-23T09:30:00+00:00",
            last_error="RuntimeError: boom",
            last_error_at="2026-03-23T08:45:00+00:00",
            config={
                "proxy": "http://alice:secret@proxy.example:8080",
                "nested": {"upstream": "https://bob:token@example.com/path"},
            },
        )
        status = repository.runtime_status(limit=5, now="2026-03-23T09:10:00+00:00")

    assert status["status"] == "paused"
    assert status["phase"] == "paused"
    assert status["paused_at"] == "2026-03-23T09:00:00+00:00"
    assert status["next_resume_at"] == "2026-03-23T09:30:00+00:00"
    assert status["elapsed_pause_seconds"] == 600.0
    assert status["next_resume_in_seconds"] == 1200.0
    assert status["last_error"] == "RuntimeError: boom"
    assert status["latest_failure"] is not None
    assert status["latest_failure"]["cycle_id"] == failed_cycle
    assert len(status["recent_failures"]) == 1
    assert status["acquisition"]["status"] == "degraded"
    assert status["acquisition"]["latest_state_refresh_summary"]["anti_bot_challenge_count"] == 1

    controller = status["controller"]
    assert controller is not None
    assert controller["heartbeat"]["age_seconds"] == 300.0
    assert controller["heartbeat"]["stale_after_seconds"] == 120.0
    assert controller["heartbeat"]["is_stale"] is True
    assert status["acquisition"]["latest_cycle_id"] == completed_cycle
    assert controller["config"]["proxy"] == "http://***@proxy.example:8080"
    assert controller["config"]["nested"]["upstream"] == "https://***@example.com/path"


def test_runtime_pause_and_resume_requests_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"

    with RadarRepository(db_path) as repository:
        cycle_id = repository.start_runtime_cycle(
            mode="continuous",
            phase="starting",
            interval_seconds=300.0,
            state_probe_limit=3,
            config={"state_refresh_limit": 3},
        )

        pending_pause = repository.request_runtime_pause(requested_at="2026-03-23T10:00:00+00:00")
        assert pending_pause["status"] == "running"
        assert pending_pause["requested_action"] == "pause"
        assert pending_pause["requested_at"] == "2026-03-23T10:00:00+00:00"

        cleared = repository.request_runtime_resume(requested_at="2026-03-23T10:01:00+00:00")
        assert cleared["status"] == "running"
        assert cleared["requested_action"] == "none"
        assert cleared["requested_at"] is None

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
        )
        repository.set_runtime_controller_state(
            status="scheduled",
            phase="waiting",
            mode="continuous",
            active_cycle_id=None,
            latest_cycle_id=cycle_id,
            interval_seconds=300.0,
            updated_at="2026-03-23T10:02:00+00:00",
            paused_at=None,
            next_resume_at="2026-03-23T10:07:00+00:00",
            requested_action="none",
            requested_at=None,
            config={"state_refresh_limit": 3},
        )

        paused = repository.request_runtime_pause(requested_at="2026-03-23T10:03:00+00:00")
        assert paused["status"] == "paused"
        assert paused["phase"] == "paused"
        assert paused["paused_at"] == "2026-03-23T10:03:00+00:00"
        assert paused["next_resume_at"] is None
        assert paused["requested_action"] == "none"

        resumed = repository.request_runtime_resume(requested_at="2026-03-23T10:04:00+00:00")
        assert resumed["status"] == "scheduled"
        assert resumed["phase"] == "waiting"
        assert resumed["paused_at"] is None
        assert resumed["next_resume_at"] == "2026-03-23T10:04:00+00:00"
        assert resumed["requested_action"] == "none"
