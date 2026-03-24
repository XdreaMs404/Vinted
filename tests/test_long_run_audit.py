from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.long_run_audit import build_long_run_audit_report, render_long_run_audit_markdown
from vinted_radar.repository import RadarRepository


def _seed_audit_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-20T01:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-20T01:00:00+00:00'),
              (2002, 1904, 'Femmes', 1904, 'Vestes', 'WOMEN_JACKETS', 'https://www.vinted.fr/catalog/2002-womens-jackets', 'Femmes > Vestes', 1, 1, 1, 20, '2026-03-20T01:00:00+00:00');

            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds, total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs, successful_scans, failed_scans, raw_listing_hits, unique_listing_hits, last_error)
            VALUES
              ('run-1', '2026-03-20T02:00:00+00:00', '2026-03-20T02:10:00+00:00', 'completed', 'women', 1, 1, 0.0, 3, 2, 1, 1, 0, 3, 3, NULL),
              ('run-2', '2026-03-20T08:00:00+00:00', '2026-03-20T08:10:00+00:00', 'completed', 'women', 1, 1, 0.0, 3, 2, 1, 1, 1, 2, 2, 'HTTP 403 on page 2');

            INSERT INTO listings (listing_id, canonical_url, source_url, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts, primary_catalog_id, primary_root_catalog_id, first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json)
            VALUES
              (9001, 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?ref=catalog', 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', 8, 110, 41, 'alice', 'https://www.vinted.fr/member/41', 1710900000, 2001, 1904, '2026-03-20T02:05:00+00:00', '2026-03-20T08:05:00+00:00', 'run-2', '{"description_title": "Active robe"}'),
              (9002, 'https://www.vinted.fr/items/9002', 'https://www.vinted.fr/items/9002?ref=catalog', 'Challenge robe', 'Sandro', 'S', 'Bon état', 3200, '€', 3500, '€', 'https://images/9002.webp', 2, 30, 42, 'bruno', 'https://www.vinted.fr/member/42', 1710900300, 2001, 1904, '2026-03-20T02:06:00+00:00', '2026-03-20T02:06:00+00:00', 'run-1', '{"description_title": "Challenge robe"}'),
              (9003, 'https://www.vinted.fr/items/9003', 'https://www.vinted.fr/items/9003?ref=catalog', 'Fresh robe', 'Maje', 'L', 'Neuf', 4200, '€', 4550, '€', 'https://images/9003.webp', 20, 240, 43, 'claire', 'https://www.vinted.fr/member/43', 1710920000, 2001, 1904, '2026-03-20T08:05:00+00:00', '2026-03-20T08:05:00+00:00', 'run-2', '{"description_title": "Fresh robe"}'),
              (9004, 'https://www.vinted.fr/items/9004', 'https://www.vinted.fr/items/9004?ref=catalog', 'Another robe', 'Mango', 'L', 'Neuf', 2100, '€', 2300, '€', 'https://images/9004.webp', 5, 70, 44, 'diane', 'https://www.vinted.fr/member/44', 1710920100, 2001, 1904, '2026-03-20T08:06:00+00:00', '2026-03-20T08:06:00+00:00', 'run-2', '{"description_title": "Another robe"}'),
              (9005, 'https://www.vinted.fr/items/9005', 'https://www.vinted.fr/items/9005?ref=catalog', 'Late robe', 'Sézane', 'M', 'Très bon état', 5100, '€', 5400, '€', 'https://images/9005.webp', 1, 15, 45, 'emma', 'https://www.vinted.fr/member/45', 1710920200, 2001, 1904, '2026-03-20T08:07:00+00:00', '2026-03-20T08:07:00+00:00', 'run-2', '{"description_title": "Late robe"}');

            INSERT INTO listing_observations (run_id, listing_id, observed_at, canonical_url, source_url, source_catalog_id, source_page_number, first_card_position, sighting_count, title, brand, size_label, condition_label, price_amount_cents, price_currency, total_price_amount_cents, total_price_currency, image_url, raw_card_payload_json)
            VALUES
              ('run-1', 9001, '2026-03-20T02:05:00+00:00', 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?ref=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1450, '€', 1600, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-2', 9001, '2026-03-20T08:05:00+00:00', 'https://www.vinted.fr/items/9001', 'https://www.vinted.fr/items/9001?ref=catalog', 2001, 1, 1, 1, 'Active robe', 'Zara', 'M', 'Très bon état', 1500, '€', 1650, '€', 'https://images/9001.webp', '{"overlay_title": "Active robe"}'),
              ('run-1', 9002, '2026-03-20T02:06:00+00:00', 'https://www.vinted.fr/items/9002', 'https://www.vinted.fr/items/9002?ref=catalog', 2001, 1, 2, 1, 'Challenge robe', 'Sandro', 'S', 'Bon état', 3200, '€', 3500, '€', 'https://images/9002.webp', '{"overlay_title": "Challenge robe"}'),
              ('run-2', 9003, '2026-03-20T08:05:00+00:00', 'https://www.vinted.fr/items/9003', 'https://www.vinted.fr/items/9003?ref=catalog', 2001, 1, 3, 1, 'Fresh robe', 'Maje', 'L', 'Neuf', 4200, '€', 4550, '€', 'https://images/9003.webp', '{"overlay_title": "Fresh robe"}'),
              ('run-2', 9004, '2026-03-20T08:06:00+00:00', 'https://www.vinted.fr/items/9004', 'https://www.vinted.fr/items/9004?ref=catalog', 2001, 1, 4, 1, 'Another robe', 'Mango', 'L', 'Neuf', 2100, '€', 2300, '€', 'https://images/9004.webp', '{"overlay_title": "Another robe"}'),
              ('run-2', 9005, '2026-03-20T08:07:00+00:00', 'https://www.vinted.fr/items/9005', 'https://www.vinted.fr/items/9005?ref=catalog', 2001, 1, 5, 1, 'Late robe', 'Sézane', 'M', 'Très bon état', 5100, '€', 5400, '€', 'https://images/9005.webp', '{"overlay_title": "Late robe"}');

            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, api_listing_count, accepted_listing_count, filtered_out_count, accepted_ratio, min_price_seen_cents, max_price_seen_cents, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'https://www.vinted.fr/api/v2/catalog/items?catalog[]=2001&price_from=30', '2026-03-20T02:05:00+00:00', 200, 1, 3, 3, 3, 0, 1.0, 1450, 3200, 1, NULL, NULL),
              ('run-2', 2001, 1, 'https://www.vinted.fr/api/v2/catalog/items?catalog[]=2001&price_from=30', '2026-03-20T08:05:00+00:00', 200, 1, 3, 3, 3, 0, 1.0, 1500, 5100, 2, 'https://www.vinted.fr/api/v2/catalog/items?page=2', NULL),
              ('run-2', 2001, 2, 'https://www.vinted.fr/api/v2/catalog/items?catalog[]=2001&price_from=30&page=2', '2026-03-20T08:06:00+00:00', 403, 0, 0, 0, 0, 0, 0.0, NULL, NULL, 2, NULL, 'HTTP 403 on page 2');
            """
        )
        repository.record_item_page_probe(
            listing_id=9001,
            probed_at="2026-03-20T08:20:00+00:00",
            requested_url="https://www.vinted.fr/items/9001",
            final_url="https://www.vinted.fr/items/9001",
            response_status=200,
            probe_outcome="active",
            detail={"reason": "buy_signal_open", "response_status": 200},
            error_message=None,
        )
        repository.record_item_page_probe(
            listing_id=9002,
            probed_at="2026-03-20T08:21:00+00:00",
            requested_url="https://www.vinted.fr/items/9002",
            final_url="https://www.vinted.fr/items/9002",
            response_status=403,
            probe_outcome="unknown",
            detail={"reason": "anti_bot_challenge", "response_status": 403, "challenge_markers": ["just a moment"]},
            error_message=None,
        )
        repository.record_item_page_probe(
            listing_id=9003,
            probed_at="2026-03-20T08:22:00+00:00",
            requested_url="https://www.vinted.fr/items/9003",
            final_url="https://www.vinted.fr/items/9003",
            response_status=200,
            probe_outcome="active",
            detail={"reason": "buy_signal_open", "response_status": 200},
            error_message=None,
        )

        conn.execute(
            """
            INSERT INTO runtime_cycles (
                cycle_id, started_at, finished_at, mode, status, phase, interval_seconds,
                state_probe_limit, discovery_run_id, state_probed_count, tracked_listings,
                first_pass_only, fresh_followup, aging_followup, stale_followup, last_error,
                state_refresh_summary_json, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cycle-1",
                "2026-03-20T02:00:00+00:00",
                "2026-03-20T02:12:00+00:00",
                "continuous",
                "completed",
                "completed",
                21600.0,
                2,
                "run-1",
                1,
                2,
                1,
                1,
                0,
                0,
                None,
                json.dumps(
                    {
                        "status": "partial",
                        "requested_limit": 2,
                        "selected_target_count": 1,
                        "probed_count": 1,
                        "direct_signal_count": 0,
                        "inconclusive_probe_count": 1,
                        "degraded_probe_count": 0,
                        "anti_bot_challenge_count": 0,
                        "http_error_count": 0,
                        "transport_error_count": 0,
                        "reason_counts": {"unknown": 1},
                        "degraded_listing_ids": [],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                json.dumps({"page_limit": 1, "state_refresh_limit": 2, "max_leaf_categories": 1}, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO runtime_cycles (
                cycle_id, started_at, finished_at, mode, status, phase, interval_seconds,
                state_probe_limit, discovery_run_id, state_probed_count, tracked_listings,
                first_pass_only, fresh_followup, aging_followup, stale_followup, last_error,
                state_refresh_summary_json, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cycle-2",
                "2026-03-20T08:00:00+00:00",
                "2026-03-20T08:14:00+00:00",
                "continuous",
                "completed",
                "completed",
                21600.0,
                3,
                "run-2",
                2,
                5,
                4,
                1,
                0,
                0,
                None,
                json.dumps(
                    {
                        "status": "degraded",
                        "requested_limit": 3,
                        "selected_target_count": 2,
                        "probed_count": 2,
                        "direct_signal_count": 1,
                        "inconclusive_probe_count": 0,
                        "degraded_probe_count": 1,
                        "anti_bot_challenge_count": 1,
                        "http_error_count": 0,
                        "transport_error_count": 0,
                        "reason_counts": {"anti_bot_challenge": 1, "buy_signal_open": 1},
                        "degraded_listing_ids": [9002],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                json.dumps({"page_limit": 1, "state_refresh_limit": 3, "max_leaf_categories": 1}, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO runtime_cycles (
                cycle_id, started_at, finished_at, mode, status, phase, interval_seconds,
                state_probe_limit, discovery_run_id, state_probed_count, tracked_listings,
                first_pass_only, fresh_followup, aging_followup, stale_followup, last_error,
                state_refresh_summary_json, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cycle-3",
                "2026-03-20T10:00:00+00:00",
                "2026-03-20T10:02:00+00:00",
                "continuous",
                "failed",
                "discovery",
                21600.0,
                3,
                None,
                0,
                5,
                4,
                1,
                0,
                0,
                "RuntimeError: discovery exploded",
                json.dumps({}, ensure_ascii=False, sort_keys=True),
                json.dumps({"page_limit": 1, "state_refresh_limit": 3, "max_leaf_categories": 1}, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO runtime_controller_state (
                controller_id, status, phase, mode, active_cycle_id, latest_cycle_id,
                interval_seconds, updated_at, paused_at, next_resume_at, last_error,
                last_error_at, requested_action, requested_at, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "scheduled",
                "waiting",
                "continuous",
                None,
                "cycle-3",
                21600.0,
                "2026-03-20T10:05:00+00:00",
                None,
                "2026-03-20T14:00:00+00:00",
                "RuntimeError: discovery exploded",
                "2026-03-20T10:02:00+00:00",
                "none",
                None,
                json.dumps({"page_limit": 1, "state_refresh_limit": 3, "max_leaf_categories": 1}, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.commit()


def test_build_long_run_audit_report_summarizes_vps_window(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _seed_audit_db(db_path)

    report = build_long_run_audit_report(
        db_path,
        hours=12,
        now="2026-03-20T12:00:00+00:00",
        issue_limit=3,
        revisit_limit=5,
    )

    assert report["verdict"]["status"] == "degraded"
    assert report["runtime"]["cycle_count"] == 3
    assert report["runtime"]["failed_cycles"] == 1
    assert report["discovery"]["run_count"] == 2
    assert report["discovery"]["unique_leaf_catalogs_scanned"] == 1
    assert report["discovery"]["narrow_coverage_suspected"] is True
    assert report["discovery"]["top_failing_catalogs"][0]["catalog_path"] == "Femmes > Robes"
    assert report["acquisition"]["latest_status"] == "degraded"
    assert report["acquisition"]["window_cycle_status_counts"] == {
        "healthy": 0,
        "partial": 1,
        "degraded": 1,
        "unknown": 1,
    }
    assert report["acquisition"]["probe_totals"]["anti_bot_challenge_count"] == 1
    assert report["acquisition"]["degraded_listing_examples"][0]["listing_id"] == 9002
    assert report["freshness"]["overall"]["tracked_listings"] == 5
    assert report["freshness"]["overall"]["first-pass-only"] == 4
    assert report["revisit"]["top_candidates"][0]["listing_id"] == 9002
    assert any("--max-leaf-categories" in item for item in report["recommendations"])

    markdown = render_long_run_audit_markdown(report)
    assert "# Long-run audit — 12.0h" in markdown
    assert "## Recommendations" in markdown
    assert "Freshness snapshot" in markdown


def test_audit_long_run_cli_emits_json_and_markdown(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _seed_audit_db(db_path)
    runner = CliRunner()

    json_result = runner.invoke(
        app,
        [
            "audit-long-run",
            "--db",
            str(db_path),
            "--hours",
            "12",
            "--now",
            "2026-03-20T12:00:00+00:00",
            "--format",
            "json",
        ],
    )
    assert json_result.exit_code == 0
    payload = json.loads(json_result.stdout)
    assert payload["verdict"]["status"] == "degraded"
    assert payload["acquisition"]["probe_totals"]["anti_bot_challenge_count"] == 1

    markdown_result = runner.invoke(
        app,
        [
            "audit-long-run",
            "--db",
            str(db_path),
            "--hours",
            "12",
            "--now",
            "2026-03-20T12:00:00+00:00",
            "--format",
            "markdown",
        ],
    )
    assert markdown_result.exit_code == 0
    assert "# Long-run audit — 12.0h" in markdown_result.stdout
    assert "Status: **degraded**" in markdown_result.stdout
