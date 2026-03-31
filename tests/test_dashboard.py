from __future__ import annotations

import json
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from tests.clickhouse_product_test_support import make_clickhouse_product_client
from vinted_radar.dashboard import (
    DashboardApplication,
    DashboardFilters,
    ExplorerFilters,
    _escape,
    build_dashboard_payload,
    build_explorer_payload,
    build_listing_detail_payload,
    build_runtime_payload,
)
from vinted_radar.repository import RadarRepository
from vinted_radar.serving import RouteContext


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

            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9001, 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', 11, 120, 41, 'alice', 'https://www.vinted.fr/member/41', 1711101600, 2001, 1904, '2026-03-17T10:05:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Zara"}'),
              (9002, 'https://www.vinted.fr/items/9002-sold-probable', 'https://www.vinted.fr/items/9002-sold-probable?referrer=catalog', 'Sold probable robe', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9002.webp', 2, 35, 42, 'bruno', 'https://www.vinted.fr/member/42', 1711015200, 2001, 1904, '2026-03-17T10:06:00+00:00', '2026-03-17T10:06:00+00:00', 'run-1', '{"description_title": "Sandro"}'),
              (9003, 'https://www.vinted.fr/items/9003-new', 'https://www.vinted.fr/items/9003-new?referrer=catalog', 'New robe', 'Maje', 'L', 'Neuf', 4200, '€', 4550, '€', 'https://images/9003.webp', 41, 650, 43, 'claire', 'https://www.vinted.fr/member/43', 1711188000, 2001, 1904, '2026-03-19T10:05:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Maje"}'),
              (9004, 'https://www.vinted.fr/items/9004-deleted', 'https://www.vinted.fr/items/9004-deleted?referrer=catalog', 'Deleted robe', 'Mango', 'L', 'Neuf', 2000, '€', 2200, '€', 'https://images/9004.webp', NULL, NULL, NULL, NULL, NULL, NULL, 2001, 1904, '2026-03-18T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{"description_title": "Mango"}');

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
            listing_id=9002,
            probed_at="2026-03-19T11:05:00+00:00",
            requested_url="https://www.vinted.fr/items/9002-sold-probable",
            final_url="https://www.vinted.fr/items/9002-sold-probable",
            response_status=403,
            probe_outcome="unknown",
            detail={"reason": "anti_bot_challenge", "response_status": 403, "challenge_markers": ["just a moment"]},
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
            state_probed_count=3,
            tracked_listings=4,
            freshness_counts={
                "first-pass-only": 2,
                "fresh-followup": 1,
                "aging-followup": 0,
                "stale-followup": 1,
            },
            last_error=None,
            state_refresh_summary={
                "status": "degraded",
                "probed_count": 3,
                "direct_signal_count": 2,
                "inconclusive_probe_count": 0,
                "degraded_probe_count": 1,
                "anti_bot_challenge_count": 1,
                "http_error_count": 0,
                "transport_error_count": 0,
                "degraded_listing_ids": [9002],
            },
        )
        repository.set_runtime_controller_state(
            status="scheduled",
            phase="waiting",
            mode="continuous",
            active_cycle_id=None,
            latest_cycle_id=cycle_id,
            interval_seconds=900.0,
            updated_at="2026-03-19T11:55:00+00:00",
            paused_at=None,
            next_resume_at="2026-03-19T12:05:00+00:00",
            requested_action="none",
            requested_at=None,
            config={"state_refresh_limit": 4, "page_limit": 1},
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


def test_dashboard_payload_uses_sql_overview_contract_and_honesty_notes(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_dashboard_payload(
            repository,
            filters=DashboardFilters(state="active", limit=5),
            now="2026-03-19T12:00:00+00:00",
        )

    assert payload["request"]["primary_payload_source"] == "repository.overview_snapshot"
    assert payload["request"]["legacy_query_filters"]["state"] == "active"
    assert payload["summary"]["inventory"]["tracked_listings"] == 4
    assert payload["summary"]["inventory"]["sold_like_count"] == 1
    assert payload["summary"]["inventory"]["comparison_support_threshold"] == 3
    assert payload["summary"]["honesty"]["inferred_state_count"] == 1
    assert payload["summary"]["honesty"]["estimated_publication_count"] == 3
    assert payload["summary"]["freshness"]["current_runtime_status"] == "scheduled"
    assert payload["summary"]["freshness"]["acquisition_status"] == "degraded"
    assert payload["summary"]["freshness"]["recent_probe_issue_count"] == 1
    assert payload["summary"]["freshness"]["latest_runtime_cycle_status"] == "completed"
    assert payload["comparisons"]["category"]["status"] == "ok"
    assert payload["comparisons"]["brand"]["status"] == "thin-support"
    assert payload["comparisons"]["category"]["rows"][0]["drilldown"]["filters"] == {"catalog_id": 2001}
    assert payload["comparisons"]["brand"]["rows"][0]["honesty"]["low_support"] is True
    assert [note["slug"] for note in payload["honesty_notes"]] == [
        "low-support-rule",
        "inferred-states",
        "estimated-publication",
        "degraded-state-refresh",
    ]
    assert [item["listing_id"] for item in payload["featured_listings"]] == [9003, 9001, 9004, 9002]
    assert payload["featured_listings"][0]["detail_href"] == "/listings/9003"
    assert payload["featured_listings"][0]["detail_api"] == "/api/listings/9003"
    assert payload["featured_listings"][0]["explorer_href"] == "/explorer?q=9003"
    assert payload["diagnostics"]["dashboard_api"] == "/api/dashboard"
    assert payload["diagnostics"]["runtime"] == "/runtime"
    assert payload["diagnostics"]["runtime_api"] == "/api/runtime"
    assert payload["diagnostics"]["explorer_api"] == "/api/explorer"
    assert payload["diagnostics"]["listing_detail_examples"] == [
        "/listings/9003",
        "/listings/9001",
        "/listings/9004",
        "/listings/9002",
    ]


def test_dashboard_payload_reuses_one_generated_at_for_repository_calls() -> None:
    captured: dict[str, str | None] = {}

    class _RepositoryStub:
        db_path = Path("data/stub.db")

        def overview_snapshot(self, *, now: str | None, comparison_limit: int) -> dict[str, object]:
            captured["overview_now"] = now
            return {
                "generated_at": now,
                "db_path": str(self.db_path),
                "summary": {
                    "inventory": {"tracked_listings": 0, "sold_like_count": 0, "comparison_support_threshold": 3, "state_counts": {}},
                    "honesty": {"observed_state_count": 0, "inferred_state_count": 0, "unknown_state_count": 0, "partial_signal_count": 0, "thin_signal_count": 0, "estimated_publication_count": 0, "missing_estimated_publication_count": 0, "confidence_counts": {"high": 0, "medium": 0, "low": 0}},
                    "freshness": {"acquisition_status": None, "acquisition_reasons": [], "recent_probe_issue_count": 0, "recent_inconclusive_probe_count": 0, "recent_probe_issues": [], "recent_acquisition_failure_count": 0, "recent_acquisition_failures": []},
                },
                "comparisons": {},
                "coverage": None,
                "runtime": {"acquisition": {"status": "healthy", "reasons": []}},
            }

        def listing_explorer_page(self, *, page: int, page_size: int, sort: str, now: str | None) -> dict[str, object]:
            captured["page_now"] = now
            return {"items": []}

    payload = build_dashboard_payload(_RepositoryStub(), filters=DashboardFilters())

    assert captured["overview_now"] is not None
    assert captured["overview_now"] == captured["page_now"]
    assert payload["generated_at"] == captured["overview_now"]



def test_escape_repairs_common_utf8_mojibake_for_visible_html() -> None:
    escaped = _escape("Femmes > VÃªtements > Porte-clÃ©s")

    assert "Vêtements" in escaped
    assert "Porte-clés" in escaped
    assert "VÃªtements" not in escaped



def test_explorer_payload_pages_tracked_listings_from_sql(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_explorer_payload(
            repository,
            filters=ExplorerFilters(root="Femmes", query="robe", page=1, page_size=2),
            now="2026-03-19T12:00:00+00:00",
        )

    assert payload["results"]["total_listings"] == 4
    assert payload["summary"]["inventory"]["matched_listings"] == 4
    assert payload["notes"]["acquisition_status"] == "degraded"
    assert payload["results"]["page"] == 1
    assert payload["results"]["page_size"] == 2
    assert payload["results"]["has_next_page"] is True
    assert len(payload["items"]) == 2
    assert [item["listing_id"] for item in payload["items"]] == [9003, 9001]
    assert payload["comparisons"]["brand"]["status"] == "thin-support"
    assert payload["items"][0]["freshness_bucket"] == "first-pass-only"
    assert payload["items"][1]["freshness_bucket"] == "fresh-followup"
    assert payload["items"][0]["visible_likes_display"] == "41"
    assert payload["items"][0]["seller_display"] == "claire"
    assert payload["items"][0]["estimated_publication_at"] == "2024-03-23T10:00:00+00:00"
    assert payload["items"][0]["detail_href"] == "/listings/9003?root=Femmes&q=robe&page_size=2"
    assert payload["filters"]["available"]["catalogs"][1]["catalog_id"] == 2001
    assert payload["filters"]["available"]["brands"][1]["value"] == "Maje"


def test_explorer_payload_reuses_one_generated_at_for_repository_calls() -> None:
    captured: dict[str, str | None] = {}

    class _RepositoryStub:
        db_path = Path("data/stub.db")

        def explorer_filter_options(self, *, now: str | None) -> dict[str, object]:
            captured["options_now"] = now
            return {
                "tracked_listings": 0,
                "roots": [{"value": "all", "label": "All roots"}],
                "catalogs": [{"value": "", "label": "All catalogs"}],
                "brands": [{"value": "all", "label": "All brands"}],
                "conditions": [{"value": "all", "label": "All conditions"}],
                "price_bands": [{"value": "all", "label": "All price bands"}],
                "states": [{"value": "all", "label": "All radar states"}],
                "sorts": [{"value": "last_seen_desc", "label": "Recently seen"}],
            }

        def explorer_snapshot(self, *, now: str | None, **kwargs) -> dict[str, object]:
            captured["snapshot_now"] = now
            return {
                "summary": {"inventory": {"matched_listings": 0, "sold_like_count": 0, "comparison_support_threshold": 3, "average_price_amount_cents": None, "state_counts": {}}, "honesty": {"observed_state_count": 0, "inferred_state_count": 0, "unknown_state_count": 0, "partial_signal_count": 0, "thin_signal_count": 0, "estimated_publication_count": 0, "missing_estimated_publication_count": 0}},
                "comparisons": {},
                "page": {"total_listings": 0, "total_pages": 0, "page": 1, "page_size": 50, "sort": "last_seen_desc", "has_previous_page": False, "has_next_page": False, "items": []},
            }

        def runtime_status(self, *, limit: int, now: str | None) -> dict[str, object]:
            captured["runtime_now"] = now
            return {"acquisition": {"status": "healthy", "reasons": []}}

    payload = build_explorer_payload(_RepositoryStub(), filters=ExplorerFilters())

    assert captured["options_now"] is not None
    assert captured["options_now"] == captured["snapshot_now"] == captured["runtime_now"]
    assert payload["generated_at"] == captured["options_now"]


def test_explorer_payload_applies_sql_brand_condition_and_sort_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_explorer_payload(
            repository,
            filters=ExplorerFilters(
                root="Femmes",
                brand="Zara",
                condition="Très bon état",
                sort="price_asc",
                page=1,
                page_size=5,
            ),
            now="2026-03-19T12:00:00+00:00",
        )

    assert payload["results"]["total_listings"] == 1
    assert payload["results"]["sort"] == "price_asc"
    assert [item["listing_id"] for item in payload["items"]] == [9001]
    assert payload["items"][0]["seller_display"] == "alice"
    assert payload["items"][0]["visible_views_display"] == "120"
    assert payload["notes"]["estimated_publication"].startswith("La publication estimée")



def test_explorer_payload_preserves_current_slice_in_comparison_links(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_explorer_payload(
            repository,
            filters=ExplorerFilters(root="Femmes", query="robe", sort="view_desc", page_size=2),
            now="2026-03-19T12:00:00+00:00",
        )

    brand_row = payload["comparisons"]["brand"]["rows"][0]
    assert brand_row["drilldown"]["href"] == "/explorer?root=Femmes&q=robe&sort=view_desc&page_size=2&brand=Maje"



def test_listing_detail_payload_exposes_back_link_for_explorer_context(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_listing_detail_payload(
            repository,
            listing_id=9001,
            now="2026-03-19T12:00:00+00:00",
            explorer_filters=ExplorerFilters(root="Femmes", brand="Zara", page=2, page_size=12),
        )

    assert payload is not None
    assert payload["explorer_context"]["back_href"] == "/explorer?root=Femmes&brand=Zara&page=2&page_size=12"
    assert payload["explorer_context"]["summary"].startswith("Vue active —")
    assert payload["diagnostics"]["explorer_back"] == "/explorer?root=Femmes&brand=Zara&page=2&page_size=12"



def test_listing_detail_payload_exposes_narrative_and_provenance_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_listing_detail_payload(
            repository,
            listing_id=9002,
            now="2026-03-19T12:00:00+00:00",
            explorer_filters=ExplorerFilters(root="Femmes", state="active", price_band="40_plus_eur", page_size=12),
        )

    assert payload is not None
    assert payload["narrative"]["headline"].startswith("Lecture radar")
    assert payload["narrative"]["summary"].startswith("L’annonce a disparu après")
    assert payload["narrative"]["explorer_angle"].startswith("Lecture ouverte depuis Vue active —")
    assert [item["slug"] for item in payload["narrative"]["highlights"]] == [
        "radar_read",
        "market_read",
        "timing",
        "visibility",
    ]
    assert any(note["slug"] == "inferred-state" for note in payload["narrative"]["risk_notes"])
    assert any(note["slug"] == "estimated-publication" for note in payload["narrative"]["risk_notes"])
    assert any(note["slug"] == "degraded-probe" for note in payload["narrative"]["risk_notes"])
    assert payload["provenance"]["state_signal"]["kind"] == "inferred"
    assert payload["provenance"]["state_signal"]["source"] == "historique radar après probe dégradée"
    assert payload["provenance"]["publication_timing"]["kind"] == "estimated"
    assert payload["provenance"]["radar_window"]["kind"] == "radar"
    assert payload["state_explanation"]["reasons"]
    assert payload["score_explanation"]["factors"]["follow_up_miss"] > 0



def test_listing_detail_payload_scopes_scoring_to_target_listing(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    original = RadarRepository.listing_state_inputs

    def _guard(self, *, now: str | None = None, listing_id: int | None = None) -> list[dict[str, object]]:
        if listing_id is None:
            raise AssertionError("detail payload should not request full listing state inputs")
        return original(self, now=now, listing_id=listing_id)

    monkeypatch.setattr(RadarRepository, "listing_state_inputs", _guard)

    with RadarRepository(db_path) as repository:
        payload = build_listing_detail_payload(
            repository,
            listing_id=9002,
            now="2026-03-19T12:00:00+00:00",
        )

    assert payload is not None
    assert payload["listing_id"] == 9002



def test_listing_detail_payload_preserves_price_context_without_full_score_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        repository.connection.executescript(
            """
            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9011, 'https://www.vinted.fr/items/9011-active', 'https://www.vinted.fr/items/9011-active?referrer=catalog', 'Active robe peer 1', 'Zara', 'S', 'Très bon état', 1000, '€', 1150, '€', 'https://images/9011.webp', 7, 80, 51, 'alice-bis', 'https://www.vinted.fr/member/51', 1711187000, 2001, 1904, '2026-03-19T10:01:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Zara peer 1"}'),
              (9012, 'https://www.vinted.fr/items/9012-active', 'https://www.vinted.fr/items/9012-active?referrer=catalog', 'Active robe peer 2', 'Zara', 'L', 'Très bon état', 1700, '€', 1850, '€', 'https://images/9012.webp', 8, 90, 52, 'alice-ter', 'https://www.vinted.fr/member/52', 1711187100, 2001, 1904, '2026-03-19T10:02:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Zara peer 2"}'),
              (9013, 'https://www.vinted.fr/items/9013-active', 'https://www.vinted.fr/items/9013-active?referrer=catalog', 'Active robe peer 3', 'Zara', 'M', 'Très bon état', 1900, '€', 2050, '€', 'https://images/9013.webp', 9, 95, 53, 'alice-quatre', 'https://www.vinted.fr/member/53', 1711187200, 2001, 1904, '2026-03-19T10:03:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Zara peer 3"}');

            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES
              ('run-3', 9011, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9011-active', 'https://www.vinted.fr/items/9011-active?referrer=catalog', 2001, 1, 5, 1, 'Active robe peer 1', 'Zara', 'S', 'Très bon état', 1000, '€', 1150, '€', 'https://images/9011.webp', '{"overlay_title": "Active robe peer 1"}'),
              ('run-3', 9012, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9012-active', 'https://www.vinted.fr/items/9012-active?referrer=catalog', 2001, 1, 6, 1, 'Active robe peer 2', 'Zara', 'L', 'Très bon état', 1700, '€', 1850, '€', 'https://images/9012.webp', '{"overlay_title": "Active robe peer 2"}'),
              ('run-3', 9013, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9013-active', 'https://www.vinted.fr/items/9013-active?referrer=catalog', 2001, 1, 7, 1, 'Active robe peer 3', 'Zara', 'M', 'Très bon état', 1900, '€', 2050, '€', 'https://images/9013.webp', '{"overlay_title": "Active robe peer 3"}');
            """
        )

    with RadarRepository(db_path) as repository:
        payload = build_listing_detail_payload(
            repository,
            listing_id=9001,
            now="2026-03-19T12:00:00+00:00",
        )

    assert payload is not None
    assert payload["score_explanation"]["context"] is not None
    assert payload["score_explanation"]["context"]["label"] == "catalog_brand_condition"
    assert payload["score_explanation"]["context"]["sample_size"] == 4



def test_runtime_payload_surfaces_controller_truth_separately_from_latest_cycle(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        payload = build_runtime_payload(repository, now="2026-03-19T12:00:00+00:00")

    assert payload["summary"]["status"] == "scheduled"
    assert payload["summary"]["phase"] == "waiting"
    assert payload["summary"]["next_resume_at"] == "2026-03-19T12:05:00+00:00"
    assert payload["summary"]["acquisition_status"] == "degraded"
    assert payload["runtime"]["latest_cycle"]["status"] == "completed"
    assert payload["acquisition"]["latest_state_refresh_summary"]["anti_bot_challenge_count"] == 1
    assert payload["diagnostics"]["runtime"] == "/runtime"



def test_dashboard_application_serves_html_and_json_views(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    app = DashboardApplication(db_path, now="2026-03-19T12:00:00+00:00")

    html_status, html_body, html_headers = _call_app(app, "/")
    api_status, api_body, api_headers = _call_app(app, "/api/dashboard", "state=active")
    explorer_status, explorer_body, explorer_headers = _call_app(app, "/explorer", "q=robe&page_size=2&sort=favourite_desc")
    explorer_api_status, explorer_api_body, explorer_api_headers = _call_app(app, "/api/explorer", "q=robe&page_size=2&sort=favourite_desc")
    runtime_page_status, runtime_page_body, runtime_page_headers = _call_app(app, "/runtime")
    runtime_status, runtime_body, runtime_headers = _call_app(app, "/api/runtime")
    detail_page_status, detail_page_body, detail_page_headers = _call_app(app, "/listings/9002")
    detail_status, detail_body, detail_headers = _call_app(app, "/api/listings/9002")
    health_status, health_body, _ = _call_app(app, "/health")

    assert html_status == "200 OK"
    assert html_headers["Content-Type"].startswith("text/html")
    html_text = html_body.decode("utf-8")
    assert "Vinted Radar" in html_text
    assert "Navigation principale du produit" in html_text
    assert '<html lang="fr">' in html_text
    assert "Ce qui bouge maintenant sur le radar Vinted." in html_text
    assert "Niveau d’honnêteté du signal" in html_text
    assert "acquisition dégradée" in html_text
    assert "Comparaisons à lire avec contexte" in html_text
    assert "JSON aperçu" in html_text
    assert 'aria-current="page">Accueil<' in html_text

    assert api_status == "200 OK"
    assert api_headers["Content-Type"].startswith("application/json")
    api_payload = json.loads(api_body)
    assert api_payload["request"]["legacy_query_filters"]["state"] == "active"
    assert api_payload["summary"]["inventory"]["tracked_listings"] == 4
    assert api_payload["summary"]["freshness"]["current_runtime_status"] == "scheduled"
    assert api_payload["summary"]["freshness"]["acquisition_status"] == "degraded"
    assert api_payload["comparisons"]["category"]["rows"][0]["label"] == "Femmes > Robes"
    assert api_payload["featured_listings"][0]["detail_api"] == "/api/listings/9003"

    assert explorer_status == "200 OK"
    assert explorer_headers["Content-Type"].startswith("text/html")
    explorer_text = explorer_body.decode("utf-8")
    assert "Navigation principale du produit" in explorer_text
    assert "acquisition dégradée" in explorer_text
    assert "Filtres d’exploration" in explorer_text
    assert "Comparer la tranche affichée" in explorer_text
    assert "Annonces du corpus" in explorer_text
    assert "JSON explorateur" in explorer_text
    assert "class=\"explorer-item\"" in explorer_text
    assert "min-width: 1320px" not in explorer_text

    assert explorer_api_status == "200 OK"
    assert explorer_api_headers["Content-Type"].startswith("application/json")
    explorer_payload = json.loads(explorer_api_body)
    assert explorer_payload["results"]["total_listings"] == 4
    assert explorer_payload["summary"]["inventory"]["matched_listings"] == 4
    assert explorer_payload["notes"]["acquisition_status"] == "degraded"
    assert explorer_payload["results"]["page_size"] == 2
    assert explorer_payload["results"]["sort"] == "favourite_desc"
    assert len(explorer_payload["items"]) == 2
    assert [item["listing_id"] for item in explorer_payload["items"]] == [9003, 9001]
    assert explorer_payload["items"][0]["visible_likes_display"] == "41"
    assert explorer_payload["items"][0]["detail_api"] == "/api/listings/9003?q=robe&sort=favourite_desc&page_size=2"

    assert runtime_page_status == "200 OK"
    assert runtime_page_headers["Content-Type"].startswith("text/html")
    runtime_page_text = runtime_page_body.decode("utf-8")
    assert "Navigation principale du produit" in runtime_page_text
    assert "Le contrôleur vivant du radar" in runtime_page_text
    assert "Santé d’acquisition" in runtime_page_text
    assert "Cycles récents" in runtime_page_text
    assert "JSON runtime" in runtime_page_text

    assert runtime_status == "200 OK"
    assert runtime_headers["Content-Type"].startswith("application/json")
    runtime_payload = json.loads(runtime_body)
    assert runtime_payload["status"] == "scheduled"
    assert runtime_payload["phase"] == "waiting"
    assert runtime_payload["next_resume_at"] == "2026-03-19T12:05:00+00:00"
    assert runtime_payload["latest_cycle"]["status"] == "completed"
    assert runtime_payload["latest_cycle"]["discovery_run_id"] == "run-3"
    assert runtime_payload["acquisition"]["status"] == "degraded"
    assert runtime_payload["acquisition"]["latest_state_refresh_summary"]["anti_bot_challenge_count"] == 1

    assert detail_page_status == "200 OK"
    assert detail_page_headers["Content-Type"].startswith("text/html")
    detail_page_text = detail_page_body.decode("utf-8")
    assert "Navigation principale du produit" in detail_page_text
    assert "Fiche annonce" in detail_page_text
    assert "Ce que le radar voit d’abord" in detail_page_text
    assert "Preuves techniques et détails" in detail_page_text
    assert "Lecture radar : probablement déjà partie" in detail_page_text

    assert detail_status == "200 OK"
    assert detail_headers["Content-Type"].startswith("application/json")
    detail_payload = json.loads(detail_body)
    assert detail_payload["listing_id"] == 9002
    assert detail_payload["state_code"] == "sold_probable"
    assert detail_payload["seller"]["login"] == "bruno"
    assert detail_payload["narrative"]["headline"].startswith("Lecture radar")
    assert any(note["slug"] == "degraded-probe" for note in detail_payload["narrative"]["risk_notes"])
    assert detail_payload["provenance"]["state_signal"]["kind"] == "inferred"
    assert detail_payload["provenance"]["state_signal"]["source"] == "historique radar après probe dégradée"

    assert health_status == "200 OK"
    health_payload = json.loads(health_body)
    assert health_payload["tracked_listings"] == 4
    assert health_payload["current_runtime_status"] == "scheduled"
    assert health_payload["latest_runtime_cycle"]["status"] == "completed"
    assert health_payload["acquisition"]["status"] == "degraded"
    assert health_payload["acquisition"]["latest_state_refresh_summary"]["anti_bot_challenge_count"] == 1
    assert health_payload["serving"]["home"] == "/"
    assert health_payload["serving"]["detail_example"] == "/listings/1"


def test_dashboard_application_serves_clickhouse_backed_product_routes(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    app = DashboardApplication(
        db_path,
        now="2026-03-19T12:00:00+00:00",
        clickhouse_client=make_clickhouse_product_client(),
        clickhouse_database="vinted_radar",
    )

    dashboard_status, dashboard_body, dashboard_headers = _call_app(app, "/api/dashboard", "state=active")
    explorer_status, explorer_body, explorer_headers = _call_app(app, "/api/explorer", "q=robe&page_size=2")
    detail_status, detail_body, detail_headers = _call_app(app, "/api/listings/9002")
    health_status, health_body, _ = _call_app(app, "/health")

    assert dashboard_status == "200 OK"
    assert dashboard_headers["Content-Type"].startswith("application/json")
    dashboard_payload = json.loads(dashboard_body)
    assert dashboard_payload["request"]["primary_payload_source"] == "clickhouse.overview_snapshot"
    assert dashboard_payload["summary"]["inventory"]["tracked_listings"] == 4
    assert dashboard_payload["featured_listings"][0]["detail_api"] == "/api/listings/9003"

    assert explorer_status == "200 OK"
    assert explorer_headers["Content-Type"].startswith("application/json")
    explorer_payload = json.loads(explorer_body)
    assert explorer_payload["results"]["total_listings"] == 4
    assert [item["listing_id"] for item in explorer_payload["items"]] == [9003, 9001]

    assert detail_status == "200 OK"
    assert detail_headers["Content-Type"].startswith("application/json")
    detail_payload = json.loads(detail_body)
    assert detail_payload["listing_id"] == 9002
    assert detail_payload["state_code"] == "sold_probable"
    assert detail_payload["provenance"]["state_signal"]["source"] == "historique radar après probe dégradée"

    assert health_status == "200 OK"
    health_payload = json.loads(health_body)
    assert health_payload["tracked_listings"] == 4
    assert health_payload["acquisition"]["status"] == "degraded"



def test_dashboard_application_supports_base_path_links_and_prefixed_routes(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)
    route_context = RouteContext.from_options(base_path="/radar", public_base_url="https://radar.example.com/radar")

    with RadarRepository(db_path) as repository:
        dashboard_payload = build_dashboard_payload(
            repository,
            filters=DashboardFilters(),
            now="2026-03-19T12:00:00+00:00",
            route_context=route_context,
        )
        explorer_payload = build_explorer_payload(
            repository,
            filters=ExplorerFilters(page_size=2),
            now="2026-03-19T12:00:00+00:00",
            route_context=route_context,
        )
        runtime_payload = build_runtime_payload(
            repository,
            now="2026-03-19T12:00:00+00:00",
            route_context=route_context,
        )

    assert dashboard_payload["diagnostics"]["home"] == "/radar/"
    assert dashboard_payload["featured_listings"][0]["detail_href"] == "/radar/listings/9003"
    assert explorer_payload["diagnostics"]["explorer"] == "/radar/explorer"
    assert explorer_payload["items"][0]["detail_api"] == "/radar/api/listings/9003?page_size=2"
    assert runtime_payload["diagnostics"]["runtime"] == "/radar/runtime"

    app = DashboardApplication(
        db_path,
        now="2026-03-19T12:00:00+00:00",
        base_path="/radar",
        public_base_url="https://radar.example.com/radar",
    )
    prefixed_status, prefixed_body, _ = _call_app(app, "/radar/")
    prefixed_detail_status, prefixed_detail_body, _ = _call_app(app, "/radar/listings/9002")
    prefixed_health_status, prefixed_health_body, _ = _call_app(app, "/radar/health")

    assert prefixed_status == "200 OK"
    assert b'Navigation principale du produit' in prefixed_body
    assert b'href="/radar/explorer"' in prefixed_body
    assert b'href="/radar/runtime"' in prefixed_body
    assert prefixed_detail_status == "200 OK"
    assert b'href="/radar/api/listings/9002"' in prefixed_detail_body
    assert prefixed_health_status == "200 OK"
    prefixed_health = json.loads(prefixed_health_body)
    assert prefixed_health["serving"]["base_path"] == "/radar"
    assert prefixed_health["serving"]["public_base_url"] == "https://radar.example.com/radar"
