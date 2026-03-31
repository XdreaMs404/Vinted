from __future__ import annotations

from pathlib import Path

from scripts.verify_clickhouse_routes import (
    normalize_dashboard_payload_for_parity,
    normalize_detail_payload_for_parity,
    normalize_explorer_payload_for_parity,
    verify_clickhouse_routes,
)
from tests.clickhouse_product_test_support import make_clickhouse_product_client
from tests.test_dashboard import _seed_dashboard_db
from vinted_radar.dashboard import (
    DashboardFilters,
    ExplorerFilters,
    build_dashboard_payload,
    build_explorer_payload,
    build_listing_detail_payload,
)
from vinted_radar.query.overview_clickhouse import ClickHouseProductQueryAdapter
from vinted_radar.repository import RadarRepository


_NOW = "2026-03-19T12:00:00+00:00"


def _build_clickhouse_adapter(db_path: Path) -> ClickHouseProductQueryAdapter:
    repository = RadarRepository(db_path)
    repository.__enter__()
    return ClickHouseProductQueryAdapter(
        repository=repository,
        clickhouse_client=make_clickhouse_product_client(),
        database="vinted_radar",
    )


def test_clickhouse_dashboard_payload_matches_repository_parity_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    filters = DashboardFilters(state="active", limit=5)

    with RadarRepository(db_path) as repository:
        repository_payload = build_dashboard_payload(repository, filters=filters, now=_NOW)

    adapter = _build_clickhouse_adapter(db_path)
    try:
        clickhouse_payload = build_dashboard_payload(adapter, filters=filters, now=_NOW)
    finally:
        adapter.repository.__exit__(None, None, None)

    assert clickhouse_payload["request"]["primary_payload_source"] == "clickhouse.overview_snapshot"
    assert clickhouse_payload["featured_listings"][1]["latest_probe_display"] == "active (200)"
    assert normalize_dashboard_payload_for_parity(repository_payload) == normalize_dashboard_payload_for_parity(
        clickhouse_payload
    )


def test_clickhouse_explorer_payload_matches_repository_parity_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    filters = ExplorerFilters(root="Femmes", query="robe", sort="favourite_desc", page=1, page_size=2)

    with RadarRepository(db_path) as repository:
        repository_payload = build_explorer_payload(repository, filters=filters, now=_NOW)

    adapter = _build_clickhouse_adapter(db_path)
    try:
        clickhouse_payload = build_explorer_payload(adapter, filters=filters, now=_NOW)
    finally:
        adapter.repository.__exit__(None, None, None)

    assert [item["listing_id"] for item in clickhouse_payload["items"]] == [9003, 9001]
    assert clickhouse_payload["items"][1]["latest_probe_display"] == "active (200)"
    assert normalize_explorer_payload_for_parity(repository_payload) == normalize_explorer_payload_for_parity(
        clickhouse_payload
    )


def test_clickhouse_detail_payload_matches_repository_parity_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    explorer_filters = ExplorerFilters(root="Femmes", state="active", price_band="40_plus_eur", page_size=12)

    with RadarRepository(db_path) as repository:
        repository_payload = build_listing_detail_payload(
            repository,
            listing_id=9002,
            now=_NOW,
            explorer_filters=explorer_filters,
        )

    adapter = _build_clickhouse_adapter(db_path)
    try:
        clickhouse_payload = build_listing_detail_payload(
            adapter,
            listing_id=9002,
            now=_NOW,
            explorer_filters=explorer_filters,
        )
    finally:
        adapter.repository.__exit__(None, None, None)

    assert repository_payload is not None
    assert clickhouse_payload is not None
    assert clickhouse_payload["provenance"]["state_signal"]["source"] == "historique radar après probe dégradée"
    assert normalize_detail_payload_for_parity(repository_payload) == normalize_detail_payload_for_parity(
        clickhouse_payload
    )


def test_verify_clickhouse_routes_reports_parity_and_route_latency(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    proof = verify_clickhouse_routes(
        db_path=db_path,
        listing_id=9002,
        now=_NOW,
        timeout=5.0,
        clickhouse_client=make_clickhouse_product_client(),
        clickhouse_database="vinted_radar",
    )

    assert proof["repository"]["dashboard_source"] == "repository.overview_snapshot"
    assert proof["clickhouse"]["dashboard_source"] == "clickhouse.overview_snapshot"
    assert proof["parity"] == {
        "dashboard_api": "match",
        "explorer_api": "match",
        "detail_api": "match",
        "health": "match",
    }
    assert [route["label"] for route in proof["repository"]["routes"]] == [
        "dashboard_api",
        "explorer_api",
        "detail_api",
        "health",
    ]
    assert [route["label"] for route in proof["clickhouse"]["routes"]] == [
        "dashboard_api",
        "explorer_api",
        "detail_api",
        "health",
        "dashboard_html",
        "explorer_html",
        "detail_html",
    ]
    assert all(route["status"] == 200 for route in proof["repository"]["routes"])
    assert all(route["status"] == 200 for route in proof["clickhouse"]["routes"])
    assert proof["repository"]["total_duration_ms"] >= 0.0
    assert proof["clickhouse"]["total_duration_ms"] >= 0.0
