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
