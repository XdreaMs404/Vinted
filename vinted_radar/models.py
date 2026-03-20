from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CatalogNode:
    catalog_id: int
    root_catalog_id: int
    root_title: str
    parent_catalog_id: int | None
    title: str
    code: str | None
    url: str
    path: tuple[str, ...]
    depth: int
    is_leaf: bool
    allow_browsing_subcategories: bool
    order_index: int | None = None

    @property
    def path_text(self) -> str:
        return " > ".join(self.path)


@dataclass(frozen=True, slots=True)
class ListingCard:
    listing_id: int
    source_url: str
    canonical_url: str
    title: str | None
    brand: str | None
    size_label: str | None
    condition_label: str | None
    price_amount_cents: int | None
    price_currency: str | None
    total_price_amount_cents: int | None
    total_price_currency: str | None
    image_url: str | None
    favourite_count: int | None = None
    view_count: int | None = None
    user_id: int | None = None
    user_login: str | None = None
    user_profile_url: str | None = None
    created_at_ts: int | None = None
    source_catalog_id: int | None = None
    source_root_catalog_id: int | None = None
    raw_card: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogPage:
    listings: list[ListingCard]
    current_page: int | None
    total_pages: int | None
    next_page_url: str | None
