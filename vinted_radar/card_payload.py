from __future__ import annotations

from typing import Any, Mapping
import re
from urllib.parse import urlsplit, urlunsplit

_MONEY_RE = re.compile(r"(?P<amount>\d[\d\s.,]*)\s*(?P<currency>€|EUR|£|\$)")
_SUBTITLE_SPLIT_RE = re.compile(r"\s*[·•|]\s*")


def normalize_card_snapshot(
    *,
    raw_card_payload: Mapping[str, Any],
    source_url: str,
    canonical_url: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    overlay_title = _normalize_text(_coerce_str(raw_card_payload.get("overlay_title")))
    image_alt = _normalize_text(_coerce_str(raw_card_payload.get("image_alt")))
    description_title = _normalize_text(_coerce_str(raw_card_payload.get("description_title")))
    subtitle = _normalize_text(_coerce_str(raw_card_payload.get("description_subtitle")))
    price_text = _normalize_text(_coerce_str(raw_card_payload.get("price_text")))
    total_price_text = _normalize_text(_coerce_str(raw_card_payload.get("total_price_text")))

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
        "canonical_url": canonical_url or canonicalize_url(source_url),
        "source_url": source_url,
        "title": title,
        "brand": brand,
        "size_label": size_label,
        "condition_label": condition_label,
        "price_amount_cents": price_amount_cents,
        "price_currency": price_currency,
        "total_price_amount_cents": total_price_amount_cents,
        "total_price_currency": total_price_currency,
        "image_url": image_url,
    }


def canonicalize_url(url: str) -> str:
    if not url:
        return url
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", ""))


def _coerce_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


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
