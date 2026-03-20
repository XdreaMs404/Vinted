"""Parse Vinted *JSON API* catalog responses into the shared dataclass contract.

This module mirrors the interface of :mod:`catalog_page` (HTML parser) but
operates on the *decoded* JSON payload returned by
``https://www.vinted.fr/api/v2/catalog/items``.

The public entry-point is :func:`parse_api_catalog_page`.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from vinted_radar.models import CatalogPage, ListingCard

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
BASE_URL = "https://www.vinted.fr"

# Vinted status_id → French condition label (mirrors the public UI).
# Source: observed API responses; IDs are stable across locales.
STATUS_ID_TO_CONDITION: dict[int, str] = {
    1: "Neuf avec étiquette",
    2: "Neuf sans étiquette",
    3: "Très bon état",
    4: "Bon état",
    5: "Satisfaisant",
    6: "Mauvais état",
}

# ISO-4217 codes that Vinted uses in its price objects.
_CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "EUR": "€",
    "GBP": "£",
    "USD": "$",
    "PLN": "PLN",
    "CZK": "CZK",
    "SEK": "SEK",
}

# API base path used to build next-page URLs.
_API_CATALOG_PATH = "/api/v2/catalog/items"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
class ApiCatalogParseError(RuntimeError):
    """Raised when the JSON payload is structurally unusable."""


def parse_api_catalog_page(
    payload: dict[str, Any],
    *,
    source_catalog_id: int | None = None,
    source_root_catalog_id: int | None = None,
) -> CatalogPage:
    """Convert a decoded JSON API response into a :class:`CatalogPage`.

    Parameters
    ----------
    payload:
        The full decoded JSON body from ``/api/v2/catalog/items``.
    source_catalog_id:
        Catalog id that was being scanned (forwarded to each card).
    source_root_catalog_id:
        Root catalog id (forwarded to each card).

    Returns
    -------
    CatalogPage
        Identical contract to the HTML-based ``parse_catalog_page``.
    """
    if not isinstance(payload, dict):
        raise ApiCatalogParseError(
            f"Expected a dict payload, got {type(payload).__name__}"
        )

    raw_items = payload.get("items")
    if raw_items is None:
        raw_items = []
    if not isinstance(raw_items, list):
        raise ApiCatalogParseError(
            f"Expected 'items' to be a list, got {type(raw_items).__name__}"
        )

    cards: list[ListingCard] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            logger.warning(
                "Skipping non-dict item at position %d (type=%s)",
                index,
                type(raw_item).__name__,
            )
            continue
        card = _parse_api_item(
            raw_item,
            source_catalog_id=source_catalog_id,
            source_root_catalog_id=source_root_catalog_id,
        )
        if card is not None:
            cards.append(card)

    current_page, total_pages, next_page_url = _parse_api_pagination(payload)

    return CatalogPage(
        listings=cards,
        current_page=current_page,
        total_pages=total_pages,
        next_page_url=next_page_url,
    )


# ------------------------------------------------------------------
# Item parsing
# ------------------------------------------------------------------
def _parse_api_item(
    item: dict[str, Any],
    *,
    source_catalog_id: int | None,
    source_root_catalog_id: int | None,
) -> ListingCard | None:
    """Convert a single API item dict into a :class:`ListingCard`.

    Returns ``None`` when the item cannot be meaningfully converted
    (e.g. missing ``id``).
    """
    # -- Mandatory: listing id ------------------------------------------------
    raw_id = item.get("id")
    if raw_id is None:
        logger.warning("Skipping item without 'id': %s", _truncate(item))
        return None
    try:
        listing_id = int(raw_id)
    except (TypeError, ValueError):
        logger.warning("Skipping item with non-integer 'id': %r", raw_id)
        return None

    # -- URLs -----------------------------------------------------------------
    item_path = _safe_str(item.get("url")) or _safe_str(item.get("path")) or ""
    if item_path and not item_path.startswith("http"):
        source_url = f"{BASE_URL}{item_path}" if item_path.startswith("/") else f"{BASE_URL}/{item_path}"
    elif item_path:
        source_url = item_path
    else:
        source_url = f"{BASE_URL}/items/{listing_id}"
    canonical_url = _canonicalize_url(source_url)

    # -- Text fields ----------------------------------------------------------
    title = _safe_str(item.get("title"))
    brand = _safe_str(item.get("brand_title"))
    # Fallback: some API responses nest brand inside an object.
    if brand is None and isinstance(item.get("brand"), dict):
        brand = _safe_str(item["brand"].get("title"))
    size_label = _safe_str(item.get("size_title"))
    condition_label = _resolve_condition(item)

    # -- Prices ---------------------------------------------------------------
    price_cents, price_currency = _safe_price_to_cents(item.get("price"))
    total_cents, total_currency = _safe_price_to_cents(
        item.get("total_item_price")
    )

    # -- Image ----------------------------------------------------------------
    image_url = _extract_image_url(item)

    # -- Extended metadata ----------------------------------------------------
    favourite_count = _safe_int(item.get("favourite_count"))
    view_count = _safe_int(item.get("view_count"))
    
    user = item.get("user")
    if not isinstance(user, dict):
        user = {}
    user_id = _safe_int(user.get("id"))
    user_login = _safe_str(user.get("login"))
    user_profile_url = _safe_str(user.get("profile_url"))
    
    photo = item.get("photo")
    if not isinstance(photo, dict):
        photo = {}
    high_res = photo.get("high_resolution")
    if not isinstance(high_res, dict):
        high_res = {}
    created_at_ts = _safe_int(high_res.get("timestamp"))

    return ListingCard(
        listing_id=listing_id,
        source_url=source_url,
        canonical_url=canonical_url,
        title=title,
        brand=brand,
        size_label=size_label,
        condition_label=condition_label,
        price_amount_cents=price_cents,
        price_currency=price_currency,
        total_price_amount_cents=total_cents,
        total_price_currency=total_currency,
        image_url=image_url,
        favourite_count=favourite_count,
        view_count=view_count,
        user_id=user_id,
        user_login=user_login,
        user_profile_url=user_profile_url,
        created_at_ts=created_at_ts,
        source_catalog_id=source_catalog_id,
        source_root_catalog_id=source_root_catalog_id,
        raw_card=dict(item),
    )


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------
def _parse_api_pagination(
    payload: dict[str, Any],
) -> tuple[int | None, int | None, str | None]:
    """Extract pagination from the API response.

    The Vinted API returns pagination in one of two shapes:

    1. Top-level ``pagination`` object with ``current_page`` /
       ``total_pages`` / ``per_page`` / ``total_entries``.
    2. Occasionally the page info sits directly at the root level.

    Returns ``(current_page, total_pages, next_page_url)``.
    """
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        pagination = {}

    current_page = _safe_int(pagination.get("current_page"))
    total_pages = _safe_int(pagination.get("total_pages"))
    per_page = _safe_int(pagination.get("per_page"))

    # Fallback: compute total_pages from total_entries when missing.
    if total_pages is None:
        total_entries = _safe_int(pagination.get("total_entries"))
        if total_entries is not None and per_page is not None and per_page > 0:
            total_pages = -(-total_entries // per_page)  # ceil division

    # Build next_page_url when there are more pages to fetch.
    # Only page and per_page are included; the caller (e.g. discovery.py)
    # is responsible for injecting catalog_ids and other query parameters
    # via its own URL builder — keeping this layer stateless.
    next_page_url: str | None = None
    if current_page is not None and total_pages is not None and current_page < total_pages:
        next_page = current_page + 1
        params: dict[str, str] = {"page": str(next_page)}
        if per_page is not None:
            params["per_page"] = str(per_page)
        next_page_url = f"{_API_CATALOG_PATH}?{urlencode(params)}"

    return current_page, total_pages, next_page_url


# ------------------------------------------------------------------
# Price helpers
# ------------------------------------------------------------------
def _safe_price_to_cents(
    price_obj: Any,
) -> tuple[int | None, str | None]:
    """Convert an API price object to ``(cents, currency_symbol)``.

    Handles multiple shapes seen in the wild:

    * ``{"amount": "12.50", "currency_code": "EUR"}``
    * ``{"amount": 12.5, "currency_code": "EUR"}``
    * ``{"amount": "1250", "currency_code": "EUR"}`` (already centimes)
    * ``None`` / missing keys → ``(None, None)``
    """
    if not isinstance(price_obj, dict):
        return None, None

    raw_amount = price_obj.get("amount")
    if raw_amount is None:
        return None, None

    # Currency
    raw_currency = _safe_str(price_obj.get("currency_code"))
    currency = _CURRENCY_SYMBOL_MAP.get(raw_currency or "", raw_currency)

    # Amount → float
    try:
        amount_str = str(raw_amount).strip().replace(",", ".").replace(" ", "")
        if not amount_str:
            return None, None
        amount_float = float(amount_str)
    except (TypeError, ValueError):
        logger.warning("Unparseable price amount: %r", raw_amount)
        return None, None

    # The API *normally* returns amounts as decimal euros (e.g. "12.50").
    # Convert to centimes: multiply by 100 and round to avoid float drift.
    cents = round(amount_float * 100)

    return cents, currency


# ------------------------------------------------------------------
# Condition / status helpers
# ------------------------------------------------------------------
def _resolve_condition(item: dict[str, Any]) -> str | None:
    """Resolve the human-readable condition label.

    Tries, in order:
    1. ``item["status"]`` (string label already present in some responses)
    2. ``STATUS_ID_TO_CONDITION[item["status_id"]]``
    """
    explicit_status = _safe_str(item.get("status"))
    if explicit_status:
        return explicit_status

    status_id = _safe_int(item.get("status_id"))
    if status_id is not None:
        return STATUS_ID_TO_CONDITION.get(status_id)

    return None


# ------------------------------------------------------------------
# Image helpers
# ------------------------------------------------------------------
def _extract_image_url(item: dict[str, Any]) -> str | None:
    """Extract the best available image URL from an API item.

    Tries (in order):
    1. ``item["photo"]["url"]``
    2. ``item["photo"]["full_size_url"]``
    3. ``item["photos"][0]["url"]``
    4. ``item["photos"][0]["full_size_url"]``
    """
    photo = item.get("photo")
    if isinstance(photo, dict):
        for key in ("url", "full_size_url"):
            url = _safe_str(photo.get(key))
            if url:
                return url

    photos = item.get("photos")
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            for key in ("url", "full_size_url"):
                url = _safe_str(first.get(key))
                if url:
                    return url

    return None


# ------------------------------------------------------------------
# Generic helpers
# ------------------------------------------------------------------
def _safe_str(value: Any) -> str | None:
    """Return a cleaned string or ``None`` if empty / wrong type."""
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip() or None
    cleaned = value.strip()
    return cleaned or None


def _safe_int(value: Any) -> int | None:
    """Return an ``int`` or ``None`` when coercion fails."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _canonicalize_url(url: str) -> str:
    """Strip query-string and fragment from a URL."""
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _truncate(obj: Any, *, limit: int = 120) -> str:
    """Produce a short repr for logging."""
    text = repr(obj)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text
