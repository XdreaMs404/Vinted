from __future__ import annotations

from pathlib import Path

from vinted_radar.parsers.catalog_page import parse_catalog_page
from vinted_radar.parsers.catalog_tree import parse_catalog_tree_from_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_catalog_tree_extracts_homme_and_femme_nodes() -> None:
    html = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    catalogs = parse_catalog_tree_from_html(html)

    assert len(catalogs) == 6
    assert catalogs[0].title == "Femmes"
    assert catalogs[-1].root_title == "Hommes"
    assert catalogs[-1].title == "Pantalons"
    assert [catalog.catalog_id for catalog in catalogs if catalog.is_leaf] == [2001, 3001]


def test_parse_catalog_page_normalizes_listing_fields_and_pagination() -> None:
    html = (FIXTURES / "catalog-page-women.html").read_text(encoding="utf-8")

    page = parse_catalog_page(html, source_catalog_id=2001, source_root_catalog_id=1904)

    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.next_page_url == "/catalog/2001-womens-dresses?page=2"
    assert len(page.listings) == 2

    first = page.listings[0]
    assert first.listing_id == 9001
    assert first.title == "Robe noire"
    assert first.brand == "Zara"
    assert first.size_label == "M"
    assert first.condition_label == "Très bon état"
    assert first.price_amount_cents == 1250
    assert first.total_price_amount_cents == 1413
    assert first.canonical_url == "https://www.vinted.fr/items/9001-robe-noire"
    assert first.raw_card["fragments"]["description_subtitle"] == "M · Très bon état"
