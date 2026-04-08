from __future__ import annotations

import json

from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository


class _QueryResult:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class ProjectionConnection:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, object]] = {}
        self.discovery_runs: dict[str, dict[str, object]] = {}
        self.listing_current_state: dict[int, dict[str, object]] = {}
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> _QueryResult:
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO platform_events"):
            assert params is not None
            event_id = str(params[0])
            self.events.setdefault(
                event_id,
                {
                    "event_id": event_id,
                    "schema_version": int(params[1]),
                    "event_type": str(params[2]),
                    "aggregate_type": str(params[3]),
                    "aggregate_id": str(params[4]),
                    "occurred_at": str(params[5]),
                    "producer": str(params[6]),
                    "partition_key": str(params[7]),
                    "payload_json": json.loads(str(params[8])),
                    "metadata_json": json.loads(str(params[9])),
                    "payload_checksum": str(params[10]),
                },
            )
            return _QueryResult()
        if normalized.startswith("INSERT INTO platform_discovery_runs"):
            assert params is not None
            last_event_id = None if params[16] is None else str(params[16])
            if last_event_id is not None and last_event_id not in self.events:
                raise AssertionError(f"missing parent platform_event for discovery run row: {last_event_id}")
            self.discovery_runs[str(params[0])] = {
                "run_id": str(params[0]),
                "started_at": params[1],
                "finished_at": params[2],
                "status": params[3],
                "root_scope": params[4],
                "page_limit": params[5],
                "max_leaf_categories": params[6],
                "request_delay_seconds": params[7],
                "total_seed_catalogs": params[8],
                "total_leaf_catalogs": params[9],
                "scanned_leaf_catalogs": params[10],
                "successful_scans": params[11],
                "failed_scans": params[12],
                "raw_listing_hits": params[13],
                "unique_listing_hits": params[14],
                "last_error": params[15],
                "last_event_id": last_event_id,
                "last_manifest_id": params[17],
                "projected_at": params[18],
            }
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_discovery_runs WHERE run_id = %s"):
            assert params is not None
            row = self.discovery_runs.get(str(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        if normalized.startswith("INSERT INTO platform_listing_current_state"):
            assert params is not None
            last_event_id = None if params[18] is None else str(params[18])
            if last_event_id is not None and last_event_id not in self.events:
                raise AssertionError(f"missing parent platform_event for current-state row: {last_event_id}")
            self.listing_current_state[int(params[0])] = {
                "listing_id": int(params[0]),
                "state_code": str(params[1]),
                "state_label": str(params[2]),
                "basis_kind": str(params[3]),
                "confidence_label": str(params[4]),
                "confidence_score": float(params[5]),
                "sold_like": bool(params[6]),
                "seen_in_latest_primary_scan": bool(params[7]),
                "latest_primary_scan_run_id": params[8],
                "latest_primary_scan_at": params[9],
                "follow_up_miss_count": int(params[10]),
                "latest_follow_up_miss_at": params[11],
                "latest_probe_at": params[12],
                "latest_probe_response_status": params[13],
                "latest_probe_outcome": params[14],
                "latest_probe_error_message": params[15],
                "last_seen_age_hours": float(params[16]),
                "state_explanation_json": json.loads(str(params[17])),
                "last_event_id": last_event_id,
                "last_manifest_id": params[19],
                "projected_at": params[20],
            }
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_listing_current_state WHERE listing_id = %s"):
            assert params is not None
            row = self.listing_current_state.get(int(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        if normalized.startswith("SELECT * FROM platform_listing_identity WHERE listing_id = %s"):
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_listing_presence_summary WHERE listing_id = %s"):
            return _QueryResult()
        raise AssertionError(f"Unexpected SQL in projection test: {normalized}")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        return None


def test_discovery_run_started_materializes_parent_projection_event() -> None:
    connection = ProjectionConnection()
    repository = PostgresMutableTruthRepository(connection)

    repository.project_discovery_run_started(
        run_id="run-123",
        started_at="2026-04-08T18:00:00+00:00",
        root_scope="women",
        page_limit=1,
        max_leaf_categories=1,
        request_delay_seconds=0.0,
        event_id="projection-event-1",
    )

    assert "projection-event-1" in connection.events
    assert connection.events["projection-event-1"]["event_type"] == "vinted.mutable-truth.discovery-run.started"
    assert connection.discovery_runs["run-123"]["last_event_id"] == "projection-event-1"



def test_state_refresh_probe_projection_materializes_parent_projection_event() -> None:
    connection = ProjectionConnection()
    repository = PostgresMutableTruthRepository(connection)

    repository.project_state_refresh_probes(
        probe_rows=[
            {
                "listing_id": 9001,
                "probed_at": "2026-04-08T18:05:00+00:00",
                "response_status": 200,
                "probe_outcome": "active",
                "error_message": None,
            }
        ],
        projected_at="2026-04-08T18:05:00+00:00",
        event_id="projection-event-2",
    )

    assert "projection-event-2" in connection.events
    assert connection.events["projection-event-2"]["event_type"] == "vinted.mutable-truth.state-refresh.probes"
    assert connection.listing_current_state[9001]["last_event_id"] == "projection-event-2"
    assert connection.listing_current_state[9001]["latest_probe_outcome"] == "active"
