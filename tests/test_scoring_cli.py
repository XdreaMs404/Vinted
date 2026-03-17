from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.repository import RadarRepository


def _seed_scoring_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds)
            VALUES
              ('run-1', '2026-03-17T10:00:00+00:00', '2026-03-17T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0),
              ('run-2', '2026-03-18T10:00:00+00:00', '2026-03-18T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0);
            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00');
            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9001, 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?referrer=catalog', 'Strong robe', 'Sandro', 'M', 'Très bon état', 5000, '€', 5500, '€', 'https://images/9001.webp', 2001, 1904, '2026-03-17T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{"description_title": "Sandro"}'),
              (9002, 'https://www.vinted.fr/items/9002', 'https://www.vinted.fr/items/9002?referrer=catalog', 'Mid robe', 'Sandro', 'M', 'Très bon état', 3200, '€', 3500, '€', 'https://images/9002.webp', 2001, 1904, '2026-03-17T10:06:00+00:00', '2026-03-17T10:06:00+00:00', 'run-1', '{"description_title": "Sandro"}'),
              (9003, 'https://www.vinted.fr/items/9003', 'https://www.vinted.fr/items/9003?referrer=catalog', 'Cheap robe', 'Sandro', 'M', 'Très bon état', 1800, '€', 2000, '€', 'https://images/9003.webp', 2001, 1904, '2026-03-18T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{"description_title": "Sandro"}'),
              (9004, 'https://www.vinted.fr/items/9004', 'https://www.vinted.fr/items/9004?referrer=catalog', 'Budget robe', 'Sandro', 'M', 'Très bon état', 1200, '€', 1400, '€', 'https://images/9004.webp', 2001, 1904, '2026-03-18T10:05:00+00:00', '2026-03-18T10:05:00+00:00', 'run-2', '{"description_title": "Sandro"}');
            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES
              ('run-1', 9001, '2026-03-17T10:05:00+00:00', 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?referrer=catalog', 2001, 1, 1, 1, 'Strong robe', 'Sandro', 'M', 'Très bon état', 5000, '€', 5500, '€', 'https://images/9001.webp', '{"overlay_title": "Strong robe"}'),
              ('run-2', 9001, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?referrer=catalog', 2001, 1, 1, 1, 'Strong robe', 'Sandro', 'M', 'Très bon état', 5000, '€', 5500, '€', 'https://images/9001.webp', '{"overlay_title": "Strong robe"}'),
              ('run-1', 9002, '2026-03-17T10:06:00+00:00', 'https://www.vinted.fr/items/9002', 'https://www.vinted.fr/items/9002?referrer=catalog', 2001, 1, 2, 1, 'Mid robe', 'Sandro', 'M', 'Très bon état', 3200, '€', 3500, '€', 'https://images/9002.webp', '{"overlay_title": "Mid robe"}'),
              ('run-2', 9003, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9003', 'https://www.vinted.fr/items/9003?referrer=catalog', 2001, 1, 3, 1, 'Cheap robe', 'Sandro', 'M', 'Très bon état', 1800, '€', 2000, '€', 'https://images/9003.webp', '{"overlay_title": "Cheap robe"}'),
              ('run-2', 9004, '2026-03-18T10:05:00+00:00', 'https://www.vinted.fr/items/9004', 'https://www.vinted.fr/items/9004?referrer=catalog', 2001, 1, 4, 1, 'Budget robe', 'Sandro', 'M', 'Très bon état', 1200, '€', 1400, '€', 'https://images/9004.webp', '{"overlay_title": "Budget robe"}');
            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-17T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-2', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-18T10:05:00+00:00', 200, 1, 3, 1, NULL, NULL);
            """
        )
        repository.record_item_page_probe(
            listing_id=9001,
            probed_at='2026-03-18T11:00:00+00:00',
            requested_url='https://www.vinted.fr/items/9001',
            final_url='https://www.vinted.fr/items/9001',
            response_status=200,
            probe_outcome='active',
            detail={'reason': 'buy_signal_open', 'can_buy': True, 'is_closed': False, 'is_hidden': False, 'is_reserved': False, 'parsed_item_id': 9001, 'response_status': 200},
            error_message=None,
        )
        conn.commit()


def test_rankings_score_and_market_summary_cli_emit_json(tmp_path: Path) -> None:
    db_path = tmp_path / 'scoring.db'
    _seed_scoring_db(db_path)
    runner = CliRunner()

    rankings_result = runner.invoke(app, ['rankings', '--db', str(db_path), '--kind', 'premium', '--format', 'json'])
    score_result = runner.invoke(app, ['score', '--db', str(db_path), '--listing-id', '9001', '--format', 'json'])
    summary_result = runner.invoke(app, ['market-summary', '--db', str(db_path), '--format', 'json'])

    assert rankings_result.exit_code == 0
    assert score_result.exit_code == 0
    assert summary_result.exit_code == 0

    rankings_payload = json.loads(rankings_result.stdout)
    score_payload = json.loads(score_result.stdout)
    summary_payload = json.loads(summary_result.stdout)

    assert rankings_payload[0]['listing_id'] == 9001
    assert score_payload['score_explanation']['context']['price_band_label'] == 'premium'
    assert summary_payload['performing_segments'][0]['catalog_id'] == 2001
