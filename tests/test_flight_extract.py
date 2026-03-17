from __future__ import annotations

import pytest

from vinted_radar.parsers.catalog_tree import CatalogTreeParseError, _extract_escaped_json_array


def test_extract_escaped_json_array_handles_nested_payloads() -> None:
    payload = 'prefix [{\"id\":1,\"catalogs\":[{\"id\":2,\"catalogs\":[]}]}], suffix'

    extracted = _extract_escaped_json_array(payload)

    assert extracted == '[{\"id\":1,\"catalogs\":[{\"id\":2,\"catalogs\":[]}]}]'


def test_extract_escaped_json_array_raises_without_array_start() -> None:
    with pytest.raises(CatalogTreeParseError):
        _extract_escaped_json_array('prefix {\"catalogTree\":{}}')
