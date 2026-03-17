from __future__ import annotations

import json
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from vinted_radar.dashboard import DashboardApplication, DashboardFilters, build_dashboard_payload
from vinted_radar.repository import RadarRepository


def _seed_dashboard_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds, total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs, successful_scans, failed_scans, raw_listing_hits, unique_listing_hits)
            VALUES
              ('run-1', '2026-03-17T10:00:00+00:00', '2026-03-17T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0, 6, 2, 2, 2, 0, 3, 3),
              ('run-2', '2026-03-18T10:00:00+00:00', '2026-03-18T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0, 6, 2, 2, 2, 0, 2, 2),
              ('run-3', '2026-03-19T10:00:00+00:00', '2026-03-19T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0, 6, 2, 2, 2, 0, 2, 2);

            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00');

            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9001, 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', 2001, 1904, '2026-03-17T10:05:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Zara"}'),
              (9002, 'https://www.vinted.fr/items/9002-sold-probable', 'https://www.vinted.fr/items/9002-sold-probable?referrer=catalog', 'Sold probable robe', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9002.webp', 2001, 1904, '2026-03-17T10:06:00+00:00', '2026-03-17T10:06:00+00:00', 'run-1', '{"description_title": "Sandro"}'),
              (9003, 'https://www.vinted.fr/items/9003-new', 'https://www.vinted.fr/items/9003-new?referrer=catalog', 'New robe', 'Maje', 'L', 'Neuf', 4200, '€', 4550, '€', 'https://images/9003.webp', 2001, 1904, '2026-03-19T10:05:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Maje"}'),
              (9004, 'https://www.vinted.fr/items/9004-deleted', 'https://www.vinted.fr/items/9004-deleted?referrer=catalog', 'Deleted robe', 'Mango', 'L', 'Neuf', 2000, '€', 2200, '€', 'https://images/9004.webp', 2001, 1904, '2026-03-18T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{"description_title": "Mango"}');

            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES
              ('run-1', 9001, '2026-03-17T10:05:00+00:00', 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1250, '€', 1413, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-2', 9001, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1400, '€', 1550, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-3', 9001, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-1', 9002, '2026-03-17T10:06:00+00:00', 'https://www.vinted.fr/items/9002-sold-probable', 'https://www.vinted.fr/items/9002-sold-probable?referrer=catalog', 2001, 1, 2, 1, 'Sold probable robe', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9002.webp', '{"overlay_title": "Sold probable robe"}'),
              ('run-3', 9003, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9003-new', 'https://www.vinted.fr/items/9003-new?referrer=catalog', 2001, 1, 3, 1, 'New robe', 'Maje', 'L', 'Neuf', 4200, '€', 4550, '€', 'https://images/9003.webp', '{"overlay_title": "New robe"}'),
              ('run-2', 9004, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9004-deleted', 'https://www.vinted.fr/items/9004-deleted?referrer=catalog', 2001, 1, 4, 1, 'Deleted robe', 'Mango', 'L', 'Neuf', 2000, '€', 2200, '€', 'https://images/9004.webp', '{"overlay_title": "Deleted robe"}');

            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-17T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-2', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-18T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-3', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-19T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL);
            """
        )
        repository.record_item_page_probe(
            listing_id=9001,
            probed_at="2026-03-19T11:00:00+00:00",
            requested_url="https://www.vinted.fr/items/9001-active",
            final_url="https://www.vinted.fr/items/9001-active",
            response_status=200,
            probe_outcome="active",
            detail={"reason": "buy_signal_open", "response_status": 200},
            error_message=None,
        )
        repository.record_item_page_probe(
            listing_id=9004,
            probed_at="2026-03-19T11:10:00+00:00",
            requested_url="https://www.vinted.fr/items/9004-deleted",
            final_url="https://www.vinted.fr/items/9004-deleted",
            response_status=404,
            probe_outcome="deleted",
            detail={"reason": "http_404", "response_status": 404},
            error_message=None,
        )
        cycle_id = repository.start_runtime_cycle(
            mode="continuous",
            phase="starting",
            interval_seconds=900.0,
            state_probe_limit=4,
            config={"state_refresh_limit": 4, "page_limit": 1},
        )
        repository.complete_runtime_cycle(
            cycle_id,
            status="completed",
            phase="completed",
            discovery_run_id="run-3",
            state_probed_count=2,
            tracked_listings=4,
            freshness_counts={
                "first-pass-only": 2,
                "fresh-followup": 1,
                "aging-followup": 0,
                "stale-followup": 1,
            },
            last_error=None,
        )
        conn.commit()


def _call_app(app: DashboardApplication, path: str, query: str = "") -> tuple[str, bytes, dict[str, str]]:
    environ: dict[str, str] = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    environ["QUERY_STRING"] = query
    captured: dict[str, str] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        for key, value in headers:
            captured[key] = value

    body = b"".join(app(environ, start_response))
    return captured["status"], body, captured


def test_dashboard_payload_keeps_summary_filters_and_detail_separate(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_dashboard_payload(
            repository,
            filters=DashboardFilters(root="Femmes", state="active", listing_id=9002, limit=5),
            now="2026-03-19T12:00:00+00:00",
        )

    assert payload["results"]["total_listings"] == 4
    assert payload["results"]["filtered_listings"] == 2
    assert payload["results"]["selected_listing_visible"] is False
    assert payload["market_summary"]["performing_segments"] == []
    assert payload["detail"]["listing_id"] == 9002
    assert payload["detail"]["state_code"] == "sold_probable"
    assert payload["runtime"]["latest_cycle"]["status"] == "completed"
    assert payload["diagnostics"]["runtime_api"] == "/api/runtime"
    assert any(item["label"] == "Follow-up misses" for item in payload["detail"]["transitions"])
    assert payload["filters"]["available"]["roots"][0]["value"] == "all"


def test_dashboard_application_serves_html_and_json_views(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    app = DashboardApplication(db_path, now="2026-03-19T12:00:00+00:00")

    html_status, html_body, html_headers = _call_app(app, "/")
    api_status, api_body, api_headers = _call_app(app, "/api/dashboard", "state=active")
    runtime_status, runtime_body, runtime_headers = _call_app(app, "/api/runtime")
    detail_status, detail_body, detail_headers = _call_app(app, "/api/listings/9002")
    health_status, health_body, _ = _call_app(app, "/health")

    assert html_status == "200 OK"
    assert html_headers["Content-Type"].startswith("text/html")
    assert b"Market summary first" in html_body
    assert b"Demand proof" in html_body
    assert b"Runtime payload" in html_body

    assert api_status == "200 OK"
    assert api_headers["Content-Type"].startswith("application/json")
    api_payload = json.loads(api_body)
    assert api_payload["results"]["filtered_listings"] == 2
    assert api_payload["rankings"]["demand"][0]["listing_id"] == 9001

    assert runtime_status == "200 OK"
    assert runtime_headers["Content-Type"].startswith("application/json")
    runtime_payload = json.loads(runtime_body)
    assert runtime_payload["latest_cycle"]["status"] == "completed"
    assert runtime_payload["latest_cycle"]["discovery_run_id"] == "run-3"

    assert detail_status == "200 OK"
    assert detail_headers["Content-Type"].startswith("application/json")
    detail_payload = json.loads(detail_body)
    assert detail_payload["listing_id"] == 9002
    assert detail_payload["state_code"] == "sold_probable"

    assert health_status == "200 OK"
    health_payload = json.loads(health_body)
    assert health_payload["tracked_listings"] == 4
    assert health_payload["latest_runtime_cycle"]["status"] == "completed"
