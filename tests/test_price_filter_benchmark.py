from __future__ import annotations

import json
from pathlib import Path

from tests.test_discovery_service import (
    FIXTURES,
    FakeHttpClient,
    _make_api_item,
    _make_api_page,
)
from vinted_radar.http import FetchedPage
from vinted_radar.models import CatalogNode
from vinted_radar.price_filter_benchmark import (
    BenchmarkPageRecord,
    PriceFilterBenchmarkOptions,
    build_price_filter_benchmark_report,
    render_price_filter_benchmark_markdown,
    run_price_filter_benchmark,
    write_price_filter_benchmark_report,
)
from vinted_radar.services.discovery import _build_api_catalog_url


def _catalog(*, catalog_id: int, root_catalog_id: int, root_title: str, title: str, path: tuple[str, ...]) -> CatalogNode:
    return CatalogNode(
        catalog_id=catalog_id,
        root_catalog_id=root_catalog_id,
        root_title=root_title,
        parent_catalog_id=root_catalog_id if catalog_id != root_catalog_id else None,
        title=title,
        code=f"CAT_{catalog_id}",
        url=f"https://www.vinted.fr/catalog/{catalog_id}",
        path=path,
        depth=len(path) - 1,
        is_leaf=True,
        allow_browsing_subcategories=True,
        order_index=1,
    )


def test_build_price_filter_benchmark_report_aggregates_deltas_and_catalog_summaries() -> None:
    catalog = _catalog(
        catalog_id=2001,
        root_catalog_id=1904,
        root_title="Femmes",
        title="Robes",
        path=("Femmes", "Robes"),
    )
    options = PriceFilterBenchmarkOptions(
        page_limit=2,
        max_leaf_categories=1,
        root_scope="women",
        min_price=30.0,
        request_delay=0.0,
    )
    page_records = [
        BenchmarkPageRecord(
            pair_index=1,
            mode="bounded",
            catalog_id=2001,
            catalog_path="Femmes > Robes",
            root_title="Femmes",
            page_number=1,
            requested_url="https://example.test/bounded-1",
            requested_at="2026-03-23T19:00:00+00:00",
            duration_ms=120,
            response_status=200,
            success=True,
            api_listing_count=4,
            accepted_listing_count=4,
            filtered_out_count=0,
            accepted_ratio=1.0,
            min_price_seen_cents=3500,
            max_price_seen_cents=12000,
            pagination_total_pages=2,
            error_kind=None,
            error_message=None,
            challenge_suspected=False,
        ),
        BenchmarkPageRecord(
            pair_index=1,
            mode="unbounded",
            catalog_id=2001,
            catalog_path="Femmes > Robes",
            root_title="Femmes",
            page_number=1,
            requested_url="https://example.test/unbounded-1",
            requested_at="2026-03-23T19:00:03+00:00",
            duration_ms=140,
            response_status=200,
            success=True,
            api_listing_count=4,
            accepted_listing_count=2,
            filtered_out_count=2,
            accepted_ratio=0.5,
            min_price_seen_cents=1200,
            max_price_seen_cents=12000,
            pagination_total_pages=2,
            error_kind=None,
            error_message=None,
            challenge_suspected=False,
        ),
        BenchmarkPageRecord(
            pair_index=2,
            mode="bounded",
            catalog_id=2001,
            catalog_path="Femmes > Robes",
            root_title="Femmes",
            page_number=2,
            requested_url="https://example.test/bounded-2",
            requested_at="2026-03-23T19:00:06+00:00",
            duration_ms=160,
            response_status=403,
            success=False,
            api_listing_count=None,
            accepted_listing_count=None,
            filtered_out_count=None,
            accepted_ratio=None,
            min_price_seen_cents=None,
            max_price_seen_cents=None,
            pagination_total_pages=None,
            error_kind="http_403",
            error_message="HTTP 403",
            challenge_suspected=True,
        ),
        BenchmarkPageRecord(
            pair_index=2,
            mode="unbounded",
            catalog_id=2001,
            catalog_path="Femmes > Robes",
            root_title="Femmes",
            page_number=2,
            requested_url="https://example.test/unbounded-2",
            requested_at="2026-03-23T19:00:09+00:00",
            duration_ms=180,
            response_status=200,
            success=True,
            api_listing_count=4,
            accepted_listing_count=1,
            filtered_out_count=3,
            accepted_ratio=0.25,
            min_price_seen_cents=900,
            max_price_seen_cents=11000,
            pagination_total_pages=2,
            error_kind=None,
            error_message=None,
            challenge_suspected=False,
        ),
    ]

    report = build_price_filter_benchmark_report(
        options=options,
        selected_catalogs=[catalog],
        page_records=page_records,
    )

    bounded = report["aggregates"]["by_mode"]["bounded"]
    unbounded = report["aggregates"]["by_mode"]["unbounded"]
    delta = report["aggregates"]["delta"]
    paired_summary = report["aggregates"]["paired_delta_summary"]
    catalog_summary = report["aggregates"]["by_catalog"][0]
    markdown = render_price_filter_benchmark_markdown(report)

    assert bounded["request_count"] == 2
    assert bounded["success_count"] == 1
    assert bounded["failure_count"] == 1
    assert bounded["challenge_suspected_count"] == 1
    assert bounded["accepted_listing_count_total"] == 4
    assert bounded["accepted_listings_per_request"] == 2.0
    assert bounded["accepted_ratio_weighted"] == 1.0

    assert unbounded["request_count"] == 2
    assert unbounded["success_count"] == 2
    assert unbounded["accepted_listing_count_total"] == 3
    assert unbounded["accepted_listings_per_request"] == 1.5
    assert unbounded["accepted_ratio_weighted"] == 0.375

    assert delta["accepted_listings_per_request_delta"] == 0.5
    assert delta["accepted_ratio_weighted_delta"] == 0.625
    assert delta["challenge_suspected_count_delta"] == 1

    assert paired_summary["comparable_pair_count"] == 2
    assert paired_summary["accepted_ratio_delta_mean"] == 0.5
    assert paired_summary["accepted_listing_count_delta_mean"] == 2.0

    assert catalog_summary["catalog_id"] == 2001
    assert catalog_summary["bounded"]["challenge_suspected_count"] == 1
    assert catalog_summary["delta"]["accepted_listings_per_request_delta"] == 0.5

    assert "# Price filter benchmark" in markdown
    assert "| bounded | 2 | 1 | 1 | 1 |" in markdown
    assert "Femmes > Robes" in markdown


def test_run_price_filter_benchmark_pairs_modes_and_writes_reports(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_bounded_url = _build_api_catalog_url(2001, 1, price_from=30.0, price_to=0.0)
    women_unbounded_url = _build_api_catalog_url(2001, 1, price_from=0.0, price_to=0.0)
    men_bounded_url = _build_api_catalog_url(3001, 1, price_from=30.0, price_to=0.0)
    men_unbounded_url = _build_api_catalog_url(3001, 1, price_from=0.0, price_to=0.0)

    women_bounded_items = [
        _make_api_item(9401, title="Robe premium", brand="Zara", size="M", status_id=3, price="45.00", total_price="49.00", image_url="https://images1.vinted.net/t/women-9401.webp"),
    ]
    women_unbounded_items = [
        _make_api_item(9401, title="Robe premium", brand="Zara", size="M", status_id=3, price="45.00", total_price="49.00", image_url="https://images1.vinted.net/t/women-9401.webp"),
        _make_api_item(9402, title="Robe bruit", brand="Zara", size="S", status_id=3, price="12.00", total_price="14.00", image_url="https://images1.vinted.net/t/women-9402.webp"),
    ]
    men_bounded_items = [
        _make_api_item(9501, title="Veste homme", brand="Carhartt", size="L", status_id=3, price="55.00", total_price="58.00", image_url="https://images1.vinted.net/t/men-9501.webp"),
    ]
    men_unbounded_items = [
        _make_api_item(9501, title="Veste homme", brand="Carhartt", size="L", status_id=3, price="55.00", total_price="58.00", image_url="https://images1.vinted.net/t/men-9501.webp"),
        _make_api_item(9502, title="Tee shirt", brand="Nike", size="M", status_id=3, price="9.00", total_price="11.00", image_url="https://images1.vinted.net/t/men-9502.webp"),
    ]

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_bounded_url: FetchedPage(women_bounded_url, 200, _make_api_page(women_bounded_items, current_page=1, total_pages=1)),
        women_unbounded_url: FetchedPage(women_unbounded_url, 200, _make_api_page(women_unbounded_items, current_page=1, total_pages=1)),
        men_unbounded_url: FetchedPage(men_unbounded_url, 200, _make_api_page(men_unbounded_items, current_page=1, total_pages=1)),
        men_bounded_url: FetchedPage(men_bounded_url, 200, _make_api_page(men_bounded_items, current_page=1, total_pages=1)),
    }

    report = run_price_filter_benchmark(
        PriceFilterBenchmarkOptions(
            page_limit=1,
            max_leaf_categories=2,
            root_scope="both",
            min_price=30.0,
            request_delay=0.0,
            mode_order="alternate",
        ),
        http_client=FakeHttpClient(pages),
    )

    json_path = tmp_path / "benchmark.json"
    markdown_path = tmp_path / "benchmark.md"
    written = write_price_filter_benchmark_report(
        report,
        json_path=json_path,
        markdown_path=markdown_path,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    page_modes = [row["mode"] for row in payload["pages"]]
    delta = payload["aggregates"]["delta"]

    assert written["json"] == str(json_path)
    assert written["markdown"] == str(markdown_path)
    assert len(payload["catalogs"]) == 2
    assert len(payload["pages"]) == 4
    assert page_modes[:2] == ["bounded", "unbounded"]
    assert page_modes[2:] == ["unbounded", "bounded"]
    assert payload["aggregates"]["by_mode"]["bounded"]["accepted_listing_count_total"] == 2
    assert payload["aggregates"]["by_mode"]["unbounded"]["accepted_listing_count_total"] == 2
    assert delta["accepted_ratio_weighted_delta"] == 0.5
    assert delta["accepted_listings_per_request_delta"] == 0.0
    assert "# Price filter benchmark" in markdown
    assert "Per-catalog summary" in markdown
