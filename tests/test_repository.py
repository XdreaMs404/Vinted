from __future__ import annotations

import sqlite3
from pathlib import Path

from vinted_radar.models import CatalogNode, ListingCard
from vinted_radar.repository import RadarRepository


EXPECTED_TABLES = {
    "catalog_scans",
    "catalogs",
    "discovery_runs",
    "item_page_probes",
    "listing_discoveries",
    "listing_observations",
    "listings",
}


def test_repository_bootstraps_current_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"

    with RadarRepository(db_path):
        pass

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert EXPECTED_TABLES.issubset(tables)


def test_listing_observations_stay_one_row_per_run_and_accumulate_sightings(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"

    women_root = CatalogNode(
        catalog_id=1904,
        root_catalog_id=1904,
        root_title="Femmes",
        parent_catalog_id=None,
        title="Femmes",
        code="WOMEN_ROOT",
        url="https://www.vinted.fr/catalog/1904-women",
        path=("Femmes",),
        depth=0,
        is_leaf=False,
        allow_browsing_subcategories=True,
        order_index=0,
    )
    dresses = CatalogNode(
        catalog_id=2001,
        root_catalog_id=1904,
        root_title="Femmes",
        parent_catalog_id=1904,
        title="Robes",
        code="WOMEN_DRESSES",
        url="https://www.vinted.fr/catalog/2001-womens-dresses",
        path=("Femmes", "Robes"),
        depth=1,
        is_leaf=True,
        allow_browsing_subcategories=True,
        order_index=10,
    )
    listing = ListingCard(
        listing_id=9001,
        source_url="https://www.vinted.fr/items/9001-robe-noire?referrer=catalog",
        canonical_url="https://www.vinted.fr/items/9001-robe-noire",
        title="Robe noire",
        brand="Zara",
        size_label="M",
        condition_label="Très bon état",
        price_amount_cents=1250,
        price_currency="€",
        total_price_amount_cents=1413,
        total_price_currency="€",
        image_url="https://images1.vinted.net/t/women-9001.webp",
        source_catalog_id=2001,
        source_root_catalog_id=1904,
        raw_card={"overlay_title": "Robe noire"},
    )

    with RadarRepository(db_path) as repository:
        run_id = repository.start_run(root_scope="women", page_limit=1, max_leaf_categories=1, request_delay_seconds=0.0)
        repository.upsert_catalogs([women_root, dresses], synced_at="2026-03-17T10:00:00+00:00")
        repository.upsert_listing(listing, discovered_at="2026-03-17T10:05:00+00:00", primary_catalog_id=2001, primary_root_catalog_id=1904, run_id=run_id)

        repository.record_listing_observation(
            run_id=run_id,
            listing=listing,
            observed_at="2026-03-17T10:05:00+00:00",
            source_catalog_id=2001,
            source_page_number=1,
            card_position=1,
        )
        repository.record_listing_observation(
            run_id=run_id,
            listing=listing,
            observed_at="2026-03-17T10:05:10+00:00",
            source_catalog_id=2001,
            source_page_number=1,
            card_position=3,
        )

        row = repository.connection.execute(
            "SELECT observed_at, first_card_position, sighting_count FROM listing_observations WHERE run_id = ? AND listing_id = ?",
            (run_id, 9001),
        ).fetchone()

    assert row is not None
    assert row["observed_at"] == "2026-03-17T10:05:00+00:00"
    assert row["first_card_position"] == 1
    assert row["sighting_count"] == 2


def test_upsert_listing_persists_extended_catalog_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    women_root = CatalogNode(
        catalog_id=1904,
        root_catalog_id=1904,
        root_title="Femmes",
        parent_catalog_id=None,
        title="Femmes",
        code="WOMEN_ROOT",
        url="https://www.vinted.fr/catalog/1904-women",
        path=("Femmes",),
        depth=0,
        is_leaf=False,
        allow_browsing_subcategories=True,
        order_index=0,
    )
    dresses = CatalogNode(
        catalog_id=2001,
        root_catalog_id=1904,
        root_title="Femmes",
        parent_catalog_id=1904,
        title="Robes",
        code="WOMEN_DRESSES",
        url="https://www.vinted.fr/catalog/2001-womens-dresses",
        path=("Femmes", "Robes"),
        depth=1,
        is_leaf=True,
        allow_browsing_subcategories=True,
        order_index=10,
    )
    listing = ListingCard(
        listing_id=9010,
        source_url="https://www.vinted.fr/items/9010-robe-premium?referrer=catalog",
        canonical_url="https://www.vinted.fr/items/9010-robe-premium",
        title="Robe premium",
        brand="Sézane",
        size_label="S",
        condition_label="Très bon état",
        price_amount_cents=9900,
        price_currency="€",
        total_price_amount_cents=10450,
        total_price_currency="€",
        image_url="https://images1.vinted.net/t/women-9010.webp",
        favourite_count=17,
        view_count=223,
        user_id=41,
        user_login="alice",
        user_profile_url="https://www.vinted.fr/member/41",
        created_at_ts=1711092000,
        source_catalog_id=2001,
        source_root_catalog_id=1904,
        raw_card={"overlay_title": "Robe premium"},
    )

    with RadarRepository(db_path) as repository:
        run_id = repository.start_run(root_scope="women", page_limit=1, max_leaf_categories=1, request_delay_seconds=0.0)
        repository.upsert_catalogs([women_root, dresses], synced_at="2026-03-17T10:00:00+00:00")
        repository.upsert_listing(
            listing,
            discovered_at="2026-03-17T10:05:00+00:00",
            primary_catalog_id=2001,
            primary_root_catalog_id=1904,
            run_id=run_id,
        )
        row = repository.connection.execute(
            "SELECT favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts FROM listings WHERE listing_id = ?",
            (9010,),
        ).fetchone()

    assert row is not None
    assert row["favourite_count"] == 17
    assert row["view_count"] == 223
    assert row["user_id"] == 41
    assert row["user_login"] == "alice"
    assert row["user_profile_url"] == "https://www.vinted.fr/member/41"
    assert row["created_at_ts"] == 1711092000


def test_explorer_filter_options_include_comparison_dimensions(tmp_path: Path) -> None:
    from tests.test_dashboard import _seed_dashboard_db

    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        options = repository.explorer_filter_options(now="2026-03-19T12:00:00+00:00")

    assert any(item["value"] == "active" for item in options["states"])
    assert any(item["value"] == "20_to_39_eur" for item in options["price_bands"])


def test_repository_reuses_materialized_overview_snapshot_for_same_now(tmp_path: Path) -> None:
    from tests.test_dashboard import _seed_dashboard_db

    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        calls = {"count": 0}
        original = repository._rebuild_overview_state_snapshot

        def _wrapped(*, now_dt):
            calls["count"] += 1
            return original(now_dt=now_dt)

        repository._rebuild_overview_state_snapshot = _wrapped  # type: ignore[method-assign]
        fixed_now = "2026-03-19T12:00:00+00:00"

        repository.explorer_filter_options(now=fixed_now)
        repository.overview_snapshot(now=fixed_now)
        repository.explorer_snapshot(now=fixed_now)

        assert calls["count"] == 1

        repository.overview_snapshot(now="2026-03-19T12:00:01+00:00")
        assert calls["count"] == 2


def test_repository_migrates_catalog_scan_telemetry_columns_without_faking_legacy_acceptance(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-scans.db"

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE catalog_scans (
                run_id TEXT NOT NULL,
                catalog_id INTEGER NOT NULL,
                page_number INTEGER NOT NULL,
                requested_url TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                response_status INTEGER,
                success INTEGER NOT NULL CHECK (success IN (0, 1)),
                listing_count INTEGER NOT NULL DEFAULT 0,
                pagination_total_pages INTEGER,
                next_page_url TEXT,
                error_message TEXT,
                PRIMARY KEY (run_id, catalog_id, page_number)
            );

            INSERT INTO catalog_scans (
                run_id,
                catalog_id,
                page_number,
                requested_url,
                fetched_at,
                response_status,
                success,
                listing_count,
                pagination_total_pages,
                next_page_url,
                error_message
            ) VALUES (
                'run-1',
                2001,
                1,
                'https://www.vinted.fr/api/v2/catalog/items?catalog_ids=2001&page=1',
                '2026-03-23T10:00:00+00:00',
                200,
                1,
                96,
                3,
                NULL,
                NULL
            );
            """
        )
        connection.commit()

    with RadarRepository(db_path) as repository:
        columns = {
            row["name"]
            for row in repository.connection.execute("PRAGMA table_info(catalog_scans)")
        }
        row = repository.connection.execute(
            """
            SELECT
                listing_count,
                api_listing_count,
                accepted_listing_count,
                filtered_out_count,
                accepted_ratio,
                min_price_seen_cents,
                max_price_seen_cents
            FROM catalog_scans
            WHERE run_id = 'run-1' AND catalog_id = 2001 AND page_number = 1
            """
        ).fetchone()

    assert {
        "api_listing_count",
        "accepted_listing_count",
        "filtered_out_count",
        "accepted_ratio",
        "min_price_seen_cents",
        "max_price_seen_cents",
    }.issubset(columns)
    assert row is not None
    assert row["listing_count"] == 96
    assert row["api_listing_count"] == 96
    assert row["accepted_listing_count"] is None
    assert row["filtered_out_count"] is None
    assert row["accepted_ratio"] is None
    assert row["min_price_seen_cents"] is None
    assert row["max_price_seen_cents"] is None


def test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE listings (
                listing_id INTEGER PRIMARY KEY,
                canonical_url TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT,
                brand TEXT,
                size_label TEXT,
                condition_label TEXT,
                price_amount_cents INTEGER,
                price_currency TEXT,
                total_price_amount_cents INTEGER,
                total_price_currency TEXT,
                image_url TEXT,
                primary_catalog_id INTEGER,
                primary_root_catalog_id INTEGER,
                first_discovered_at TEXT NOT NULL,
                last_discovered_at TEXT NOT NULL,
                last_seen_run_id TEXT NOT NULL,
                last_card_payload_json TEXT NOT NULL
            );
            """
        )
        connection.commit()

    with RadarRepository(db_path) as repository:
        columns = {
            row["name"]
            for row in repository.connection.execute("PRAGMA table_info(listings)")
        }
        indexes = {
            row["name"]
            for row in repository.connection.execute("PRAGMA index_list(listings)")
        }

    assert {"favourite_count", "view_count", "user_id", "user_login", "user_profile_url", "created_at_ts"}.issubset(columns)
    assert {
        "idx_listings_created_at_ts",
        "idx_listings_favourite_count",
        "idx_listings_view_count",
    }.issubset(indexes)
