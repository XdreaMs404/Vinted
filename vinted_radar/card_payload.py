from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import re
from urllib.parse import urlsplit, urlunsplit

CARD_EVIDENCE_SCHEMA_VERSION = 1
CARD_EVIDENCE_SOURCE_HTML = "html"
CARD_EVIDENCE_SOURCE_API = "api"

STATUS_ID_TO_CONDITION: dict[int, str] = {
    1: "Neuf avec étiquette",
    2: "Neuf sans étiquette",
    3: "Très bon état",
    4: "Bon état",
    5: "Satisfaisant",
    6: "Mauvais état",
}

_MONEY_RE = re.compile(r"(?P<amount>\d[\d\s.,]*)\s*(?P<currency>€|EUR|£|\$)")
_SUBTITLE_SPLIT_RE = re.compile(r"\s*[·•|]\s*")
_HTML_HINT_KEYS = frozenset(
    {
        "data_testid",
        "overlay_title",
        "image_alt",
        "description_title",
        "description_subtitle",
        "price_text",
        "total_price_text",
    }
)
_API_HINT_KEYS = frozenset(
    {
        "title",
        "brand_title",
        "size_title",
        "status",
        "status_id",
        "price",
        "total_item_price",
        "brand",
    }
)


def build_html_card_evidence(
    *,
    data_testid: str | None,
    overlay_title: str | None,
    image_alt: str | None,
    description_title: str | None,
    description_subtitle: str | None,
    price_text: str | None,
    total_price_text: str | None,
) -> dict[str, Any]:
    """Return the minimal HTML card evidence contract.

    The hot path keeps only the visible fragments required to explain how the
    normalized listing card was derived. Full HTML and unrelated attributes are
    intentionally excluded.
    """
    fragments = _compact_mapping(
        {
            "data_testid": _normalize_text(data_testid),
            "overlay_title": _normalize_text(overlay_title),
            "image_alt": _normalize_text(image_alt),
            "description_title": _normalize_text(description_title),
            "description_subtitle": _normalize_text(description_subtitle),
            "price_text": _normalize_text(price_text),
            "total_price_text": _normalize_text(total_price_text),
        }
    )
    return _build_card_evidence(source=CARD_EVIDENCE_SOURCE_HTML, fragments=fragments)



def build_api_card_evidence(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the minimal API card evidence contract.

    We persist only the fragments needed to explain normalized card fields
    (title/brand/size/condition/prices). Heavy nested payloads like user,
    photos, and unrelated API metadata stay out of the hot mutable path.
    """
    brand_title = _normalize_text(_coerce_str(item.get("brand_title")))
    brand = item.get("brand")
    if brand_title is None and isinstance(brand, Mapping):
        brand_title = _normalize_text(_coerce_str(brand.get("title")))

    fragments = _compact_mapping(
        {
            "title": _normalize_text(_coerce_str(item.get("title"))),
            "brand_title": brand_title,
            "size_title": _normalize_text(_coerce_str(item.get("size_title"))),
            "status": _normalize_text(_coerce_str(item.get("status"))),
            "status_id": _coerce_int(item.get("status_id")),
            "price": _price_fragment(item.get("price")),
            "total_item_price": _price_fragment(item.get("total_item_price")),
        }
    )
    return _build_card_evidence(source=CARD_EVIDENCE_SOURCE_API, fragments=fragments)



def normalize_card_snapshot(
    *,
    raw_card_payload: Mapping[str, Any],
    source_url: str,
    canonical_url: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    """Normalize persisted card evidence back into listing-card fields.

    Accepts the current minimal evidence envelope plus legacy flat HTML/API
    payloads so historical observation rows remain explainable after the hot-path
    contract is tightened.
    """
    evidence_source, fragments = _extract_evidence_contract(raw_card_payload)
    normalized = (
        _normalize_api_snapshot(fragments=fragments)
        if evidence_source == CARD_EVIDENCE_SOURCE_API
        else _normalize_html_snapshot(fragments=fragments, source_url=source_url)
    )

    return {
        "canonical_url": canonical_url or canonicalize_url(source_url),
        "source_url": source_url,
        **normalized,
        "image_url": image_url,
    }



def canonicalize_url(url: str) -> str:
    if not url:
        return url
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", ""))



def _build_card_evidence(*, source: str, fragments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CARD_EVIDENCE_SCHEMA_VERSION,
        "evidence_source": source,
        "fragments": dict(fragments),
    }



def _extract_evidence_contract(
    raw_card_payload: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any]]:
    fragments = raw_card_payload.get("fragments")
    schema_version = raw_card_payload.get("schema_version")
    if schema_version == CARD_EVIDENCE_SCHEMA_VERSION and isinstance(fragments, Mapping):
        source = _coerce_str(raw_card_payload.get("evidence_source"))
        return _infer_evidence_source(fragments, explicit_source=source), fragments
    return _infer_evidence_source(raw_card_payload), raw_card_payload



def _infer_evidence_source(
    payload: Mapping[str, Any],
    *,
    explicit_source: str | None = None,
) -> str:
    if explicit_source in {CARD_EVIDENCE_SOURCE_HTML, CARD_EVIDENCE_SOURCE_API}:
        return explicit_source
    keys = set(payload.keys())
    if keys & _HTML_HINT_KEYS:
        return CARD_EVIDENCE_SOURCE_HTML
    if keys & _API_HINT_KEYS:
        return CARD_EVIDENCE_SOURCE_API
    return CARD_EVIDENCE_SOURCE_HTML



def _normalize_html_snapshot(
    *,
    fragments: Mapping[str, Any],
    source_url: str,
) -> dict[str, Any]:
    overlay_title = _normalize_text(_coerce_str(fragments.get("overlay_title")))
    image_alt = _normalize_text(_coerce_str(fragments.get("image_alt")))
    description_title = _normalize_text(_coerce_str(fragments.get("description_title")))
    subtitle = _normalize_text(_coerce_str(fragments.get("description_subtitle")))
    price_text = _normalize_text(_coerce_str(fragments.get("price_text")))
    total_price_text = _normalize_text(_coerce_str(fragments.get("total_price_text")))

    size_label, condition_label = _split_subtitle(subtitle)
    title = _extract_title(overlay_title, image_alt, source_url)
    brand = description_title or _extract_named_value(overlay_title or image_alt, "marque")
    if size_label is None:
        size_label = _extract_named_value(overlay_title or image_alt, "taille")
    if condition_label is None:
        condition_label = _extract_named_value(overlay_title or image_alt, "État") or _extract_named_value(overlay_title or image_alt, "état")

    price_amount_cents, price_currency = _parse_money(price_text)
    total_price_amount_cents, total_price_currency = _parse_money(total_price_text)

    return {
        "title": title,
        "brand": brand,
        "size_label": size_label,
        "condition_label": condition_label,
        "price_amount_cents": price_amount_cents,
        "price_currency": price_currency,
        "total_price_amount_cents": total_price_amount_cents,
        "total_price_currency": total_price_currency,
    }



def _normalize_api_snapshot(*, fragments: Mapping[str, Any]) -> dict[str, Any]:
    brand = _normalize_text(_coerce_str(fragments.get("brand_title")))
    if brand is None:
        nested_brand = fragments.get("brand")
        if isinstance(nested_brand, Mapping):
            brand = _normalize_text(_coerce_str(nested_brand.get("title")))

    explicit_status = _normalize_text(_coerce_str(fragments.get("status")))
    status_id = _coerce_int(fragments.get("status_id"))
    condition_label = explicit_status or (
        STATUS_ID_TO_CONDITION.get(status_id) if status_id is not None else None
    )

    price_amount_cents, price_currency = _parse_api_price(fragments.get("price"))
    total_price_amount_cents, total_price_currency = _parse_api_price(
        fragments.get("total_item_price")
    )

    return {
        "title": _normalize_text(_coerce_str(fragments.get("title"))),
        "brand": brand,
        "size_label": _normalize_text(_coerce_str(fragments.get("size_title"))),
        "condition_label": condition_label,
        "price_amount_cents": price_amount_cents,
        "price_currency": price_currency,
        "total_price_amount_cents": total_price_amount_cents,
        "total_price_currency": total_price_currency,
    }



def _price_fragment(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    amount = value.get("amount")
    currency_code = _normalize_text(_coerce_str(value.get("currency_code")))
    if isinstance(amount, str):
        amount = amount.strip() or None
    if amount is None and currency_code is None:
        return None
    return _compact_mapping(
        {
            "amount": amount,
            "currency_code": currency_code,
        }
    )



def _parse_api_price(value: Any) -> tuple[int | None, str | None]:
    if not isinstance(value, Mapping):
        return None, None

    raw_amount = value.get("amount")
    if raw_amount is None:
        return None, None

    currency_code = _normalize_text(_coerce_str(value.get("currency_code")))
    currency = {
        "EUR": "€",
        "GBP": "£",
        "USD": "$",
        "PLN": "PLN",
        "CZK": "CZK",
        "SEK": "SEK",
    }.get(currency_code or "", currency_code)

    try:
        amount_str = str(raw_amount).strip().replace(",", ".").replace(" ", "")
        if not amount_str:
            return None, None
        amount_float = float(amount_str)
    except (TypeError, ValueError):
        return None, None

    return round(amount_float * 100), currency



def _compact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, item in value.items():
        if item is None:
            continue
        if isinstance(item, Mapping):
            nested = _compact_mapping(item)
            if nested:
                compact[key] = nested
            continue
        compact[key] = item
    return compact



def _coerce_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None



def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\xa0", " ").replace("\u202f", " ").split())
    return cleaned or None



def _split_subtitle(subtitle: str | None) -> tuple[str | None, str | None]:
    if not subtitle:
        return None, None
    parts = [part.strip() for part in _SUBTITLE_SPLIT_RE.split(subtitle) if part.strip()]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]



def _extract_title(overlay_title: str | None, image_alt: str | None, source_url: str) -> str | None:
    for candidate in (overlay_title, image_alt):
        if candidate:
            return candidate.split(",", 1)[0].strip() or None
    if source_url:
        path = urlsplit(source_url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1]
        if "-" in slug:
            return slug.split("-", 1)[1].replace("-", " ") or None
    return None



def _extract_named_value(text: str | None, label: str) -> str | None:
    if not text:
        return None
    pattern = re.compile(rf"{re.escape(label)}\s*:\s*([^,]+)", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    return _normalize_text(match.group(1))



def _parse_money(text: str | None) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    match = _MONEY_RE.search(text)
    if not match:
        return None, None
    amount = match.group("amount").replace(" ", "").replace(".", "").replace(",", ".")
    cents = round(float(amount) * 100)
    return cents, match.group("currency")
