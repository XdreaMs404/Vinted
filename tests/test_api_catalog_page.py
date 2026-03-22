"""Tests for the JSON API catalog page parser."""

from __future__ import annotations

import pytest

from vinted_radar.parsers.api_catalog_page import (
    ApiCatalogParseError,
    parse_api_catalog_page,
    _safe_price_to_cents,
)


# ------------------------------------------------------------------
# Fixtures / helpers
# ------------------------------------------------------------------
def _make_item(
    id: int = 42,
    title: str = "T-shirt Nike",
    brand_title: str = "Nike",
    size_title: str = "L",
    status_id: int = 3,
    price_amount: str = "12.50",
    price_currency: str = "EUR",
    total_amount: str = "14.13",
    total_currency: str = "EUR",
    photo_url: str = "https://img.vinted.fr/42.jpg",
    url: str = "/items/42-t-shirt-nike",
    **overrides,
) -> dict:
    item: dict = {
        "id": id,
        "title": title,
        "brand_title": brand_title,
        "size_title": size_title,
        "status_id": status_id,
        "price": {"amount": price_amount, "currency_code": price_currency},
        "total_item_price": {"amount": total_amount, "currency_code": total_currency},
        "photo": {"url": photo_url},
        "url": url,
    }
    item.update(overrides)
    return item


def _make_payload(
    items: list[dict] | None = None,
    current_page: int = 1,
    total_pages: int = 3,
    per_page: int = 96,
    total_entries: int = 250,
) -> dict:
    return {
        "items": items if items is not None else [_make_item()],
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "per_page": per_page,
            "total_entries": total_entries,
        },
    }


# ------------------------------------------------------------------
# Full payload → CatalogPage
# ------------------------------------------------------------------
class TestParseApiCatalogPageFull:
    """Happy-path tests with realistic payloads."""

    def test_two_items_mapped_correctly(self) -> None:
        items = [
            _make_item(id=9001, title="Robe noire", brand_title="Zara", size_title="M",
                        status_id=3, price_amount="12.50", total_amount="14.13",
                        url="/items/9001-robe-noire"),
            _make_item(id=9002, title="Pantalon", brand_title="H&M", size_title="S",
                        status_id=4, price_amount="8.00", total_amount="9.70",
                        url="/items/9002-pantalon"),
        ]
        payload = _make_payload(items=items, current_page=1, total_pages=2)

        page = parse_api_catalog_page(payload, source_catalog_id=2001, source_root_catalog_id=1904)

        assert len(page.listings) == 2
        assert page.current_page == 1
        assert page.total_pages == 2
        assert page.next_page_url is not None

        first = page.listings[0]
        assert first.listing_id == 9001
        assert first.title == "Robe noire"
        assert first.brand == "Zara"
        assert first.size_label == "M"
        assert first.condition_label == "Très bon état"
        assert first.price_amount_cents == 1250
        assert first.price_currency == "€"
        assert first.total_price_amount_cents == 1413
        assert first.total_price_currency == "€"
        assert first.canonical_url == "https://www.vinted.fr/items/9001-robe-noire"
        assert first.source_catalog_id == 2001
        assert first.source_root_catalog_id == 1904
        assert first.image_url == "https://img.vinted.fr/42.jpg"

        second = page.listings[1]
        assert second.listing_id == 9002
        assert second.brand == "H&M"
        assert second.condition_label == "Bon état"
        assert second.price_amount_cents == 800

    def test_catalog_ids_forwarded(self) -> None:
        page = parse_api_catalog_page(
            _make_payload(), source_catalog_id=555, source_root_catalog_id=100
        )
        assert page.listings[0].source_catalog_id == 555
        assert page.listings[0].source_root_catalog_id == 100

    def test_raw_card_is_a_copy_of_original_dict(self) -> None:
        item = _make_item(id=7)
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].raw_card == item
        assert page.listings[0].raw_card is not item  # defensive copy

    def test_extended_metadata_fields_are_mapped(self) -> None:
        item = _make_item(
            id=9010,
            favourite_count=17,
            view_count=223,
            user={"id": 41, "login": "alice", "profile_url": "https://www.vinted.fr/member/41"},
            photo={
                "url": "https://img.vinted.fr/9010.jpg",
                "high_resolution": {"timestamp": 1711092000},
            },
        )
        page = parse_api_catalog_page(_make_payload(items=[item]))
        listing = page.listings[0]

        assert listing.favourite_count == 17
        assert listing.view_count == 223
        assert listing.user_id == 41
        assert listing.user_login == "alice"
        assert listing.user_profile_url == "https://www.vinted.fr/member/41"
        assert listing.created_at_ts == 1711092000


# ------------------------------------------------------------------
# Price conversion
# ------------------------------------------------------------------
class TestSafePriceToCents:
    """Unit tests for the price → cents conversion helper."""

    def test_decimal_string(self) -> None:
        assert _safe_price_to_cents({"amount": "12.50", "currency_code": "EUR"}) == (1250, "€")

    def test_small_amount(self) -> None:
        assert _safe_price_to_cents({"amount": "0.99", "currency_code": "EUR"}) == (99, "€")

    def test_round_amount(self) -> None:
        assert _safe_price_to_cents({"amount": "100.00", "currency_code": "EUR"}) == (10000, "€")

    def test_integer_amount(self) -> None:
        assert _safe_price_to_cents({"amount": "25", "currency_code": "EUR"}) == (2500, "€")

    def test_float_numeric(self) -> None:
        assert _safe_price_to_cents({"amount": 8.0, "currency_code": "EUR"}) == (800, "€")

    def test_gbp_currency(self) -> None:
        assert _safe_price_to_cents({"amount": "5.99", "currency_code": "GBP"}) == (599, "£")

    def test_unknown_currency_kept_as_is(self) -> None:
        assert _safe_price_to_cents({"amount": "10", "currency_code": "CHF"}) == (1000, "CHF")

    def test_none_returns_none(self) -> None:
        assert _safe_price_to_cents(None) == (None, None)

    def test_missing_amount(self) -> None:
        assert _safe_price_to_cents({"currency_code": "EUR"}) == (None, None)

    def test_empty_string_amount(self) -> None:
        assert _safe_price_to_cents({"amount": "", "currency_code": "EUR"}) == (None, None)

    def test_comma_decimal_separator(self) -> None:
        assert _safe_price_to_cents({"amount": "12,50", "currency_code": "EUR"}) == (1250, "€")


# ------------------------------------------------------------------
# Missing / optional fields
# ------------------------------------------------------------------
class TestMissingFields:
    """Items with missing or null optional fields should not crash."""

    def test_no_brand(self) -> None:
        item = _make_item()
        del item["brand_title"]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].brand is None

    def test_no_photo(self) -> None:
        item = _make_item()
        del item["photo"]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].image_url is None

    def test_no_total_price(self) -> None:
        item = _make_item()
        del item["total_item_price"]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].total_price_amount_cents is None
        assert page.listings[0].total_price_currency is None

    def test_no_size(self) -> None:
        item = _make_item()
        del item["size_title"]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].size_label is None

    def test_no_status_id(self) -> None:
        item = _make_item()
        del item["status_id"]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].condition_label is None

    def test_brand_as_nested_object(self) -> None:
        """Some API responses nest brand info inside a dict."""
        item = _make_item()
        del item["brand_title"]
        item["brand"] = {"title": "Adidas", "id": 99}
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].brand == "Adidas"


# ------------------------------------------------------------------
# Edge cases / malformed data
# ------------------------------------------------------------------
class TestEdgeCases:
    """Structural edge cases that should be handled gracefully."""

    def test_empty_items_list(self) -> None:
        page = parse_api_catalog_page({"items": [], "pagination": {}})
        assert page.listings == []
        assert page.current_page is None
        assert page.total_pages is None
        assert page.next_page_url is None

    def test_item_without_id_is_skipped(self) -> None:
        bad_item = {"title": "Ghost item", "price": {"amount": "5", "currency_code": "EUR"}}
        good_item = _make_item(id=1)
        page = parse_api_catalog_page(_make_payload(items=[bad_item, good_item]))
        assert len(page.listings) == 1
        assert page.listings[0].listing_id == 1

    def test_non_dict_item_is_skipped(self) -> None:
        page = parse_api_catalog_page(_make_payload(items=["not a dict", _make_item(id=2)]))
        assert len(page.listings) == 1
        assert page.listings[0].listing_id == 2

    def test_non_dict_payload_raises(self) -> None:
        with pytest.raises(ApiCatalogParseError, match="dict"):
            parse_api_catalog_page([])  # type: ignore[arg-type]

    def test_non_list_items_raises(self) -> None:
        with pytest.raises(ApiCatalogParseError, match="list"):
            parse_api_catalog_page({"items": "oops"})

    def test_missing_items_key_gives_empty(self) -> None:
        page = parse_api_catalog_page({"pagination": {}})
        assert page.listings == []

    def test_absolute_url_preserved(self) -> None:
        item = _make_item(url="https://www.vinted.fr/items/99-absolute")
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].source_url == "https://www.vinted.fr/items/99-absolute"
        assert page.listings[0].canonical_url == "https://www.vinted.fr/items/99-absolute"

    def test_fallback_url_when_missing(self) -> None:
        item = _make_item(id=123)
        del item["url"]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].source_url == "https://www.vinted.fr/items/123"


# ------------------------------------------------------------------
# Status ID → condition label mapping
# ------------------------------------------------------------------
class TestStatusMapping:
    @pytest.mark.parametrize(
        "status_id, expected_label",
        [
            (1, "Neuf avec étiquette"),
            (2, "Neuf sans étiquette"),
            (3, "Très bon état"),
            (4, "Bon état"),
            (5, "Satisfaisant"),
            (6, "Mauvais état"),
        ],
    )
    def test_known_status_ids(self, status_id: int, expected_label: str) -> None:
        item = _make_item(status_id=status_id)
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].condition_label == expected_label

    def test_unknown_status_id_gives_none(self) -> None:
        item = _make_item(status_id=999)
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].condition_label is None

    def test_explicit_status_string_preferred(self) -> None:
        """When the API already gives a string 'status', prefer it."""
        item = _make_item(status_id=3)
        item["status"] = "Comme neuf"
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].condition_label == "Comme neuf"


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------
class TestPagination:
    def test_next_page_url_built_when_more_pages(self) -> None:
        page = parse_api_catalog_page(_make_payload(current_page=1, total_pages=3))
        assert page.next_page_url is not None
        assert "page=2" in page.next_page_url

    def test_no_next_page_on_last_page(self) -> None:
        page = parse_api_catalog_page(_make_payload(current_page=3, total_pages=3))
        assert page.next_page_url is None

    def test_single_page(self) -> None:
        page = parse_api_catalog_page(_make_payload(current_page=1, total_pages=1))
        assert page.next_page_url is None

    def test_total_pages_computed_from_entries(self) -> None:
        payload = {
            "items": [_make_item()],
            "pagination": {
                "current_page": 1,
                "per_page": 96,
                "total_entries": 250,
            },
        }
        page = parse_api_catalog_page(payload)
        assert page.total_pages == 3  # ceil(250 / 96) = 3
        assert page.next_page_url is not None


# ------------------------------------------------------------------
# Image extraction
# ------------------------------------------------------------------
class TestImageExtraction:
    def test_photo_url(self) -> None:
        item = _make_item(photo_url="https://img.vinted.fr/1.jpg")
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].image_url == "https://img.vinted.fr/1.jpg"

    def test_photo_full_size_url_fallback(self) -> None:
        item = _make_item()
        item["photo"] = {"full_size_url": "https://img.vinted.fr/full.jpg"}
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].image_url == "https://img.vinted.fr/full.jpg"

    def test_photos_array_fallback(self) -> None:
        item = _make_item()
        del item["photo"]
        item["photos"] = [{"url": "https://img.vinted.fr/arr.jpg"}]
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].image_url == "https://img.vinted.fr/arr.jpg"

    def test_empty_photos_array(self) -> None:
        item = _make_item()
        del item["photo"]
        item["photos"] = []
        page = parse_api_catalog_page(_make_payload(items=[item]))
        assert page.listings[0].image_url is None
