from __future__ import annotations

from pathlib import Path

from vinted_radar.http import FetchedPage
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryService

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttpClient:
    def __init__(self, pages: dict[str, FetchedPage]) -> None:
        self.pages = pages

    def get_text(self, url: str) -> FetchedPage:
        try:
            return self.pages[url]
        except KeyError as exc:  # pragma: no cover - test setup failure
            raise AssertionError(f"Unexpected URL requested: {url}") from exc


def test_discovery_service_persists_catalogs_listings_and_coverage(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    women_page = (FIXTURES / "catalog-page-women.html").read_text(encoding="utf-8")
    men_page = (FIXTURES / "catalog-page-men.html").read_text(encoding="utf-8")

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        "https://www.vinted.fr/catalog/2001-womens-dresses": FetchedPage("https://www.vinted.fr/catalog/2001-womens-dresses", 200, women_page),
        "https://www.vinted.fr/catalog/3001-men-trousers": FetchedPage("https://www.vinted.fr/catalog/3001-men-trousers", 200, men_page),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0))
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
    women_page = (FIXTURES / "catalog-page-women.html").read_text(encoding="utf-8")

    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        "https://www.vinted.fr/catalog/2001-womens-dresses": FetchedPage("https://www.vinted.fr/catalog/2001-womens-dresses", 200, women_page),
        "https://www.vinted.fr/catalog/3001-men-trousers": FetchedPage("https://www.vinted.fr/catalog/3001-men-trousers", 503, "service unavailable"),
    }

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=FakeHttpClient(pages))
        report = service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0))
        summary = repository.coverage_summary(report.run_id)

        assert report.successful_scans == 1
        assert report.failed_scans == 1
        assert report.unique_listing_hits == 2
        assert summary is not None
        assert len(summary["failures"]) == 1
        assert summary["failures"][0]["error_message"] == "HTTP 503"
        assert repository.count_rows("listings") == 2
