from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import zip_longest
from urllib.parse import urlencode

from vinted_radar.http import VintedHttpClient
from vinted_radar.models import CatalogNode
from vinted_radar.parsers.api_catalog_page import parse_api_catalog_page
from vinted_radar.parsers.catalog_tree import parse_catalog_tree_from_html
from vinted_radar.repository import RadarRepository

logger = logging.getLogger(__name__)

ROOT_SCOPE_MAP = {
    "both": ("Femmes", "Hommes"),
    "women": ("Femmes",),
    "men": ("Hommes",),
}

_API_CATALOG_BASE = "https://www.vinted.fr/api/v2/catalog/items"
_PER_PAGE = 96
_DEFAULT_CONCURRENCY = 15


@dataclass(frozen=True, slots=True)
class DiscoveryOptions:
    page_limit: int = 5
    max_leaf_categories: int | None = None
    root_scope: str = "both"
    request_delay: float = 3.0
    concurrency: int = 1


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


@dataclass
class _CatalogScanResult:
    """Mutable accumulator returned by each catalog scan coroutine."""
    successful_scans: int = 0
    failed_scans: int = 0
    raw_listing_hits: int = 0
    unique_listing_ids: set[int] = field(default_factory=set)


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

    # ------------------------------------------------------------------
    # Public: sync wrapper  (keeps CLI / runtime / tests backward-compat)
    # ------------------------------------------------------------------
    def run(self, options: DiscoveryOptions) -> DiscoveryRunReport:
        """Synchronous entry-point — delegates to the async core."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Already inside an event-loop (e.g. Jupyter, nested call).
            # Fall back to a dedicated thread to avoid "cannot nest".
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.run_async(options)).result()

        return asyncio.run(self.run_async(options))

    # ------------------------------------------------------------------
    # Public: async core
    # ------------------------------------------------------------------
    async def run_async(self, options: DiscoveryOptions) -> DiscoveryRunReport:
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
            # 1. Fetch the catalog tree (single request, still via async).
            root_page = await self.http_client.get_text_async(
                "https://www.vinted.fr/catalog"
            )
            if root_page.status_code >= 400:
                raise RuntimeError(
                    f"Catalog root request failed with HTTP {root_page.status_code}"
                )

            catalogs = parse_catalog_tree_from_html(
                root_page.text,
                allowed_root_titles=set(ROOT_SCOPE_MAP[options.root_scope]),
            )
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
                total_leaf_catalogs=len(
                    [c for c in catalogs if c.is_leaf]
                ),
            )

            # 2. Scan all leaf catalogs concurrently, bounded by semaphore.
            semaphore = asyncio.Semaphore(options.concurrency)

            async def _scan_one(catalog: CatalogNode) -> _CatalogScanResult:
                return await self._scan_catalog(
                    run_id=run_id,
                    catalog=catalog,
                    options=options,
                    semaphore=semaphore,
                )

            results = await asyncio.gather(
                *(_scan_one(cat) for cat in leaf_catalogs),
                return_exceptions=True,
            )

            # 3. Aggregate results.
            scanned_leaf_catalogs = len(leaf_catalogs)
            for result in results:
                if isinstance(result, BaseException):
                    # Catalog-level unexpected crash (shouldn't happen,
                    # individual page errors are caught inside _scan_catalog).
                    failed_scans += 1
                    logger.error("Catalog scan coroutine crashed: %s", result)
                    continue
                successful_scans += result.successful_scans
                failed_scans += result.failed_scans
                raw_listing_hits += result.raw_listing_hits
                unique_listing_ids.update(result.unique_listing_ids)

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
        finally:
            close = getattr(self.http_client, "close_async", None)
            if close is not None:
                await close()

        return DiscoveryRunReport(
            run_id=run_id,
            total_seed_catalogs=len(catalogs),
            total_leaf_catalogs=len([c for c in catalogs if c.is_leaf]),
            scanned_leaf_catalogs=scanned_leaf_catalogs,
            successful_scans=successful_scans,
            failed_scans=failed_scans,
            raw_listing_hits=raw_listing_hits,
            unique_listing_hits=len(unique_listing_ids),
        )

    # ------------------------------------------------------------------
    # Per-catalog scan coroutine
    # ------------------------------------------------------------------
    async def _scan_catalog(
        self,
        *,
        run_id: str,
        catalog: CatalogNode,
        options: DiscoveryOptions,
        semaphore: asyncio.Semaphore,
    ) -> _CatalogScanResult:
        """Scan one leaf catalog, paginating sequentially within it.

        The semaphore is acquired around each HTTP call so that at most
        ``concurrency`` requests are in-flight across *all* catalogs.
        """
        result = _CatalogScanResult()

        for page_number in range(1, options.page_limit + 1):
            api_url = _build_api_catalog_url(catalog.catalog_id, page_number)
            logger.info(
                "Catalog %d (%s) – fetching API page %d/%d",
                catalog.catalog_id,
                catalog.title,
                page_number,
                options.page_limit,
            )
            observed_at = self.now_provider()
            try:
                async with semaphore:
                    page = await self.http_client.get_text_async(api_url)

                if page.status_code >= 400:
                    logger.warning(
                        "Catalog %d page %d – HTTP %d, stopping this catalog",
                        catalog.catalog_id,
                        page_number,
                        page.status_code,
                    )
                    result.failed_scans += 1
                    self.repository.record_catalog_scan(
                        run_id=run_id,
                        catalog_id=catalog.catalog_id,
                        page_number=page_number,
                        requested_url=api_url,
                        fetched_at=observed_at,
                        response_status=page.status_code,
                        success=False,
                        listing_count=0,
                        pagination_total_pages=None,
                        next_page_url=None,
                        error_message=f"HTTP {page.status_code}",
                    )
                    break

                try:
                    payload = json.loads(page.text)
                except json.JSONDecodeError as json_exc:
                    snippet = page.text[:200] if page.text else "<empty>"
                    logger.error(
                        "Catalog %d page %d – response is not valid JSON "
                        "(status %d). First 200 chars: %s",
                        catalog.catalog_id,
                        page_number,
                        page.status_code,
                        snippet,
                    )
                    raise RuntimeError(
                        f"Invalid JSON from API for catalog {catalog.catalog_id} "
                        f"page {page_number} (HTTP {page.status_code})"
                    ) from json_exc

                parsed_page = parse_api_catalog_page(
                    payload,
                    source_catalog_id=catalog.catalog_id,
                    source_root_catalog_id=catalog.root_catalog_id,
                )
                result.successful_scans += 1
                result.raw_listing_hits += len(parsed_page.listings)
                logger.info(
                    "Catalog %d page %d – %d listings found (page %s/%s)",
                    catalog.catalog_id,
                    page_number,
                    len(parsed_page.listings),
                    parsed_page.current_page,
                    parsed_page.total_pages,
                )

                for card_position, listing in enumerate(
                    parsed_page.listings, start=1
                ):
                    result.unique_listing_ids.add(listing.listing_id)
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
                    requested_url=api_url,
                    fetched_at=observed_at,
                    response_status=page.status_code,
                    success=True,
                    listing_count=len(parsed_page.listings),
                    pagination_total_pages=parsed_page.total_pages,
                    next_page_url=parsed_page.next_page_url,
                    error_message=None,
                )

                # Stop early when the API returns an empty page.
                if not parsed_page.listings:
                    logger.info(
                        "Catalog %d page %d – empty page, stopping pagination",
                        catalog.catalog_id,
                        page_number,
                    )
                    break

                # Stop paginating when the API reports no further pages.
                if (
                    parsed_page.current_page is not None
                    and parsed_page.total_pages is not None
                    and parsed_page.current_page >= parsed_page.total_pages
                ):
                    break

            except Exception as exc:  # noqa: BLE001
                result.failed_scans += 1
                self.repository.record_catalog_scan(
                    run_id=run_id,
                    catalog_id=catalog.catalog_id,
                    page_number=page_number,
                    requested_url=api_url,
                    fetched_at=observed_at,
                    response_status=None,
                    success=False,
                    listing_count=0,
                    pagination_total_pages=None,
                    next_page_url=None,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                break

        return result


def build_default_service(
    *,
    db_path: str,
    timeout_seconds: float,
    request_delay: float,
    proxies: list[str] | None = None,
    max_retries: int = 3,
) -> DiscoveryService:
    repository = RadarRepository(db_path)
    http_client = VintedHttpClient(
        timeout_seconds=timeout_seconds,
        request_delay=request_delay,
        proxies=proxies,
        max_retries=max_retries,
    )
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


def _build_api_catalog_url(catalog_id: int, page: int) -> str:
    """Build the full API URL for a catalog page request."""
    params = {
        "catalog_ids": str(catalog_id),
        "page": str(page),
        "per_page": str(_PER_PAGE),
    }
    return f"{_API_CATALOG_BASE}?{urlencode(params)}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
