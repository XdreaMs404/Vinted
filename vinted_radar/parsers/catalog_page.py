from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from vinted_radar.card_payload import build_html_card_evidence
from vinted_radar.models import CatalogPage, ListingCard

BASE_URL = "https://www.vinted.fr"
_LISTING_ID_RE = re.compile(r"product-item-id-(?P<id>\d+)$")
_MONEY_RE = re.compile(r"(?P<amount>\d[\d\s.,]*)\s*(?P<currency>€|EUR|£|\$)")
_SUBTITLE_SPLIT_RE = re.compile(r"\s*[·•|]\s*")


class CatalogPageParseError(RuntimeError):
    pass


def parse_catalog_page(
    html: str,
    *,
    source_catalog_id: int | None = None,
    source_root_catalog_id: int | None = None,
) -> CatalogPage:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[ListingCard] = []

    for container in soup.select('div.new-item-box__container[data-testid^="product-item-id-"]'):
        card = _parse_listing_card(
            container,
            source_catalog_id=source_catalog_id,
            source_root_catalog_id=source_root_catalog_id,
        )
        if card is not None:
            cards.append(card)

    current_page, total_pages, next_page_url = _parse_pagination(soup)
    return CatalogPage(listings=cards, current_page=current_page, total_pages=total_pages, next_page_url=next_page_url)


def _parse_listing_card(
    container: Tag,
    *,
    source_catalog_id: int | None,
    source_root_catalog_id: int | None,
) -> ListingCard | None:
    data_testid = container.get("data-testid") or ""
    match = _LISTING_ID_RE.match(data_testid)
    if not match:
        return None

    listing_id = int(match.group("id"))
    overlay_link = container.select_one("a.new-item-box__overlay")
    image = container.select_one("img")

    source_url = urljoin(BASE_URL, overlay_link.get("href", "")) if overlay_link else ""
    canonical_url = _canonicalize_url(source_url)
    overlay_title = _normalize_text(overlay_link.get("title") if overlay_link else None)
    image_alt = _normalize_text(image.get("alt") if image else None)
    description_title = _extract_text(container.select_one('[data-testid$="--description-title"]'))
    subtitle = _extract_text(container.select_one('[data-testid$="--description-subtitle"]'))
    price_text = _extract_text(container.select_one('[data-testid$="--price-text"]'))
    total_price_text = _extract_text(container.select_one('[data-testid="total-combined-price"]'))

    size_label, condition_label = _split_subtitle(subtitle)
    title = _extract_title(overlay_title, image_alt, source_url)
    brand = description_title or _extract_named_value(overlay_title or image_alt, "marque")
    if size_label is None:
        size_label = _extract_named_value(overlay_title or image_alt, "taille")
    if condition_label is None:
        condition_label = _extract_named_value(overlay_title or image_alt, "État") or _extract_named_value(overlay_title or image_alt, "état")

    price_amount_cents, price_currency = _parse_money(price_text)
    total_price_amount_cents, total_price_currency = _parse_money(total_price_text)

    return ListingCard(
        listing_id=listing_id,
        source_url=source_url,
        canonical_url=canonical_url,
        title=title,
        brand=brand,
        size_label=size_label,
        condition_label=condition_label,
        price_amount_cents=price_amount_cents,
        price_currency=price_currency,
        total_price_amount_cents=total_price_amount_cents,
        total_price_currency=total_price_currency,
        image_url=image.get("src") if image else None,
        source_catalog_id=source_catalog_id,
        source_root_catalog_id=source_root_catalog_id,
        raw_card=build_html_card_evidence(
            data_testid=data_testid,
            overlay_title=overlay_title,
            image_alt=image_alt,
            description_title=description_title,
            description_subtitle=subtitle,
            price_text=price_text,
            total_price_text=total_price_text,
        ),
    )


def _parse_pagination(soup: BeautifulSoup) -> tuple[int | None, int | None, str | None]:
    nav = soup.select_one('nav[data-testid="catalog-pagination"]')
    if nav is None:
        return None, None, None

    current_page = None
    total_pages = None

    page_links = nav.select('a[data-testid^="catalog-pagination--page-"]')
    numeric_pages: list[int] = []
    for link in page_links:
        page_label = _normalize_text(link.get_text())
        if page_label.isdigit():
            numeric_pages.append(int(page_label))
        if link.get("aria-current") == "true" and page_label.isdigit():
            current_page = int(page_label)

    if numeric_pages:
        total_pages = max(numeric_pages)

    next_link = nav.select_one('a[data-testid="catalog-pagination--next-page"]')
    if next_link is not None and next_link.get("aria-disabled") == "false":
        next_page_url = next_link.get("href")
    else:
        next_page_url = None

    return current_page, total_pages, next_page_url


def _extract_text(node: Tag | None) -> str | None:
    if node is None:
        return None
    return _normalize_text(node.get_text())


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


def _canonicalize_url(url: str) -> str:
    if not url:
        return url
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", ""))
