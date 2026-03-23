from __future__ import annotations

from pathlib import Path

from tests.test_dashboard import _seed_dashboard_db
from vinted_radar.repository import RadarRepository


NOW = "2026-03-19T12:00:00+00:00"


def test_explorer_filter_options_expose_state_and_price_band_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        options = repository.explorer_filter_options(now=NOW)

    assert options["tracked_listings"] == 4
    assert [item["value"] for item in options["states"][:4]] == [
        "all",
        "active",
        "sold_probable",
        "deleted",
    ]
    price_band_counts = {item["value"]: item["count"] for item in options["price_bands"][1:]}
    assert price_band_counts == {
        "under_20_eur": 1,
        "20_to_39_eur": 2,
        "40_plus_eur": 1,
    }


def test_listing_explorer_page_filters_state_and_price_band_from_classified_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        page = repository.listing_explorer_page(
            state="sold_probable",
            price_band="20_to_39_eur",
            sort="price_desc",
            page=1,
            page_size=5,
            now=NOW,
        )

    assert page["total_listings"] == 1
    assert [item["listing_id"] for item in page["items"]] == [9002]
    assert page["items"][0]["state_code"] == "sold_probable"
    assert page["items"][0]["price_band_code"] == "20_to_39_eur"
    assert page["items"][0]["state_label"] == "Vendu probable"


def test_explorer_snapshot_returns_low_support_comparisons_with_drilldown_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with RadarRepository(db_path) as repository:
        snapshot = repository.explorer_snapshot(
            root="Femmes",
            state="active",
            price_band="40_plus_eur",
            sort="price_desc",
            page=1,
            page_size=12,
            support_threshold=2,
            now=NOW,
        )

    assert snapshot["summary"]["inventory"]["matched_listings"] == 1
    assert snapshot["summary"]["inventory"]["sold_like_count"] == 0
    assert [item["listing_id"] for item in snapshot["page"]["items"]] == [9003]

    brand_module = snapshot["comparisons"]["brand"]
    assert brand_module["status"] == "thin-support"
    assert brand_module["supported_rows"] == 0
    assert brand_module["rows"][0]["drilldown"]["filters"] == {"brand": "Maje"}
    assert brand_module["rows"][0]["honesty"]["low_support"] is True

    sold_state_module = snapshot["comparisons"]["sold_state"]
    assert sold_state_module["rows"][0]["drilldown"]["filters"] == {"state": "active"}
    assert sold_state_module["rows"][0]["inventory"]["support_count"] == 1
