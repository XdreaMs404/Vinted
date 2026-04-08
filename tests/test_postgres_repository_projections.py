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
        self.catalogs: dict[int, dict[str, object]] = {}
        self.mutable_manifests: dict[str, dict[str, object]] = {}
        self.listing_identity: dict[int, dict[str, object]] = {}
        self.listing_presence_summary: dict[int, dict[str, object]] = {}
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
        if normalized.startswith("INSERT INTO platform_mutable_manifests"):
            assert params is not None
            manifest_id = str(params[0])
            self.mutable_manifests[manifest_id] = {
                "manifest_id": manifest_id,
                "event_id": str(params[1]),
                "event_type": str(params[2]),
                "aggregate_type": str(params[3]),
                "aggregate_id": str(params[4]),
                "occurred_at": str(params[5]),
                "manifest_type": str(params[6]),
                "projection_status": str(params[7]),
                "projected_at": params[8],
                "last_error": params[9],
                "metadata_json": json.loads(str(params[10])),
            }
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
        if normalized.startswith("INSERT INTO platform_listing_identity"):
            assert params is not None
            last_manifest_id = None if params[25] is None else str(params[25])
            if last_manifest_id is not None and last_manifest_id not in self.mutable_manifests:
                raise AssertionError(f"missing parent mutable manifest for listing identity row: {last_manifest_id}")
            self.listing_identity[int(params[0])] = {
                "listing_id": int(params[0]),
                "canonical_url": str(params[1]),
                "source_url": str(params[2]),
                "title": params[3],
                "brand": params[4],
                "size_label": params[5],
                "condition_label": params[6],
                "price_amount_cents": params[7],
                "price_currency": params[8],
                "total_price_amount_cents": params[9],
                "total_price_currency": params[10],
                "image_url": params[11],
                "favourite_count": params[12],
                "view_count": params[13],
                "user_id": params[14],
                "user_login": params[15],
                "user_profile_url": params[16],
                "created_at_ts": params[17],
                "primary_catalog_id": params[18],
                "primary_root_catalog_id": params[19],
                "first_seen_at": params[20],
                "last_seen_at": params[21],
                "first_seen_run_id": params[22],
                "last_seen_run_id": params[23],
                "last_event_id": params[24],
                "last_manifest_id": params[25],
                "projected_at": params[26],
            }
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_listing_identity WHERE listing_id = %s"):
            assert params is not None
            row = self.listing_identity.get(int(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        if normalized.startswith("INSERT INTO platform_listing_presence_summary"):
            assert params is not None
            last_manifest_id = None if params[16] is None else str(params[16])
            if last_manifest_id is not None and last_manifest_id not in self.mutable_manifests:
                raise AssertionError(f"missing parent mutable manifest for presence row: {last_manifest_id}")
            self.listing_presence_summary[int(params[0])] = {
                "listing_id": int(params[0]),
                "observation_count": int(params[1]),
                "total_sightings": int(params[2]),
                "first_seen_at": params[3],
                "last_seen_at": params[4],
                "average_revisit_hours": params[5],
                "last_observed_run_id": params[6],
                "freshness_bucket": params[7],
                "signal_completeness": int(params[8]),
                "partial_signal": bool(params[9]),
                "thin_signal": bool(params[10]),
                "has_estimated_publication": bool(params[11]),
                "price_band_code": str(params[12]),
                "price_band_label": str(params[13]),
                "price_band_sort_order": int(params[14]),
                "last_event_id": params[15],
                "last_manifest_id": params[16],
                "projected_at": params[17],
            }
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_listing_presence_summary WHERE listing_id = %s"):
            assert params is not None
            row = self.listing_presence_summary.get(int(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        if normalized.startswith("INSERT INTO platform_catalogs"):
            assert params is not None
            self.catalogs[int(params[0])] = {
                "catalog_id": int(params[0]),
                "root_catalog_id": int(params[1]),
                "root_title": str(params[2]),
                "parent_catalog_id": params[3],
                "title": str(params[4]),
                "code": params[5],
                "url": str(params[6]),
                "path": str(params[7]),
                "depth": int(params[8]),
                "is_leaf": bool(params[9]),
                "allow_browsing_subcategories": bool(params[10]),
                "order_index": params[11],
                "synced_at": params[12],
                "last_run_id": params[13],
                "last_event_id": params[14],
                "last_manifest_id": params[15],
                "projected_at": params[16],
            }
            return _QueryResult()
        if normalized.startswith("SELECT * FROM platform_catalogs WHERE catalog_id = %s"):
            assert params is not None
            row = self.catalogs.get(int(params[0]))
            return _QueryResult([] if row is None else [dict(row)])
        if normalized.startswith("SELECT listing_id FROM platform_listing_identity WHERE primary_catalog_id = %s"):
            assert params is not None
            catalog_id = int(params[0])
            rows = [
                {"listing_id": listing_id}
                for listing_id, row in sorted(self.listing_identity.items())
                if int(row.get("primary_catalog_id") or 0) == catalog_id
            ]
            return _QueryResult(rows)
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



def test_discovery_catalog_scan_completed_materializes_mutable_manifest_for_source_batch() -> None:
    connection = ProjectionConnection()
    repository = PostgresMutableTruthRepository(connection)
    connection.events["batch-event-1"] = {
        "event_id": "batch-event-1",
        "schema_version": 1,
        "event_type": "vinted.discovery.listing-seen.batch",
        "aggregate_type": "discovery-run",
        "aggregate_id": "run-123",
        "occurred_at": "2026-04-08T18:10:00+00:00",
        "producer": "vinted_radar.services.discovery",
        "partition_key": "1123",
        "payload_json": {},
        "metadata_json": {},
        "payload_checksum": "checksum",
    }
    connection.discovery_runs["run-123"] = {
        "run_id": "run-123",
        "started_at": "2026-04-08T18:00:00+00:00",
        "finished_at": None,
        "status": "running",
        "root_scope": "women",
        "page_limit": 1,
        "max_leaf_categories": 1,
        "request_delay_seconds": 0.0,
        "total_seed_catalogs": 0,
        "total_leaf_catalogs": 0,
        "scanned_leaf_catalogs": 0,
        "successful_scans": 0,
        "failed_scans": 0,
        "raw_listing_hits": 0,
        "unique_listing_hits": 0,
        "last_error": None,
        "last_event_id": None,
        "last_manifest_id": None,
        "projected_at": "2026-04-08T18:00:00+00:00",
    }

    repository.project_discovery_catalog_scan_completed(
        run_id="run-123",
        catalog={
            "catalog_id": 1123,
            "root_catalog_id": 1904,
            "root_title": "Femmes",
            "parent_catalog_id": 1904,
            "title": "Accessoires pour cheveux",
            "code": "hair-accessories",
            "url": "https://www.vinted.fr/catalog/1123-hair-accessories",
            "path": "Femmes > Accessoires pour cheveux",
            "depth": 1,
            "is_leaf": True,
            "allow_browsing_subcategories": True,
            "order_index": 10,
        },
        completed_at="2026-04-08T18:10:00+00:00",
        successful_pages=0,
        failed_pages=0,
        raw_listing_hits=1,
        unique_listing_hits=1,
        listing_rows=[
            {
                "run_id": "run-123",
                "observed_at": "2026-04-08T18:10:00+00:00",
                "catalog_id": 1123,
                "root_catalog_id": 1904,
                "listing_id": 5403391218,
                "canonical_url": "https://www.vinted.fr/items/5403391218-test",
                "source_url": "https://www.vinted.fr/items/5403391218-test?referrer=catalog",
                "title": "Accessoire test",
                "brand": "Zara",
                "size_label": None,
                "condition_label": "Très bon état",
                "price_amount_cents": 1500,
                "price_currency": "EUR",
                "total_price_amount_cents": 1650,
                "total_price_currency": "EUR",
                "image_url": "https://images/5403391218.webp",
                "source_event_id": "batch-event-1",
                "source_manifest_id": "manifest-1",
            }
        ],
        event_id="projection-event-3",
    )

    assert connection.mutable_manifests["manifest-1"]["event_id"] == "batch-event-1"
    assert connection.mutable_manifests["manifest-1"]["manifest_type"] == "listing-seen-evidence-batch"
    assert connection.listing_identity[5403391218]["last_manifest_id"] == "manifest-1"
    assert connection.listing_presence_summary[5403391218]["last_manifest_id"] == "manifest-1"
