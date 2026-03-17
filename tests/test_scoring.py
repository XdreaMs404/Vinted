from __future__ import annotations

from pathlib import Path

from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import build_listing_scores, build_market_summary, build_rankings


def _evaluation(
    listing_id: int,
    *,
    title: str,
    catalog_id: int,
    catalog_path: str,
    root_title: str = "Femmes",
    state_code: str = "active",
    basis_kind: str = "observed",
    confidence_label: str = "high",
    confidence_score: float = 0.9,
    freshness_bucket: str = "fresh-followup",
    observation_count: int = 2,
    follow_up_miss_count: int = 0,
    price_amount_cents: int | None = 2000,
    condition_label: str = "Très bon état",
    brand: str = "Zara",
    last_seen_age_hours: float = 4.0,
) -> dict[str, object]:
    return {
        "listing_id": listing_id,
        "title": title,
        "primary_catalog_id": catalog_id,
        "primary_catalog_path": catalog_path,
        "root_title": root_title,
        "state_code": state_code,
        "basis_kind": basis_kind,
        "confidence_label": confidence_label,
        "confidence_score": confidence_score,
        "freshness_bucket": freshness_bucket,
        "observation_count": observation_count,
        "follow_up_miss_count": follow_up_miss_count,
        "price_amount_cents": price_amount_cents,
        "price_currency": "€" if price_amount_cents is not None else None,
        "condition_label": condition_label,
        "brand": brand,
        "last_seen_age_hours": last_seen_age_hours,
    }


def test_demand_and_premium_rankings_stay_separate_and_explained() -> None:
    evaluations = [
        _evaluation(1, title="Sold probable premium", catalog_id=2001, catalog_path="Femmes > Robes", state_code="sold_probable", basis_kind="inferred", confidence_label="medium", confidence_score=0.72, follow_up_miss_count=3, price_amount_cents=5000, brand="Sandro"),
        _evaluation(2, title="Active cheap", catalog_id=2001, catalog_path="Femmes > Robes", state_code="active", price_amount_cents=1200, brand="Sandro"),
        _evaluation(3, title="Active mid", catalog_id=2001, catalog_path="Femmes > Robes", state_code="active", price_amount_cents=2200, brand="Sandro"),
        _evaluation(4, title="Active high", catalog_id=2001, catalog_path="Femmes > Robes", state_code="active", price_amount_cents=3200, brand="Sandro"),
        _evaluation(5, title="Unavailable decent", catalog_id=2001, catalog_path="Femmes > Robes", state_code="unavailable_non_conclusive", basis_kind="inferred", confidence_label="low", confidence_score=0.46, follow_up_miss_count=1, price_amount_cents=2600, brand="Sandro"),
    ]

    scored = build_listing_scores(evaluations)
    demand_top = build_rankings(scored, kind="demand", limit=3)
    premium_top = build_rankings(scored, kind="premium", limit=3)

    assert demand_top[0]["listing_id"] == 1
    assert premium_top[0]["listing_id"] == 1
    assert premium_top[0]["premium_score"] > premium_top[1]["premium_score"]
    assert premium_top[0]["score_explanation"]["context"]["sample_size"] >= 4
    assert premium_top[0]["score_explanation"]["context"]["price_band_label"] == "premium"


def test_premium_gracefully_degrades_without_supported_context() -> None:
    evaluations = [
        _evaluation(10, title="Sparse premium", catalog_id=9001, catalog_path="Femmes > Rare", price_amount_cents=4000, brand="RareBrand", condition_label="Neuf"),
        _evaluation(11, title="Sparse peer", catalog_id=9002, catalog_path="Femmes > Other", price_amount_cents=1500, brand="Other", condition_label="Bon état"),
    ]

    scored = build_listing_scores(evaluations)
    item = next(row for row in scored if row["listing_id"] == 10)

    assert item["score_explanation"]["context"] is None
    assert item["premium_score"] == round(item["demand_score"] * 0.85, 2)


def test_market_summary_reports_performing_and_rising_segments(tmp_path: Path) -> None:
    db_path = tmp_path / "summary.db"
    with RadarRepository(db_path) as repository:
        repository.connection.executescript(
            """
            INSERT INTO discovery_runs (run_id, started_at, finished_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds)
            VALUES
              ('run-1', '2026-03-17T10:00:00+00:00', '2026-03-17T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0),
              ('run-2', '2026-03-18T10:00:00+00:00', '2026-03-18T10:10:00+00:00', 'completed', 'both', 1, 2, 0.0);
            INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at)
            VALUES
              (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'u', 'Femmes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00'),
              (2301, 2301, 'Hommes', NULL, 'Hommes', 'MEN_ROOT', 'u', 'Hommes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00'),
              (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'u', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00'),
              (3001, 2301, 'Hommes', 2301, 'Pantalons', 'MEN_TROUSERS', 'u', 'Hommes > Pantalons', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00');
            INSERT INTO catalog_scans (run_id, catalog_id, page_number, requested_url, fetched_at, response_status, success, listing_count, pagination_total_pages, next_page_url, error_message)
            VALUES
              ('run-1', 2001, 1, 'u', '2026-03-17T10:05:00+00:00', 200, 1, 2, 1, NULL, NULL),
              ('run-2', 2001, 1, 'u', '2026-03-18T10:05:00+00:00', 200, 1, 4, 1, NULL, NULL),
              ('run-1', 3001, 1, 'u', '2026-03-17T10:05:00+00:00', 200, 1, 4, 1, NULL, NULL),
              ('run-2', 3001, 1, 'u', '2026-03-18T10:05:00+00:00', 200, 1, 3, 1, NULL, NULL);
            """
        )
        evaluations = [
            _evaluation(1, title="A", catalog_id=2001, catalog_path="Femmes > Robes", state_code="sold_probable", basis_kind="inferred", confidence_label="medium", confidence_score=0.72, follow_up_miss_count=3, price_amount_cents=5000),
            _evaluation(2, title="B", catalog_id=2001, catalog_path="Femmes > Robes", state_code="unavailable_non_conclusive", basis_kind="inferred", confidence_label="low", confidence_score=0.46, follow_up_miss_count=1, price_amount_cents=3200),
            _evaluation(3, title="C", catalog_id=2001, catalog_path="Femmes > Robes", state_code="active", observation_count=1, freshness_bucket="first-pass-only", price_amount_cents=2500),
            _evaluation(4, title="D", catalog_id=3001, catalog_path="Hommes > Pantalons", root_title="Hommes", state_code="active", price_amount_cents=1800),
            _evaluation(5, title="E", catalog_id=3001, catalog_path="Hommes > Pantalons", root_title="Hommes", state_code="active", price_amount_cents=1600),
            _evaluation(6, title="F", catalog_id=3001, catalog_path="Hommes > Pantalons", root_title="Hommes", state_code="active", price_amount_cents=1400),
        ]
        scores = build_listing_scores(evaluations)
        summary = build_market_summary(scores, repository, now="2026-03-18T12:00:00+00:00", limit=2)

    assert summary["performing_segments"][0]["catalog_id"] == 2001
    assert summary["rising_segments"][0]["catalog_id"] == 2001
    assert summary["performing_segments"][0]["avg_demand_score"] > summary["performing_segments"][1]["avg_demand_score"]
