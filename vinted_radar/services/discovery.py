from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import zip_longest
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from vinted_radar.http import VintedHttpClient
from vinted_radar.models import CatalogNode
from vinted_radar.parsers.catalog_page import parse_catalog_page
from vinted_radar.parsers.catalog_tree import parse_catalog_tree_from_html
from vinted_radar.repository import RadarRepository

ROOT_SCOPE_MAP = {
    "both": ("Femmes", "Hommes"),
    "women": ("Femmes",),
    "men": ("Hommes",),
}


@dataclass(frozen=True, slots=True)
class DiscoveryOptions:
    page_limit: int = 1
    max_leaf_categories: int | None = None
    root_scope: str = "both"
    request_delay: float = 0.5


@dataclass(frozen=True, slots=True)
class DiscoveryRunReport:
    run_id: str
    total_seed_catalogs: int
    total_leaf_catalogs: int
    scanned_leaf_catalogs: int
    successful_scans: int
    failed_scans: int
    raw_listing_hits: int
    unique_listing_hits: int


class DiscoveryService:
    def __init__(
        self,
        repository: RadarRepository,
        http_client: VintedHttpClient,
        *,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.http_client = http_client
        self.now_provider = now_provider or _utc_now

    def run(self, options: DiscoveryOptions) -> DiscoveryRunReport:
        if options.root_scope not in ROOT_SCOPE_MAP:
            raise ValueError(f"Unsupported root scope: {options.root_scope}")
        if options.page_limit < 1:
            raise ValueError("page_limit must be at least 1")

        run_id = self.repository.start_run(
            root_scope=options.root_scope,
            page_limit=options.page_limit,
            max_leaf_categories=options.max_leaf_categories,
            request_delay_seconds=options.request_delay,
        )

        scanned_leaf_catalogs = 0
        successful_scans = 0
        failed_scans = 0
        raw_listing_hits = 0
        unique_listing_ids: set[int] = set()

        try:
            root_page = self.http_client.get_text("https://www.vinted.fr/catalog")
            if root_page.status_code >= 400:
                raise RuntimeError(f"Catalog root request failed with HTTP {root_page.status_code}")

            catalogs = parse_catalog_tree_from_html(root_page.text, allowed_root_titles=set(ROOT_SCOPE_MAP[options.root_scope]))
            synced_at = self.now_provider()
            self.repository.upsert_catalogs(catalogs, synced_at=synced_at)

            leaf_catalogs = _select_leaf_catalogs(
                catalogs=catalogs,
                root_titles=ROOT_SCOPE_MAP[options.root_scope],
                limit=options.max_leaf_categories,
            )
            self.repository.update_run_catalog_totals(
                run_id,
                total_seed_catalogs=len(catalogs),
                total_leaf_catalogs=len([catalog for catalog in catalogs if catalog.is_leaf]),
            )

            for catalog in leaf_catalogs:
                scanned_leaf_catalogs += 1
                next_page_url = catalog.url
                for page_number in range(1, options.page_limit + 1):
                    if not next_page_url:
                        break
                    observed_at = self.now_provider()
                    try:
                        page = self.http_client.get_text(next_page_url)
                        if page.status_code >= 400:
                            failed_scans += 1
                            self.repository.record_catalog_scan(
                                run_id=run_id,
                                catalog_id=catalog.catalog_id,
                                page_number=page_number,
                                requested_url=next_page_url,
                                fetched_at=observed_at,
                                response_status=page.status_code,
                                success=False,
                                listing_count=0,
                                pagination_total_pages=None,
                                next_page_url=None,
                                error_message=f"HTTP {page.status_code}",
                            )
                            break

                        parsed_page = parse_catalog_page(
                            page.text,
                            source_catalog_id=catalog.catalog_id,
                            source_root_catalog_id=catalog.root_catalog_id,
                        )
                        successful_scans += 1
                        raw_listing_hits += len(parsed_page.listings)

                        for card_position, listing in enumerate(parsed_page.listings, start=1):
                            unique_listing_ids.add(listing.listing_id)
                            self.repository.upsert_listing(
                                listing,
                                discovered_at=observed_at,
                                primary_catalog_id=catalog.catalog_id,
                                primary_root_catalog_id=catalog.root_catalog_id,
                                run_id=run_id,
                            )
                            self.repository.record_listing_discovery(
                                run_id=run_id,
                                listing=listing,
                                observed_at=observed_at,
                                source_catalog_id=catalog.catalog_id,
                                source_page_number=page_number,
                                card_position=card_position,
                            )
                            self.repository.record_listing_observation(
                                run_id=run_id,
                                listing=listing,
                                observed_at=observed_at,
                                source_catalog_id=catalog.catalog_id,
                                source_page_number=page_number,
                                card_position=card_position,
                            )

                        self.repository.record_catalog_scan(
                            run_id=run_id,
                            catalog_id=catalog.catalog_id,
                            page_number=page_number,
                            requested_url=next_page_url,
                            fetched_at=observed_at,
                            response_status=page.status_code,
                            success=True,
                            listing_count=len(parsed_page.listings),
                            pagination_total_pages=parsed_page.total_pages,
                            next_page_url=parsed_page.next_page_url,
                            error_message=None,
                        )
                        next_page_url = _absolute_page_url(catalog.url, parsed_page.next_page_url)
                    except Exception as exc:  # noqa: BLE001
                        failed_scans += 1
                        self.repository.record_catalog_scan(
                            run_id=run_id,
                            catalog_id=catalog.catalog_id,
                            page_number=page_number,
                            requested_url=next_page_url,
                            fetched_at=observed_at,
                            response_status=None,
                            success=False,
                            listing_count=0,
                            pagination_total_pages=None,
                            next_page_url=None,
                            error_message=f"{type(exc).__name__}: {exc}",
                        )
                        break

            self.repository.complete_run(
                run_id,
                status="completed",
                scanned_leaf_catalogs=scanned_leaf_catalogs,
                successful_scans=successful_scans,
                failed_scans=failed_scans,
                raw_listing_hits=raw_listing_hits,
                unique_listing_hits=len(unique_listing_ids),
            )
        except Exception as exc:  # noqa: BLE001
            self.repository.complete_run(
                run_id,
                status="failed",
                scanned_leaf_catalogs=scanned_leaf_catalogs,
                successful_scans=successful_scans,
                failed_scans=failed_scans,
                raw_listing_hits=raw_listing_hits,
                unique_listing_hits=len(unique_listing_ids),
                last_error=str(exc),
            )
            raise

        return DiscoveryRunReport(
            run_id=run_id,
            total_seed_catalogs=len(catalogs),
            total_leaf_catalogs=len([catalog for catalog in catalogs if catalog.is_leaf]),
            scanned_leaf_catalogs=scanned_leaf_catalogs,
            successful_scans=successful_scans,
            failed_scans=failed_scans,
            raw_listing_hits=raw_listing_hits,
            unique_listing_hits=len(unique_listing_ids),
        )


def build_default_service(*, db_path: str, timeout_seconds: float, request_delay: float) -> DiscoveryService:
    repository = RadarRepository(db_path)
    http_client = VintedHttpClient(timeout_seconds=timeout_seconds, request_delay=request_delay)
    return DiscoveryService(repository=repository, http_client=http_client)


def _select_leaf_catalogs(
    *,
    catalogs: list[CatalogNode],
    root_titles: tuple[str, ...],
    limit: int | None,
) -> list[CatalogNode]:
    grouped: dict[str, list[CatalogNode]] = defaultdict(list)
    for catalog in catalogs:
        if catalog.is_leaf and catalog.root_title in root_titles:
            grouped[catalog.root_title].append(catalog)

    for items in grouped.values():
        items.sort(key=lambda catalog: catalog.path_text)

    ordered: list[CatalogNode] = []
    if limit is None:
        for root_title in root_titles:
            ordered.extend(grouped.get(root_title, []))
        return ordered

    for grouped_row in zip_longest(*(grouped.get(root_title, []) for root_title in root_titles)):
        for catalog in grouped_row:
            if catalog is None:
                continue
            ordered.append(catalog)
            if len(ordered) >= limit:
                return ordered
    return ordered


def _absolute_page_url(base_catalog_url: str, next_page_url: str | None) -> str | None:
    if next_page_url is None:
        return None
    if next_page_url.startswith("http://") or next_page_url.startswith("https://"):
        return next_page_url
    base_parts = urlparse(base_catalog_url)
    next_parts = urlparse(next_page_url)
    query = dict(parse_qsl(next_parts.query, keep_blank_values=True))
    return urlunparse((base_parts.scheme, base_parts.netloc, next_parts.path or base_parts.path, "", urlencode(query), ""))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
