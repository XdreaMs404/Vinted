from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.repository import RadarRepository


def _seed_state_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds, total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs, successful_scans, failed_scans, raw_listing_hits, unique_listing_hits)
            VALUES
              ('run-1', '2026-03-17T10:00:00+00:00', '2026-03-17T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0, 6, 2, 2, 2, 0, 3, 3),
              ('run-2', '2026-03-18T10:00:00+00:00', '2026-03-18T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0, 6, 2, 2, 2, 0, 2, 2),
              ('run-3', '2026-03-19T10:00:00+00:00', '2026-03-19T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0, 6, 2, 2, 2, 0, 1, 1);

            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00');

            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9001, 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', 2001, 1904, '2026-03-17T10:05:00+00:00', '2026-03-19T10:05:00+00:00', 'run-3', '{"description_title": "Zara"}'),
              (9002, 'https://www.vinted.fr/items/9002-sold-probable', 'https://www.vinted.fr/items/9002-sold-probable?referrer=catalog', 'Probable sold robe', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9002.webp', 2001, 1904, '2026-03-17T10:06:00+00:00', '2026-03-17T10:06:00+00:00', 'run-1', '{"description_title": "Sandro"}'),
              (9003, 'https://www.vinted.fr/items/9003-deleted', 'https://www.vinted.fr/items/9003-deleted?referrer=catalog', 'Deleted robe', 'Mango', 'L', 'Neuf', 2000, '€', 2200, '€', 'https://images/9003.webp', 2001, 1904, '2026-03-18T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{"description_title": "Mango"}');

            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES
              ('run-1', 9001, '2026-03-17T10:05:00+00:00', 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1250, '€', 1413, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-2', 9001, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1400, '€', 1550, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-3', 9001, '2026-03-19T10:05:00+00:00', 'https://www.vinted.fr/items/9001-active', 'https://www.vinted.fr/items/9001-active?referrer=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-1', 9002, '2026-03-17T10:06:00+00:00', 'https://www.vinted.fr/items/9002-sold-probable', 'https://www.vinted.fr/items/9002-sold-probable?referrer=catalog', 2001, 1, 2, 1, 'Probable sold robe', 'Sandro', 'S', 'Bon état', 3000, '€', 3300, '€', 'https://images/9002.webp', '{"overlay_title": "Probable sold robe"}'),
              ('run-2', 9003, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9003-deleted', 'https://www.vinted.fr/items/9003-deleted?referrer=catalog', 2001, 1, 3, 1, 'Deleted robe', 'Mango', 'L', 'Neuf', 2000, '€', 2200, '€', 'https://images/9003.webp', '{"overlay_title": "Deleted robe"}');

            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-17T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-2', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-18T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-3', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-19T10:05:00+00:00', 200, 1, 1, 1, NULL, NULL);
            """
        )
        repository.record_item_page_probe(
            listing_id=9003,
            probed_at='2026-03-19T11:00:00+00:00',
            requested_url='https://www.vinted.fr/items/9003-deleted',
            final_url='https://www.vinted.fr/items/9003-deleted',
            response_status=404,
            probe_outcome='deleted',
            detail={'reason': 'http_404', 'response_status': 404},
            error_message=None,
        )
        conn.commit()


def test_state_summary_and_detail_cli_report_cautious_states(tmp_path: Path) -> None:
    db_path = tmp_path / 'state.db'
    _seed_state_db(db_path)
    runner = CliRunner()

    summary_result = runner.invoke(app, ['state-summary', '--db', str(db_path), '--now', '2026-03-19T12:00:00+00:00', '--format', 'json'])
    state_result = runner.invoke(app, ['state', '--db', str(db_path), '--listing-id', '9003', '--now', '2026-03-19T12:00:00+00:00', '--format', 'json'])

    assert summary_result.exit_code == 0
    assert state_result.exit_code == 0

    summary_payload = json.loads(summary_result.stdout)
    state_payload = json.loads(state_result.stdout)

    assert summary_payload['overall']['active'] == 1
    assert summary_payload['overall']['sold_probable'] == 1
    assert summary_payload['overall']['deleted'] == 1
    assert state_payload['state_code'] == 'deleted'
    assert state_payload['latest_probe']['probe_outcome'] == 'deleted'
