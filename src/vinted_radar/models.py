from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from .config import DEFAULT_EXTRACTOR_VERSION

RunStatus = Literal["planned", "running", "completed", "failed"]
CoverageStage = Literal["catalog_scan", "item_detail", "verification"]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True, frozen=True)
class CatalogNode:
    catalog_id: int
    root_catalog_id: int
    parent_catalog_id: int | None = None
    slug: str | None = None
    title: str | None = None
    path: str | None = None
    source_url: str | None = None
    is_leaf: bool | None = None
    observed_at: datetime = field(default_factory=utc_now)
    extractor_version: str = DEFAULT_EXTRACTOR_VERSION


@dataclass(slots=True, frozen=True)
class DiscoveryRun:
    run_id: str
    requested_roots: tuple[int, ...]
    status: RunStatus = "running"
    max_pages_per_catalog: int | None = None
    item_details_mode: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_message: str | None = None
    observed_at: datetime = field(default_factory=utc_now)
    extractor_version: str = DEFAULT_EXTRACTOR_VERSION


@dataclass(slots=True, frozen=True)
class ListingIdentity:
    listing_id: str
    source_url: str | None = None
    seller_id: str | None = None
    seller_login: str | None = None
    first_observed_at: datetime = field(default_factory=utc_now)
    last_observed_at: datetime = field(default_factory=utc_now)
    first_extractor_version: str = DEFAULT_EXTRACTOR_VERSION
    last_extractor_version: str = DEFAULT_EXTRACTOR_VERSION


@dataclass(slots=True, frozen=True)
class ListingObservation:
    run_id: str
    listing_id: str
    observation_id: int | None = None
    catalog_id: int | None = None
    catalog_page: int | None = None
    observed_rank: int | None = None
    title: str | None = None
    brand: str | None = None
    size_label: str | None = None
    price_amount: float | None = None
    currency_code: str | None = None
    status_hint: str | None = None
    seller_login: str | None = None
    seller_country_code: str | None = None
    favourite_count: int | None = None
    view_count: int | None = None
    image_url: str | None = None
    source_url: str | None = None
    observed_at: datetime = field(default_factory=utc_now)
    extractor_version: str = DEFAULT_EXTRACTOR_VERSION


@dataclass(slots=True, frozen=True)
class RawEvidenceFragment:
    run_id: str
    fragment_kind: str
    body: str
    fragment_id: int | None = None
    listing_id: str | None = None
    catalog_id: int | None = None
    fragment_key: str | None = None
    source_url: str | None = None
    content_type: str = "application/json"
    observed_at: datetime = field(default_factory=utc_now)
    extractor_version: str = DEFAULT_EXTRACTOR_VERSION


@dataclass(slots=True, frozen=True)
class CoverageCounters:
    pages_scanned: int = 0
    listing_stubs_seen: int = 0
    unique_listings: int = 0
    duplicate_listings: int = 0
    errors: int = 0


@dataclass(slots=True, frozen=True)
class ScanCoverage:
    run_id: str
    coverage_id: int | None = None
    catalog_id: int | None = None
    root_catalog_id: int | None = None
    page_number: int | None = None
    stage: CoverageStage = "catalog_scan"
    counters: CoverageCounters = field(default_factory=CoverageCounters)
    stop_reason: str | None = None
    error_message: str | None = None
    observed_at: datetime = field(default_factory=utc_now)
    extractor_version: str = DEFAULT_EXTRACTOR_VERSION


__all__ = [
    "CatalogNode",
    "CoverageCounters",
    "CoverageStage",
    "DiscoveryRun",
    "ListingIdentity",
    "ListingObservation",
    "RawEvidenceFragment",
    "RunStatus",
    "ScanCoverage",
    "utc_now",
]
