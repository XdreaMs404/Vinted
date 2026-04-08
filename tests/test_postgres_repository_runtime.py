from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository


class _QueryResult:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class RuntimeProjectionConnection:
    def __init__(self) -> None:
        self.runtime_cycles: dict[str, dict[str, object]] = {}
        self.runtime_controller: dict[int, dict[str, object]] = {}
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> _QueryResult:
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO platform_runtime_cycles"):
            assert params is not None
            if params[18] is not None:
                raise AssertionError(f"runtime cycle snapshot must not reference synthetic platform_events rows: {params[18]}")
            row = {
                "cycle_id": params[0],
                "started_at": params[1],
                "finished_at": params[2],
                "mode": params[3],
                "status": params[4],
                "phase": params[5],
                "interval_seconds": params[6],
                "state_probe_limit": params[7],
                "discovery_run_id": params[8],
                "state_probed_count": params[9],
                "tracked_listings": params[10],
                "first_pass_only": params[11],
                "fresh_followup": params[12],
                "aging_followup": params[13],
                "stale_followup": params[14],
                "last_error": params[15],
                "state_refresh_summary_json": params[16],
                "config_json": params[17],
                "last_event_id": params[18],
                "last_manifest_id": params[19],
                "projected_at": params[20],
            }
            self.runtime_cycles[str(params[0])] = row
            return _QueryResult()
        if normalized.startswith("INSERT INTO platform_runtime_controller_state"):
            assert params is not None
            if params[16] is not None:
                raise AssertionError(f"runtime controller snapshot must not reference synthetic platform_events rows: {params[16]}")
            row = {
                "controller_id": params[0],
                "status": params[1],
                "phase": params[2],
                "mode": params[3],
                "active_cycle_id": params[4],
                "latest_cycle_id": params[5],
                "interval_seconds": params[6],
                "updated_at": params[7],
                "paused_at": params[8],
                "next_resume_at": params[9],
                "last_error": params[10],
                "last_error_at": params[11],
                "requested_action": params[12],
                "requested_at": params[13],
                "heartbeat_at": params[14],
                "config_json": params[15],
                "last_event_id": params[16],
                "last_manifest_id": params[17],
                "projected_at": params[18],
            }
            self.runtime_controller[int(params[0])] = row
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_runtime_cycles WHERE cycle_id = %s"):
            assert params is not None
            row = self.runtime_cycles.get(str(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        if normalized.startswith("SELECT * FROM platform_runtime_controller_state WHERE controller_id = %s"):
            assert params is not None
            row = self.runtime_controller.get(int(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        raise AssertionError(f"Unexpected SQL in runtime projection test: {normalized}")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        return None


def test_from_dsn_uses_dict_row_factory(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_connection = object()

    def fake_connect(dsn: str, *, row_factory=None):
        captured["dsn"] = dsn
        captured["row_factory"] = row_factory
        return fake_connection

    monkeypatch.setattr(psycopg, "connect", fake_connect)

    repository = PostgresMutableTruthRepository.from_dsn("postgresql://user:secret@db.example/vinted_radar")

    assert repository.connection is fake_connection
    assert captured["dsn"] == "postgresql://user:secret@db.example/vinted_radar"
    assert captured["row_factory"] is dict_row



def test_runtime_snapshots_do_not_reference_missing_platform_events() -> None:
    connection = RuntimeProjectionConnection()
    repository = PostgresMutableTruthRepository(connection)

    cycle_id = repository.start_runtime_cycle(
        mode="batch",
        phase="starting",
        interval_seconds=None,
        state_probe_limit=2,
        config={"state_refresh_limit": 2},
    )
    repository.update_runtime_cycle_phase(cycle_id, phase="state_refresh")
    repository.complete_runtime_cycle(
        cycle_id,
        status="completed",
        phase="completed",
        discovery_run_id="run-123",
        state_probed_count=2,
        tracked_listings=5,
        freshness_counts={
            "first-pass-only": 1,
            "fresh-followup": 2,
            "aging-followup": 1,
            "stale-followup": 1,
        },
        state_refresh_summary={"status": "healthy"},
    )

    cycle = repository.runtime_cycle(cycle_id)
    controller = repository.runtime_controller_state(now="2026-03-21T00:00:00+00:00")

    assert cycle is not None
    assert cycle["status"] == "completed"
    assert cycle["last_event_id"] is None
    assert controller is not None
    assert controller["status"] == "idle"
    assert controller["latest_cycle_id"] == cycle_id
    assert controller["last_event_id"] is None
    assert connection.commits >= 3
