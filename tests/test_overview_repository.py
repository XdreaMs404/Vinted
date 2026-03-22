from __future__ import annotations

from pathlib import Path

from vinted_radar.repository import RadarRepository


def _seed_overview_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds, total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs, successful_scans, failed_scans, raw_listing_hits, unique_listing_hits)
            VALUES
              ('run-1', '2026-03-17T10:00:00+00:00', '2026-03-17T10:10:00+00:00', 'completed', 'both', 1, 3, 0.0, 6, 3, 2, 2, 0, 4, 4),
              ('run-2', '2026-03-18T10:00:00+00:00', '2026-03-18T10:10:00+00:00', 'completed', 'both', 1, 3, 0.0, 6, 3, 2, 2, 0, 4, 4),
              ('run-3', '2026-03-19T10:00:00+00:00', '2026-03-19T10:10:00+00:00', 'completed', 'both', 1, 3, 0.0, 6, 3, 3, 2, 1, 3, 2);

            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00'),
              (2002, 1904, 'Femmes', 1904, 'Vestes', 'WOMEN_JACKETS', 'https://www.vinted.fr/catalog/2002-womens-jackets', 'Femmes > Vestes', 1, 1, 1, 20, '2026-03-17T10:00:00+00:00'),
              (2003, 1904, 'Femmes', 1904, 'Jupes', 'WOMEN_SKIRTS', 'https://www.vinted.fr/catalog/2003-womens-skirts', 'Femmes > Jupes', 1, 1, 1, 30, '2026-03-17T10:00:00+00:00');

            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9101, 'https://www.vinted.fr/items/9101-active', 'https://www.vinted.fr/items/9101-active?referrer=catalog', 'Robe active', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9101.webp', 21, 180, 41, 'alice', 'https://www.vinted.fr/member/41', 1711101600, 2001, 1904, '2026-03-17T10:05:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{}'),
              (9102, 'https://www.vinted.fr/items/9102-sold-probable', 'https://www.vinted.fr/items/9102-sold-probable?referrer=catalog', 'Robe vendue probable', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9102.webp', 8, 90, 42, 'bruno', 'https://www.vinted.fr/member/42', 1711015200, 2001, 1904, '2026-03-17T10:06:00+00:00', '2026-03-17T10:06:00+00:00', 'run-1', '{}'),
              (9103, 'https://www.vinted.fr/items/9103-sold-observed', 'https://www.vinted.fr/items/9103-sold-observed?referrer=catalog', 'Robe vendue observée', 'Maje', 'L', 'Neuf', 4500, '€', 4800, '€', 'https://images/9103.webp', 15, 120, 43, 'claire', 'https://www.vinted.fr/member/43', 1711188000, 2001, 1904, '2026-03-18T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{}'),
              (9104, 'https://www.vinted.fr/items/9104-unavailable', 'https://www.vinted.fr/items/9104-unavailable?referrer=catalog', 'Veste indisponible', 'Zara', 'M', 'Bon état', 2500, '€', 2750, '€', 'https://images/9104.webp', 5, 65, 44, 'diane', 'https://www.vinted.fr/member/44', NULL, 2002, 1904, '2026-03-19T10:06:00+00:00', '2026-03-19T10:06:00+00:00', 'run-3', '{}'),
              (9105, 'https://www.vinted.fr/items/9105-deleted', 'https://www.vinted.fr/items/9105-deleted?referrer=catalog', 'Veste supprimée', 'Zara', 'L', 'Satisfaisant', 1800, '€', 2050, '€', 'https://images/9105.webp', 1, 10, 45, 'emma', 'https://www.vinted.fr/member/45', NULL, 2002, 1904, '2026-03-18T10:07:00+00:00', '2026-03-18T10:07:00+00:00', 'run-2', '{}'),
              (9106, 'https://www.vinted.fr/items/9106-unknown', 'https://www.vinted.fr/items/9106-unknown?referrer=catalog', 'Jupe incertaine', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 1710930000, 2003, 1904, '2026-03-17T10:08:00+00:00', '2026-03-17T10:08:00+00:00', 'run-1', '{}');

            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES
              ('run-1', 9101, '2026-03-17T10:05:00+00:00', 'https://www.vinted.fr/items/9101-active', 'https://www.vinted.fr/items/9101-active?referrer=catalog', 2001, 1, 1, 1, 'Robe active', 'Zara', 'M', 'Très bon état', 1400, '€', 1550, '€', 'https://images/9101.webp', '{}'),
              ('run-2', 9101, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9101-active', 'https://www.vinted.fr/items/9101-active?referrer=catalog', 2001, 1, 1, 1, 'Robe active', 'Zara', 'M', 'Très bon état', 1450, '€', 1600, '€', 'https://images/9101.webp', '{}'),
              ('run-3', 9101, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9101-active', 'https://www.vinted.fr/items/9101-active?referrer=catalog', 2001, 1, 1, 1, 'Robe active', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9101.webp', '{}'),
              ('run-1', 9102, '2026-03-17T10:06:00+00:00', 'https://www.vinted.fr/items/9102-sold-probable', 'https://www.vinted.fr/items/9102-sold-probable?referrer=catalog', 2001, 1, 2, 1, 'Robe vendue probable', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9102.webp', '{}'),
              ('run-2', 9103, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9103-sold-observed', 'https://www.vinted.fr/items/9103-sold-observed?referrer=catalog', 2001, 1, 3, 1, 'Robe vendue observée', 'Maje', 'L', 'Neuf', 4500, '€', 4800, '€', 'https://images/9103.webp', '{}'),
              ('run-3', 9104, '2026-03-19T10:06:00+00:00', 'https://www.vinted.fr/items/9104-unavailable', 'https://www.vinted.fr/items/9104-unavailable?referrer=catalog', 2002, 1, 1, 1, 'Veste indisponible', 'Zara', 'M', 'Bon état', 2500, '€', 2750, '€', 'https://images/9104.webp', '{}'),
              ('run-2', 9105, '2026-03-18T10:07:00+00:00', 'https://www.vinted.fr/items/9105-deleted', 'https://www.vinted.fr/items/9105-deleted?referrer=catalog', 2002, 1, 2, 1, 'Veste supprimée', 'Zara', 'L', 'Satisfaisant', 1800, '€', 2050, '€', 'https://images/9105.webp', '{}'),
              ('run-1', 9106, '2026-03-17T10:08:00+00:00', 'https://www.vinted.fr/items/9106-unknown', 'https://www.vinted.fr/items/9106-unknown?referrer=catalog', 2003, 1, 1, 1, 'Jupe incertaine', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{}');

            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-17T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-1', 2002, 1, 'https://www.vinted.fr/catalog/2002-womens-jackets', '2026-03-17T10:06:00+00:00', 200, 1, 0, 1, NULL, NULL),
              ('run-2', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-18T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-2', 2002, 1, 'https://www.vinted.fr/catalog/2002-womens-jackets', '2026-03-18T10:06:00+00:00', 200, 1, 1, 1, NULL, NULL),
              ('run-3', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-19T10:05:00+00:00', 200, 1, 1, 1, NULL, NULL),
              ('run-3', 2002, 1, 'https://www.vinted.fr/catalog/2002-womens-jackets', '2026-03-19T10:06:00+00:00', 200, 1, 1, 1, NULL, NULL),
              ('run-3', 2003, 1, 'https://www.vinted.fr/catalog/2003-womens-skirts', '2026-03-19T10:07:00+00:00', 502, 0, 0, 1, NULL, 'upstream unavailable');
            """
        )
        repository.record_item_page_probe(
            listing_id=9103,
            probed_at="2026-03-19T11:00:00+00:00",
            requested_url="https://www.vinted.fr/items/9103-sold-observed",
            final_url="https://www.vinted.fr/items/9103-sold-observed",
            response_status=200,
            probe_outcome="sold",
            detail={"reason": "buy_signal_closed", "response_status": 200},
            error_message=None,
        )
        repository.record_item_page_probe(
            listing_id=9104,
            probed_at="2026-03-19T11:05:00+00:00",
            requested_url="https://www.vinted.fr/items/9104-unavailable",
            final_url="https://www.vinted.fr/items/9104-unavailable",
            response_status=200,
            probe_outcome="unavailable",
            detail={"reason": "page_reachable_but_unavailable", "response_status": 200},
            error_message=None,
        )
        repository.record_item_page_probe(
            listing_id=9105,
            probed_at="2026-03-19T11:10:00+00:00",
            requested_url="https://www.vinted.fr/items/9105-deleted",
            final_url="https://www.vinted.fr/items/9105-deleted",
            response_status=404,
            probe_outcome="deleted",
            detail={"reason": "http_404", "response_status": 404},
            error_message=None,
        )
        cycle_id = repository.start_runtime_cycle(
            mode="continuous",
            phase="starting",
            interval_seconds=900.0,
            state_probe_limit=6,
            config={"state_refresh_limit": 6, "page_limit": 1},
        )
        repository.complete_runtime_cycle(
            cycle_id,
            status="completed",
            phase="completed",
            discovery_run_id="run-3",
            state_probed_count=3,
            tracked_listings=6,
            freshness_counts={
                "first-pass-only": 5,
                "fresh-followup": 1,
                "aging-followup": 0,
                "stale-followup": 0,
            },
            last_error=None,
        )
        conn.commit()


def test_overview_snapshot_returns_summary_and_lens_modules(tmp_path: Path) -> None:
    db_path = tmp_path / "overview.db"
    _seed_overview_db(db_path)

    with RadarRepository(db_path) as repository:
        overview = repository.overview_snapshot(now="2026-03-21T12:00:00+00:00", comparison_limit=5, support_threshold=2)

    summary = overview["summary"]
    assert summary["inventory"]["tracked_listings"] == 6
    assert summary["inventory"]["sold_like_count"] == 2
    assert summary["inventory"]["state_counts"] == {
        "active": 1,
        "sold_observed": 1,
        "sold_probable": 1,
        "unavailable_non_conclusive": 1,
        "deleted": 1,
        "unknown": 1,
    }
    assert summary["honesty"]["observed_state_count"] == 4
    assert summary["honesty"]["inferred_state_count"] == 1
    assert summary["honesty"]["unknown_state_count"] == 1
    assert summary["honesty"]["partial_signal_count"] == 1
    assert summary["honesty"]["thin_signal_count"] == 1
    assert summary["honesty"]["estimated_publication_count"] == 4
    assert summary["honesty"]["missing_estimated_publication_count"] == 2
    assert summary["freshness"]["latest_successful_scan_at"] == "2026-03-19T10:06:00+00:00"
    assert summary["freshness"]["latest_runtime_cycle_status"] == "completed"
    assert summary["freshness"]["recent_acquisition_failure_count"] == 1
    assert summary["freshness"]["recent_acquisition_failures"][0]["catalog_path"] == "Femmes > Jupes"

    comparisons = overview["comparisons"]
    assert set(comparisons) == {"category", "brand", "price_band", "condition", "sold_state"}

    category_module = comparisons["category"]
    assert category_module["status"] == "ok"
    assert [row["label"] for row in category_module["rows"]] == ["Femmes > Robes", "Femmes > Vestes", "Femmes > Jupes"]
    assert category_module["rows"][0]["drilldown"]["filters"] == {"catalog_id": 2001}
    assert category_module["rows"][0]["inventory"]["support_count"] == 3
    assert category_module["rows"][0]["inventory"]["sold_like_count"] == 2
    assert category_module["rows"][0]["honesty"]["observed_state_count"] == 2
    assert category_module["rows"][0]["honesty"]["inferred_state_count"] == 1
    assert category_module["rows"][2]["honesty"]["low_support"] is True

    brand_module = comparisons["brand"]
    assert brand_module["rows"][0]["label"] == "Zara"
    assert brand_module["rows"][0]["inventory"]["support_count"] == 3
    assert brand_module["rows"][0]["drilldown"]["filters"] == {"brand": "Zara"}
    assert brand_module["rows"][0]["honesty"]["estimated_publication_count"] == 1
    assert brand_module["rows"][0]["honesty"]["missing_estimated_publication_count"] == 2

    price_band_module = comparisons["price_band"]
    assert [row["value"] for row in price_band_module["rows"][:3]] == ["under_20_eur", "20_to_39_eur", "40_plus_eur"]
    assert price_band_module["rows"][0]["drilldown"]["filters"] == {"price_band": "under_20_eur"}
    assert price_band_module["rows"][0]["inventory"]["support_count"] == 2

    condition_module = comparisons["condition"]
    assert condition_module["rows"][0]["label"] == "Bon état"
    assert condition_module["rows"][0]["inventory"]["support_count"] == 2


def test_overview_snapshot_flags_thin_support_and_keeps_honesty_visible(tmp_path: Path) -> None:
    db_path = tmp_path / "overview.db"
    _seed_overview_db(db_path)

    with RadarRepository(db_path) as repository:
        overview = repository.overview_snapshot(now="2026-03-21T12:00:00+00:00", comparison_limit=6, support_threshold=2)

    sold_state_module = overview["comparisons"]["sold_state"]
    assert sold_state_module["status"] == "thin-support"
    assert sold_state_module["supported_rows"] == 0
    assert sold_state_module["thin_support_rows"] == 6
    assert sold_state_module["reason"] == "No lens value reaches the minimum support threshold of 2 tracked listings."
    assert sold_state_module["rows"][0]["drilldown"]["filters"] == {"state": "active"}
    assert all(row["honesty"]["low_support"] is True for row in sold_state_module["rows"])

    unknown_row = next(row for row in sold_state_module["rows"] if row["value"] == "unknown")
    assert unknown_row["honesty"]["unknown_state_count"] == 1
    assert unknown_row["honesty"]["partial_signal_count"] == 1
    assert unknown_row["honesty"]["thin_signal_count"] == 1
    assert unknown_row["honesty"]["estimated_publication_count"] == 1

    category_low_support = next(row for row in overview["comparisons"]["category"]["rows"] if row["label"] == "Femmes > Jupes")
    assert category_low_support["honesty"]["low_support"] is True
    assert category_low_support["inventory"]["state_counts"]["unknown"] == 1
