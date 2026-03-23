from __future__ import annotations

from pathlib import Path
import sqlite3

from vinted_radar.db_recovery import recover_partial_database
from vinted_radar.repository import RadarRepository


def _seed_source_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds, total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs, successful_scans, failed_scans, raw_listing_hits, unique_listing_hits)
            VALUES ('run-1', '2026-03-22T10:00:00+00:00', '2026-03-22T10:10:00+00:00', 'completed', 'both', 1, 1, 0.0, 2, 1, 1, 1, 0, 1, 1);

            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-22T10:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-22T10:00:00+00:00');

            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, pagination_total_pages, next_page_url, error_message)
            VALUES ('run-1', 2001, 1, 'https://www.vinted.fr/catalog/2001-womens-dresses', '2026-03-22T10:05:00+00:00', 200, 1, 1, 1, NULL, NULL);

            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES (9001, 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?referrer=catalog', 'Recovered robe', 'Zara', 'M', 'Très bon état', 1500, 'EUR', 1650, 'EUR', 'https://images/9001.webp', 3, 9, 41, 'alice', 'https://www.vinted.fr/member/41', 1711092000, 2001, 1904, '2026-03-22T10:05:00+00:00', '2026-03-22T10:05:00+00:00', 'run-1', '{"overlay_title": "Recovered robe"}');

            INSERT INTO listing_discoveries (run_id, listing_id, observed_at, source_catalog_id, source_page_number, source_url, card_position, raw_card_payload_json)
            VALUES ('run-1', 9001, '2026-03-22T10:05:00+00:00', 2001, 1, 'https://www.vinted.fr/items/9001?referrer=catalog', 1, '{"overlay_title": "Recovered robe"}');

            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES ('run-1', 9001, '2026-03-22T10:05:00+00:00', 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?referrer=catalog', 2001, 1, 1, 1, 'Recovered robe', 'Zara', 'M', 'Très bon état', 1500, 'EUR', 1650, 'EUR', 'https://images/9001.webp', '{"overlay_title": "Recovered robe"}');
            """
        )
        repository.record_item_page_probe(
            listing_id=9001,
            probed_at='2026-03-22T11:00:00+00:00',
            requested_url='https://www.vinted.fr/items/9001',
            final_url='https://www.vinted.fr/items/9001',
            response_status=200,
            probe_outcome='active',
            detail={'reason': 'buy_signal_open'},
            error_message=None,
        )
        cycle_id = repository.start_runtime_cycle(
            mode='batch',
            phase='starting',
            interval_seconds=None,
            state_probe_limit=1,
            config={'state_refresh_limit': 1},
        )
        repository.complete_runtime_cycle(
            cycle_id,
            status='completed',
            phase='completed',
            discovery_run_id='run-1',
            state_probed_count=1,
            tracked_listings=1,
            freshness_counts={
                'first-pass-only': 1,
                'fresh-followup': 0,
                'aging-followup': 0,
                'stale-followup': 0,
            },
            last_error=None,
        )


def test_recover_partial_database_copies_healthy_source(tmp_path: Path) -> None:
    source = tmp_path / 'source.db'
    destination = tmp_path / 'recovered.db'
    _seed_source_db(source)

    report = recover_partial_database(source, destination)

    assert report['promoted'] is True
    assert report['destination_health']['healthy'] is True
    recovered = {row['table']: row['imported_rows'] for row in report['recovered_tables']}
    assert recovered['discovery_runs'] == 1
    assert recovered['catalogs'] == 2
    assert recovered['listings'] == 1
    assert recovered['item_page_probes'] == 1
    assert recovered['runtime_cycles'] == 1
    assert recovered['runtime_controller_state'] == 1

    with sqlite3.connect(destination) as connection:
        tables = {
            name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for name in ('discovery_runs', 'catalogs', 'catalog_scans', 'listings', 'listing_discoveries', 'listing_observations', 'item_page_probes', 'runtime_cycles', 'runtime_controller_state')
        }
    assert tables == {
        'discovery_runs': 1,
        'catalogs': 2,
        'catalog_scans': 1,
        'listings': 1,
        'listing_discoveries': 1,
        'listing_observations': 1,
        'item_page_probes': 1,
        'runtime_cycles': 1,
        'runtime_controller_state': 1,
    }


def test_recover_partial_database_can_target_subset(tmp_path: Path) -> None:
    source = tmp_path / 'source.db'
    destination = tmp_path / 'subset.db'
    _seed_source_db(source)

    report = recover_partial_database(source, destination, candidate_tables=('catalogs', 'runtime_cycles'))

    assert report['promoted'] is True
    recovered = {row['table']: row['imported_rows'] for row in report['recovered_tables']}
    assert recovered == {'catalogs': 2, 'runtime_cycles': 1}

    with sqlite3.connect(destination) as connection:
        counts = {
            name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for name in ('catalogs', 'runtime_cycles', 'listings', 'item_page_probes')
        }
    assert counts == {
        'catalogs': 2,
        'runtime_cycles': 1,
        'listings': 0,
        'item_page_probes': 0,
    }
