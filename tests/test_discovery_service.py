from __future__ import annotations

import json
from pathlib import Path

import pytest

from vinted_radar.http import FetchedPage
from vinted_radar.platform.lake_writer import CollectorEvidencePublisher, ParquetLakeWriter
from vinted_radar.platform.object_store import S3ObjectStore
from vinted_radar.platform.outbox import PostgresOutbox
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryService, _build_api_catalog_url

from tests.platform_test_fakes import FakePostgresConnection, FakeS3Client

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_item(item_id: int, *, title: str, brand: str, size: str, status_id: int, price: str, total_price: str, image_url: str) -> dict:
    """Build a minimal Vinted API item dict matching what the real API returns."""
    return {
        "id": item_id,
        "title": title,
        "url": f"/items/{item_id}-{title.lower().replace(' ', '-')}",
        "brand_title": brand,
        "size_title": size,
        "status_id": status_id,
        "price": {"amount": price, "currency_code": "EUR"},
        "total_item_price": {"amount": total_price, "currency_code": "EUR"},
        "photo": {"url": image_url},
    }


def _make_api_page(items: list[dict], *, current_page: int, total_pages: int, per_page: int = 96) -> str:
    """Serialize a fake API catalog JSON response."""
    return json.dumps({
        "items": items,
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "per_page": per_page,
            "total_entries": len(items),
        },
    })


# Mirror the fixture data from the HTML fixtures, using the API format.
WOMEN_ITEMS = [
    _make_api_item(9001, title="Robe noire", brand="Zara", size="M", status_id=3, price="12.50", total_price="14.13", image_url="https://images1.vinted.net/t/women-9001.webp"),
    _make_api_item(9002, title="Chemise vintage", brand="Sézane", size="S", status_id=4, price="22.00", total_price="24.20", image_url="https://images1.vinted.net/t/women-9002.webp"),
]

MEN_ITEMS = [
    _make_api_item(9101, title="Pantalon cargo", brand="Carhartt", size="L", status_id=1, price="35.00", total_price="38.15", image_url="https://images1.vinted.net/t/men-9101.webp"),
]


class FakeHttpClient:
    def __init__(self, pages: dict[str, FetchedPage]) -> None:
        self.pages = pages

    def get_text(self, url: str) -> FetchedPage:
        try:
            return self.pages[url]
        except KeyError as exc:  # pragma: no cover - test setup failure
            raise AssertionError(f"Unexpected URL requested: {url}") from exc

    async def get_text_async(self, url: str) -> FetchedPage:
        return self.get_text(url)


def _build_evidence_publisher() -> tuple[CollectorEvidencePublisher, FakePostgresConnection]:
    s3_client = FakeS3Client()
    object_store = S3ObjectStore(s3_client, bucket="vinted-radar-test")
    object_store.ensure_bucket()
    postgres_connection = FakePostgresConnection()
    publisher = CollectorEvidencePublisher(
        lake_writer=ParquetLakeWriter(
            object_store,
            raw_events_prefix="tenant-a/events/raw",
            manifests_prefix="tenant-a/manifests",
            parquet_prefix="tenant-a/parquet",
        ),
        outbox=PostgresOutbox(postgres_connection),
        sinks=("parquet",),
    )
    return publisher, postgres_connection



def test_discovery_service_defaults_to_bounded_api_price_filter(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    bounded_items = [
        _make_api_item(9301, title="Robe premium", brand="Mango", size="M", status_id=3, price="35.00", total_price="38.00", image_url="https://images1.vinted.net/t/women-9301.webp"),
    ]
    women_api_url = _build_api_catalog_url(2001, 1, price_from=30.0)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(bounded_items, current_page=1, total_pages=1)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(
            DiscoveryOptions(
                page_limit=1,
                max_leaf_categories=1,
                root_scope="women",
                request_delay=0.0,
            )
        )
        scan = repository.connection.execute(
            "SELECT requested_url FROM catalog_scans WHERE run_id = ? AND catalog_id = ? AND page_number = 1",
            (report.run_id, 2001),
        ).fetchone()

        assert report.successful_scans == 1
        assert scan is not None
        assert scan["requested_url"] == women_api_url
        assert "price_from=30.0" in scan["requested_url"]


def test_discovery_service_min_price_zero_disables_api_price_bound(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    unbounded_items = [
        _make_api_item(9302, title="Robe libre", brand="Mango", size="S", status_id=3, price="12.00", total_price="15.00", image_url="https://images1.vinted.net/t/women-9302.webp"),
    ]
    women_api_url = _build_api_catalog_url(2001, 1)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(unbounded_items, current_page=1, total_pages=1)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(
            DiscoveryOptions(
                page_limit=1,
                max_leaf_categories=1,
                root_scope="women",
                request_delay=0.0,
                min_price=0.0,
                max_price=0.0,
            )
        )
        scan = repository.connection.execute(
            "SELECT requested_url FROM catalog_scans WHERE run_id = ? AND catalog_id = ? AND page_number = 1",
            (report.run_id, 2001),
        ).fetchone()

        assert report.successful_scans == 1
        assert scan is not None
        assert scan["requested_url"] == women_api_url
        assert "price_from" not in scan["requested_url"]
        assert "price_to" not in scan["requested_url"]


def test_discovery_service_persists_catalogs_listings_and_coverage(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url = _build_api_catalog_url(2001, 1)
    men_api_url = _build_api_catalog_url(3001, 1)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(WOMEN_ITEMS, current_page=1, total_pages=2)),
        men_api_url: FetchedPage(men_api_url, 200, _make_api_page(MEN_ITEMS, current_page=1, total_pages=1)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0, min_price=0.0))
        summary = repository.coverage_summary(report.run_id)

        assert report.total_seed_catalogs == 6
        assert report.total_leaf_catalogs == 2
        assert report.scanned_leaf_catalogs == 2
        assert report.successful_scans == 2
        assert report.failed_scans == 0
        assert report.raw_listing_hits == 3
        assert report.unique_listing_hits == 3
        assert repository.count_rows("catalogs") == 6
        assert repository.count_rows("listings") == 3
        assert repository.count_rows("listing_discoveries") == 3
        assert summary is not None
        assert summary["run"]["status"] == "completed"
        assert {row["root_title"] for row in summary["by_root"]} == {"Femmes", "Hommes"}


def test_discovery_service_records_scan_failures_without_losing_successful_work(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url = _build_api_catalog_url(2001, 1)
    men_api_url = _build_api_catalog_url(3001, 1)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(WOMEN_ITEMS, current_page=1, total_pages=1)),
        men_api_url: FetchedPage(men_api_url, 503, "service unavailable"),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0, min_price=0.0))
        summary = repository.coverage_summary(report.run_id)

        assert report.successful_scans == 1
        assert report.failed_scans == 1
        assert report.unique_listing_hits == 2
        assert summary is not None
        assert len(summary["failures"]) == 1
        assert summary["failures"][0]["error_message"] == "HTTP 503"
        assert repository.count_rows("listings") == 2


def test_discovery_service_pagination_stops_at_last_page(tmp_path: Path) -> None:
    """Verify the scan loop stops when current_page >= total_pages even if page_limit allows more."""
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url_p1 = _build_api_catalog_url(2001, 1)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url_p1: FetchedPage(women_api_url_p1, 200, _make_api_page(WOMEN_ITEMS, current_page=1, total_pages=1)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=5, max_leaf_categories=1, root_scope="women", request_delay=0.0, min_price=0.0))

        assert report.successful_scans == 1
        assert report.raw_listing_hits == 2
        assert report.unique_listing_hits == 2


def test_discovery_service_multi_page_pagination(tmp_path: Path) -> None:
    """Verify the scan loop fetches multiple pages when the API reports more pages available."""
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    extra_item = _make_api_item(9003, title="Jupe plissée", brand="H&M", size="S", status_id=2, price="15.00", total_price="17.00", image_url="https://images1.vinted.net/t/women-9003.webp")

    women_api_url_p1 = _build_api_catalog_url(2001, 1)
    women_api_url_p2 = _build_api_catalog_url(2001, 2)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url_p1: FetchedPage(women_api_url_p1, 200, _make_api_page(WOMEN_ITEMS, current_page=1, total_pages=2)),
        women_api_url_p2: FetchedPage(women_api_url_p2, 200, _make_api_page([extra_item], current_page=2, total_pages=2)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=3, max_leaf_categories=1, root_scope="women", request_delay=0.0, min_price=0.0))

        assert report.successful_scans == 2
        assert report.raw_listing_hits == 3
        assert report.unique_listing_hits == 3


def test_discovery_service_invalid_json_recorded_as_failed_scan(tmp_path: Path) -> None:
    """Invalid JSON from the API should be recorded as a failed scan, not crash the run."""
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url = _build_api_catalog_url(2001, 1)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, "<html>Access Denied</html>"),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=1, root_scope="women", request_delay=0.0, min_price=0.0))

        assert report.successful_scans == 0
        assert report.failed_scans == 1
        assert report.unique_listing_hits == 0
        assert repository.count_rows("listings") == 0


def test_discovery_service_empty_page_stops_pagination(tmp_path: Path) -> None:
    """When the API returns an empty items list, pagination should stop immediately."""
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url_p1 = _build_api_catalog_url(2001, 1)
    women_api_url_p2 = _build_api_catalog_url(2001, 2)

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url_p1: FetchedPage(women_api_url_p1, 200, _make_api_page(WOMEN_ITEMS, current_page=1, total_pages=3)),
        # Page 2 returns no items — page 3 should never be requested.
        women_api_url_p2: FetchedPage(women_api_url_p2, 200, _make_api_page([], current_page=2, total_pages=3)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=5, max_leaf_categories=1, root_scope="women", request_delay=0.0, min_price=0.0))

        # 2 successful scans (page 1 with items + page 2 empty), page 3 never fetched.
        assert report.successful_scans == 2
        assert report.raw_listing_hits == 2  # Only from page 1
        assert report.unique_listing_hits == 2


def test_discovery_service_filters_out_low_value_and_non_target_brands(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url = _build_api_catalog_url(2001, 1, price_from=30.0)
    filtered_items = [
        _make_api_item(9201, title="Sac premium", brand="Louis Vuitton", size="TU", status_id=3, price="125.00", total_price="130.00", image_url="https://images1.vinted.net/t/women-9201.webp"),
        _make_api_item(9202, title="Top rapide", brand="Louis Vuitton", size="S", status_id=3, price="25.00", total_price="27.00", image_url="https://images1.vinted.net/t/women-9202.webp"),
        _make_api_item(9203, title="Veste mode", brand="Zara", size="M", status_id=3, price="95.00", total_price="99.00", image_url="https://images1.vinted.net/t/women-9203.webp"),
    ]

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(filtered_items, current_page=1, total_pages=1)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(
            DiscoveryOptions(
                page_limit=1,
                max_leaf_categories=1,
                root_scope="women",
                request_delay=0.0,
                min_price=30.0,
                target_brands=("louis vuitton",),
            )
        )
        scan = repository.connection.execute(
            """
            SELECT
                listing_count,
                api_listing_count,
                accepted_listing_count,
                filtered_out_count,
                accepted_ratio,
                min_price_seen_cents,
                max_price_seen_cents
            FROM catalog_scans
            WHERE run_id = ? AND catalog_id = ? AND page_number = 1
            """,
            (report.run_id, 2001),
        ).fetchone()

        assert report.successful_scans == 1
        assert report.raw_listing_hits == 3
        assert report.unique_listing_hits == 1
        assert repository.count_rows("listings") == 1
        assert repository.count_rows("listing_discoveries") == 1
        assert repository.count_rows("listing_observations") == 1
        assert scan is not None
        assert scan["listing_count"] == 3
        assert scan["api_listing_count"] == 3
        assert scan["accepted_listing_count"] == 1
        assert scan["filtered_out_count"] == 2
        assert scan["accepted_ratio"] == pytest.approx(1 / 3)
        assert scan["min_price_seen_cents"] == 2500
        assert scan["max_price_seen_cents"] == 12500


def test_discovery_service_restricts_scans_to_target_catalog_ids(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    men_api_url = _build_api_catalog_url(3001, 1)
    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        men_api_url: FetchedPage(men_api_url, 200, _make_api_page(MEN_ITEMS, current_page=1, total_pages=1)),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(
            DiscoveryOptions(
                page_limit=1,
                root_scope="both",
                request_delay=0.0,
                target_catalogs=(3001,),
                min_price=0.0,
            )
        )

        assert report.total_leaf_catalogs == 2
        assert report.scanned_leaf_catalogs == 1
        assert report.successful_scans == 1
        assert report.raw_listing_hits == 1
        assert report.unique_listing_hits == 1
        assert repository.count_rows("listings") == 1



def test_discovery_service_emits_retrievable_listing_seen_evidence_batches(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    women_api_url = _build_api_catalog_url(2001, 1)
    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(WOMEN_ITEMS, current_page=1, total_pages=1)),
    }
    publisher, postgres_connection = _build_evidence_publisher()

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(
            repository=repository,
            http_client=FakeHttpClient(pages),
            evidence_publisher=publisher,
        )
        report = service.run(
            DiscoveryOptions(
                page_limit=1,
                max_leaf_categories=1,
                root_scope="women",
                request_delay=0.0,
                min_price=0.0,
            )
        )

        assert len(report.evidence_batches) == 1
        batch = report.evidence_batches[0]
        assert batch["event_type"] == "vinted.discovery.listing-seen.batch"
        assert batch["row_count"] == 2
        assert batch["outbox_publish"]["sinks"] == ["parquet"]
        assert batch["outbox_publish"]["delivery_rows_created"] == 1

        parquet_key = str(batch["lake_write"]["parquet_object"]["key"])
        rows = publisher.lake_writer.read_rows(parquet_key) if publisher.lake_writer is not None else []
        assert [row["listing_id"] for row in rows] == [9001, 9002]
        assert rows[0]["catalog_id"] == 2001
        assert json.loads(str(rows[0]["raw_card"]))["evidence_source"] == "api"
        assert len(postgres_connection.outbox) == 1
