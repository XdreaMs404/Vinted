from __future__ import annotations

from pathlib import Path

import pytest

from vinted_radar.parsers.catalog_tree import CatalogTreeParseError, parse_catalog_tree_from_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_catalog_tree_parser_extracts_only_supported_roots() -> None:
    html = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    catalogs = parse_catalog_tree_from_html(html)

    assert [catalog.catalog_id for catalog in catalogs if catalog.depth == 0] == [1904, 5]
    assert all(catalog.root_title in {"Femmes", "Hommes"} for catalog in catalogs)
    assert [catalog.catalog_id for catalog in catalogs if catalog.is_leaf] == [2001, 3001]


def test_catalog_tree_parser_raises_when_embedded_payload_is_missing() -> None:
    with pytest.raises(CatalogTreeParseError):
        parse_catalog_tree_from_html("<html><body><script>window.__data = [];</script></body></html>")
