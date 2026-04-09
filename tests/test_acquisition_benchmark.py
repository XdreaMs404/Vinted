from __future__ import annotations

import json
from pathlib import Path

from vinted_radar.repository import RadarRepository
from vinted_radar.services.acquisition_benchmark import (
    build_acquisition_benchmark_report,
    collect_acquisition_benchmark_facts,
    render_acquisition_benchmark_markdown,
    write_acquisition_benchmark_report,
)


def test_build_acquisition_benchmark_report_ranks_profiles_deterministically() -> None:
    experiments = [
        {
            "experiment_id": "baseline-b",
            "profile": "baseline-b",
            "label": "Baseline B",
            "window": {
                "started_at": "2026-03-24T10:00:00+00:00",
                "finished_at": "2026-03-24T12:00:00+00:00",
            },
            "config": {"mode": "baseline"},
            "facts": {
                "discovery_runs": [
                    {
                        "run_id": "run-b-1",
                        "started_at": "2026-03-24T10:00:00+00:00",
                        "finished_at": "2026-03-24T11:00:00+00:00",
                        "status": "completed",
                        "root_scope": "women",
                        "page_limit": 1,
                        "max_leaf_categories": 2,
                        "request_delay_seconds": 0.0,
                        "scanned_leaf_catalogs": 2,
                        "successful_scans": 3,
                        "failed_scans": 0,
                        "raw_listing_hits": 20,
                        "unique_listing_hits": 10,
                    },
                    {
                        "run_id": "run-b-2",
                        "started_at": "2026-03-24T11:00:00+00:00",
                        "finished_at": "2026-03-24T12:00:00+00:00",
                        "status": "completed",
                        "root_scope": "women",
                        "page_limit": 1,
                        "max_leaf_categories": 2,
                        "request_delay_seconds": 0.0,
                        "scanned_leaf_catalogs": 2,
                        "successful_scans": 3,
                        "failed_scans": 0,
                        "raw_listing_hits": 16,
                        "unique_listing_hits": 10,
                    },
                ],
                "catalog_scans": [
                    {
                        "run_id": "run-b-1",
                        "catalog_id": 2001,
                        "catalog_path": "Femmes > Robes",
                        "root_title": "Femmes",
                        "page_number": 1,
                        "requested_url": "https://example.test/b-1",
                        "fetched_at": "2026-03-24T10:10:00+00:00",
                        "response_status": 200,
                        "success": True,
                        "listing_count": 10,
                        "api_listing_count": 10,
                        "accepted_listing_count": 10,
                        "filtered_out_count": 0,
                        "accepted_ratio": 1.0,
                        "error_message": None,
                    },
                    {
                        "run_id": "run-b-2",
                        "catalog_id": 2001,
                        "catalog_path": "Femmes > Robes",
                        "root_title": "Femmes",
                        "page_number": 1,
                        "requested_url": "https://example.test/b-2",
                        "fetched_at": "2026-03-24T11:10:00+00:00",
                        "response_status": 200,
                        "success": True,
                        "listing_count": 8,
                        "api_listing_count": 8,
                        "accepted_listing_count": 8,
                        "filtered_out_count": 0,
                        "accepted_ratio": 1.0,
                        "error_message": None,
                    },
                ],
                "runtime_cycles": [
                    {
                        "cycle_id": "cycle-b-1",
                        "started_at": "2026-03-24T10:00:00+00:00",
                        "finished_at": "2026-03-24T11:00:00+00:00",
                        "mode": "continuous",
                        "status": "completed",
                        "phase": "completed",
                        "interval_seconds": 3600.0,
                        "state_probe_limit": 3,
                        "discovery_run_id": "run-b-1",
                        "state_probed_count": 2,
                        "tracked_listings": 120,
                        "state_refresh_summary": {
                            "status": "healthy",
                            "direct_signal_count": 2,
                            "inconclusive_probe_count": 0,
                            "degraded_probe_count": 0,
                            "anti_bot_challenge_count": 0,
                            "http_error_count": 0,
                            "transport_error_count": 0,
                            "reason_counts": {"buy_signal_open": 2},
                        },
                        "config": {"page_limit": 1, "state_refresh_limit": 3},
                    }
                ],
                "storage_snapshots": [
                    {
                        "captured_at": "2026-03-24T10:00:00+00:00",
                        "listing_count": 100,
                        "db_size_bytes": 10_000,
                        "artifact_size_bytes": 2_000,
                    },
                    {
                        "captured_at": "2026-03-24T12:00:00+00:00",
                        "listing_count": 120,
                        "db_size_bytes": 12_000,
                        "artifact_size_bytes": 2_400,
                    },
                ],
                "resource_snapshots": [
                    {"captured_at": "2026-03-24T10:30:00+00:00", "cpu_percent": 42.0, "rss_mb": 400.0},
                    {"captured_at": "2026-03-24T11:30:00+00:00", "cpu_percent": 46.0, "rss_mb": 420.0},
                ],
            },
        },
        {
            "experiment_id": "baseline-a",
            "profile": "baseline-a",
            "label": "Baseline A",
            "window": {
                "started_at": "2026-03-24T10:00:00+00:00",
                "finished_at": "2026-03-24T12:00:00+00:00",
            },
            "config": {"mode": "baseline"},
            "facts": {
                "discovery_runs": [
                    {
                        "run_id": "run-a-1",
                        "started_at": "2026-03-24T10:00:00+00:00",
                        "finished_at": "2026-03-24T11:00:00+00:00",
                        "status": "completed",
                        "root_scope": "women",
                        "page_limit": 1,
                        "max_leaf_categories": 2,
                        "request_delay_seconds": 0.0,
                        "scanned_leaf_catalogs": 2,
                        "successful_scans": 3,
                        "failed_scans": 0,
                        "raw_listing_hits": 14,
                        "unique_listing_hits": 10,
                    },
                    {
                        "run_id": "run-a-2",
                        "started_at": "2026-03-24T11:00:00+00:00",
                        "finished_at": "2026-03-24T12:00:00+00:00",
                        "status": "completed",
                        "root_scope": "women",
                        "page_limit": 1,
                        "max_leaf_categories": 2,
                        "request_delay_seconds": 0.0,
                        "scanned_leaf_catalogs": 2,
                        "successful_scans": 3,
                        "failed_scans": 0,
                        "raw_listing_hits": 12,
                        "unique_listing_hits": 10,
                    },
                ],
                "catalog_scans": [
                    {
                        "run_id": "run-a-1",
                        "catalog_id": 2001,
                        "catalog_path": "Femmes > Robes",
                        "root_title": "Femmes",
                        "page_number": 1,
                        "requested_url": "https://example.test/a-1",
                        "fetched_at": "2026-03-24T10:10:00+00:00",
                        "response_status": 200,
                        "success": True,
                        "listing_count": 7,
                        "api_listing_count": 7,
                        "accepted_listing_count": 7,
                        "filtered_out_count": 0,
                        "accepted_ratio": 1.0,
                        "error_message": None,
                    },
                    {
                        "run_id": "run-a-2",
                        "catalog_id": 2001,
                        "catalog_path": "Femmes > Robes",
                        "root_title": "Femmes",
                        "page_number": 1,
                        "requested_url": "https://example.test/a-2",
                        "fetched_at": "2026-03-24T11:10:00+00:00",
                        "response_status": 200,
                        "success": True,
                        "listing_count": 6,
                        "api_listing_count": 6,
                        "accepted_listing_count": 6,
                        "filtered_out_count": 0,
                        "accepted_ratio": 1.0,
                        "error_message": None,
                    },
                ],
                "runtime_cycles": [
                    {
                        "cycle_id": "cycle-a-1",
                        "started_at": "2026-03-24T10:00:00+00:00",
                        "finished_at": "2026-03-24T11:00:00+00:00",
                        "mode": "continuous",
                        "status": "completed",
                        "phase": "completed",
                        "interval_seconds": 3600.0,
                        "state_probe_limit": 3,
                        "discovery_run_id": "run-a-1",
                        "state_probed_count": 2,
                        "tracked_listings": 120,
                        "state_refresh_summary": {
                            "status": "healthy",
                            "direct_signal_count": 2,
                            "inconclusive_probe_count": 0,
                            "degraded_probe_count": 0,
                            "anti_bot_challenge_count": 0,
                            "http_error_count": 0,
                            "transport_error_count": 0,
                            "reason_counts": {"buy_signal_open": 2},
                        },
                        "config": {"page_limit": 1, "state_refresh_limit": 3},
                    }
                ],
                "storage_snapshots": [
                    {
                        "captured_at": "2026-03-24T10:00:00+00:00",
                        "listing_count": 100,
                        "db_size_bytes": 10_000,
                        "artifact_size_bytes": 2_000,
                    },
                    {
                        "captured_at": "2026-03-24T12:00:00+00:00",
                        "listing_count": 120,
                        "db_size_bytes": 11_400,
                        "artifact_size_bytes": 2_200,
                    },
                ],
                "resource_snapshots": [
                    {"captured_at": "2026-03-24T10:30:00+00:00", "cpu_percent": 39.0, "rss_mb": 360.0},
                    {"captured_at": "2026-03-24T11:30:00+00:00", "cpu_percent": 41.0, "rss_mb": 370.0},
                ],
            },
        },
    ]

    report = build_acquisition_benchmark_report(
        experiments,
        generated_at="2026-03-24T12:30:00+00:00",
    )

    leaderboard = report["leaderboard"]
    winner = leaderboard[0]
    runner_up = leaderboard[1]
    summary = report["summary"]
    markdown = render_acquisition_benchmark_markdown(report)

    assert winner["experiment_id"] == "baseline-a"
    assert winner["rank"] == 1
    assert winner["winner"] is True
    assert winner["net_new_listings_per_hour"] == 10.0
    assert winner["duplicate_ratio"] == 0.2308
    assert winner["bytes_per_new_listing"] == 80.0
    assert winner["mean_cpu_percent"] == 40.0
    assert winner["peak_ram_mb"] == 370.0

    assert runner_up["experiment_id"] == "baseline-b"
    assert runner_up["net_new_listings_per_hour"] == 10.0
    assert runner_up["duplicate_ratio"] == 0.4444
    assert runner_up["bytes_per_new_listing"] == 120.0

    assert summary["winner_profile"] == "baseline-a"
    assert summary["runner_up_profile"] == "baseline-b"
    assert summary["winner_reason"] == "Matched higher-priority metrics and won on duplicate ratio: 0.2308 vs 0.4444."
    assert report["experiments"][0]["scorecard"]["challenge_count"] == 0
    assert report["experiments"][0]["scorecard"]["degraded_count"] == 0
    assert "# Acquisition benchmark" in markdown
    assert "## Method" in markdown
    assert "## Why the winner ranked first" in markdown
    assert "baseline-a 🏆" in markdown


def test_collect_acquisition_benchmark_facts_from_repository_window_builds_scorecard(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    _seed_repository_benchmark_db(db_path)

    experiment = collect_acquisition_benchmark_facts(
        db_path,
        experiment_id="profile-window-1",
        profile="profile-window-1",
        label="Profile Window 1",
        window_started_at="2026-03-25T09:00:00+00:00",
        window_finished_at="2026-03-25T10:00:00+00:00",
        config={"runner": "synthetic"},
        storage_snapshots=[
            {
                "captured_at": "2026-03-25T09:00:00+00:00",
                "listing_count": 100,
                "db_size_bytes": 50_000,
                "artifact_size_bytes": 5_000,
            },
            {
                "captured_at": "2026-03-25T10:00:00+00:00",
                "listing_count": 108,
                "db_size_bytes": 51_600,
                "artifact_size_bytes": 5_400,
            },
        ],
        resource_snapshots=[
            {
                "captured_at": "2026-03-25T09:15:00+00:00",
                "cpu_percent": 35.0,
                "rss_mb": 256.0,
            },
            {
                "captured_at": "2026-03-25T09:45:00+00:00",
                "cpu_percent": 45.0,
                "rss_mb": 288.0,
            },
        ],
    )

    report = build_acquisition_benchmark_report([experiment])
    payload = report["experiments"][0]
    scorecard = payload["scorecard"]
    config = payload["config"]
    leaderboard = report["leaderboard"]

    assert len(payload["facts"]["discovery_runs"]) == 1
    assert len(payload["facts"]["catalog_scans"]) == 2
    assert len(payload["facts"]["runtime_cycles"]) == 1
    assert config["declared"] == {"runner": "synthetic"}
    assert config["observed"]["page_limit"] == 1
    assert config["observed"]["state_probe_limit"] == 3
    assert payload["window"]["duration_hours"] == 1.0

    assert scorecard["net_new_listings"] == 8
    assert scorecard["net_new_listings_per_hour"] == 8.0
    assert scorecard["duplicate_ratio"] == 0.6
    assert scorecard["challenge_count"] == 2
    assert scorecard["challenge_rate"] == 0.4
    assert scorecard["degraded_count"] == 2
    assert scorecard["bytes_per_new_listing"] == 250.0
    assert scorecard["mean_cpu_percent"] == 40.0
    assert scorecard["peak_ram_mb"] == 288.0

    assert leaderboard[0]["experiment_id"] == "profile-window-1"
    assert leaderboard[0]["winner"] is True


def test_write_acquisition_benchmark_report_persists_json_and_markdown(tmp_path: Path) -> None:
    report = build_acquisition_benchmark_report(
        [
            {
                "experiment_id": "profile-a",
                "profile": "profile-a",
                "window": {
                    "started_at": "2026-03-26T09:00:00+00:00",
                    "finished_at": "2026-03-26T10:00:00+00:00",
                },
                "facts": {
                    "discovery_runs": [
                        {
                            "run_id": "run-a",
                            "started_at": "2026-03-26T09:00:00+00:00",
                            "finished_at": "2026-03-26T10:00:00+00:00",
                            "status": "completed",
                            "root_scope": "women",
                            "page_limit": 1,
                            "request_delay_seconds": 0.0,
                            "raw_listing_hits": 10,
                            "unique_listing_hits": 5,
                            "successful_scans": 1,
                            "failed_scans": 0,
                            "scanned_leaf_catalogs": 1,
                        }
                    ],
                    "catalog_scans": [],
                    "runtime_cycles": [],
                    "storage_snapshots": [
                        {
                            "captured_at": "2026-03-26T09:00:00+00:00",
                            "listing_count": 10,
                            "db_size_bytes": 1_000,
                        },
                        {
                            "captured_at": "2026-03-26T10:00:00+00:00",
                            "listing_count": 15,
                            "db_size_bytes": 1_500,
                        },
                    ],
                    "resource_snapshots": [],
                },
            }
        ],
        generated_at="2026-03-26T10:05:00+00:00",
    )

    json_path = tmp_path / "acquisition-benchmark.json"
    markdown_path = tmp_path / "acquisition-benchmark.md"
    written = write_acquisition_benchmark_report(
        report,
        json_path=json_path,
        markdown_path=markdown_path,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert written == {"json": str(json_path), "markdown": str(markdown_path)}
    assert payload["leaderboard"][0]["experiment_id"] == "profile-a"
    assert "# Acquisition benchmark" in markdown
    assert "profile-a 🏆" in markdown


def _seed_repository_benchmark_db(db_path: Path) -> None:
    with RadarRepository(db_path) as repository:
        conn = repository.connection
        conn.executescript(
            """
            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-25T08:55:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-25T08:55:00+00:00');

            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds, total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs, successful_scans, failed_scans, raw_listing_hits, unique_listing_hits, last_error)
            VALUES
              ('run-1', '2026-03-25T09:00:00+00:00', '2026-03-25T10:00:00+00:00', 'completed', 'women', 1, 2, 0.0, 2, 1, 1, 1, 1, 20, 8, NULL);

            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, api_listing_count, accepted_listing_count, filtered_out_count, accepted_ratio, min_price_seen_cents, max_price_seen_cents, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'https://www.vinted.fr/api/v2/catalog/items?catalog[]=2001&page=1', '2026-03-25T09:05:00+00:00', 200, 1, 10, 10, 8, 2, 0.8, 3500, 9900, 2, 'https://www.vinted.fr/api/v2/catalog/items?catalog[]=2001&page=2', NULL),
              ('run-1', 2001, 2, 'https://www.vinted.fr/api/v2/catalog/items?catalog[]=2001&page=2', '2026-03-25T09:07:00+00:00', 403, 0, 0, 0, 0, 0, 0.0, NULL, NULL, 2, NULL, 'HTTP 403 challenge');

            INSERT INTO runtime_cycles (
                cycle_id, started_at, finished_at, mode, status, phase, interval_seconds,
                state_probe_limit, discovery_run_id, state_probed_count, tracked_listings,
                first_pass_only, fresh_followup, aging_followup, stale_followup, last_error,
                state_refresh_summary_json, config_json
            ) VALUES (
                'cycle-1',
                '2026-03-25T09:00:00+00:00',
                '2026-03-25T09:20:00+00:00',
                'continuous',
                'completed',
                'completed',
                3600.0,
                3,
                'run-1',
                3,
                108,
                5,
                2,
                1,
                0,
                NULL,
                '{"status": "degraded", "requested_limit": 3, "selected_target_count": 3, "probed_count": 3, "direct_signal_count": 1, "inconclusive_probe_count": 0, "degraded_probe_count": 1, "anti_bot_challenge_count": 1, "http_error_count": 0, "transport_error_count": 0, "reason_counts": {"anti_bot_challenge": 1, "buy_signal_open": 1}}',
                '{"page_limit": 1, "state_refresh_limit": 3, "max_leaf_categories": 2}'
            );
            """
        )
        conn.commit()
