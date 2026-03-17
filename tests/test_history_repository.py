from __future__ import annotations

from pathlib import Path

from vinted_radar.http import FetchedPage
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryService

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttpClient:
    def __init__(self, pages_by_run: list[dict[str, FetchedPage]]) -> None:
        self.pages_by_run = pages_by_run
        self.run_index = 0

    def start_next_run(self) -> None:
        if self.run_index >= len(self.pages_by_run):
            raise AssertionError("No more fake HTTP runs configured")
        self.active_pages = self.pages_by_run[self.run_index]
        self.run_index += 1

    def get_text(self, url: str) -> FetchedPage:
        try:
            return self.active_pages[url]
        except KeyError as exc:  # pragma: no cover - test setup failure
            raise AssertionError(f"Unexpected URL requested: {url}") from exc


class SequenceClock:
    def __init__(self, timestamps: list[str]) -> None:
        self.timestamps = timestamps
        self.index = 0

    def __call__(self) -> str:
        if self.index >= len(self.timestamps):
            raise AssertionError("Clock exhausted")
        value = self.timestamps[self.index]
        self.index += 1
        return value


def test_history_repository_tracks_repeated_runs_and_freshness(tmp_path: Path) -> None:
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    women_page_run1 = (FIXTURES / "catalog-page-women.html").read_text(encoding="utf-8")
    women_page_run2 = (FIXTURES / "catalog-page-women-run2.html").read_text(encoding="utf-8")
    men_page = (FIXTURES / "catalog-page-men.html").read_text(encoding="utf-8")

    run1_pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        "https://www.vinted.fr/catalog/2001-womens-dresses": FetchedPage("https://www.vinted.fr/catalog/2001-womens-dresses", 200, women_page_run1),
        "https://www.vinted.fr/catalog/3001-men-trousers": FetchedPage("https://www.vinted.fr/catalog/3001-men-trousers", 200, men_page),
    }
    run2_pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        "https://www.vinted.fr/catalog/2001-womens-dresses": FetchedPage("https://www.vinted.fr/catalog/2001-womens-dresses", 200, women_page_run2),
        "https://www.vinted.fr/catalog/3001-men-trousers": FetchedPage("https://www.vinted.fr/catalog/3001-men-trousers", 200, men_page),
    }
    http_client = FakeHttpClient([run1_pages, run2_pages])
    clock = SequenceClock(
        [
            "2026-03-17T10:00:00+00:00",
            "2026-03-17T10:05:00+00:00",
            "2026-03-17T10:06:00+00:00",
            "2026-03-18T12:00:00+00:00",
            "2026-03-18T12:05:00+00:00",
            "2026-03-18T12:06:00+00:00",
        ]
    )

    with RadarRepository(tmp_path / "radar.db") as repository:
        service = DiscoveryService(repository=repository, http_client=http_client, now_provider=clock)

        http_client.start_next_run()
        service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0))
        http_client.start_next_run()
        service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0))

        history = repository.listing_history(9001, now="2026-03-18T18:00:00+00:00")
        freshness = repository.freshness_summary(now="2026-03-18T18:00:00+00:00")
        candidates = repository.revisit_candidates(limit=3, now="2026-03-20T18:00:00+00:00")

        assert history is not None
        assert history["summary"]["observation_count"] == 2
        assert history["summary"]["first_seen_at"] == "2026-03-17T10:05:00+00:00"
        assert history["summary"]["last_seen_at"] == "2026-03-18T12:05:00+00:00"
        assert history["summary"]["freshness_bucket"] == "fresh-followup"
        assert history["summary"]["average_revisit_hours"] == 26.0
        assert history["timeline"][0]["price_amount_cents"] == 1500
        assert history["timeline"][1]["price_amount_cents"] == 1250

        overall = freshness["overall"]
        assert overall["tracked_listings"] == 4
        assert overall["first-pass-only"] == 2
        assert overall["fresh-followup"] == 2
        assert candidates[0]["listing_id"] == 9002
        assert "under-observed" in candidates[0]["priority_reasons"]


def test_database_migration_backfills_observations_from_s01_discoveries(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    with RadarRepository(db_path) as repository:
        repository.connection.execute("DROP TABLE listing_observations")
        repository.connection.execute(
            """
            INSERT INTO discovery_runs (
                run_id, started_at, status, root_scope, page_limit, max_leaf_categories, request_delay_seconds
            ) VALUES ('run-1', '2026-03-17T10:00:00+00:00', 'completed', 'both', 1, 2, 0.0)
            """
        )
        repository.connection.execute(
            "INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at) VALUES (1904, 1904, 'Femmes', NULL, 'Femmes', 'WOMEN_ROOT', 'https://www.vinted.fr/catalog/1904-women', 'Femmes', 0, 0, 1, 0, '2026-03-17T10:00:00+00:00')"
        )
        repository.connection.execute(
            "INSERT INTO catalogs (catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code, url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at) VALUES (2001, 1904, 'Femmes', 1904, 'Robes', 'WOMEN_DRESSES', 'https://www.vinted.fr/catalog/2001-womens-dresses', 'Femmes > Robes', 1, 1, 1, 10, '2026-03-17T10:00:00+00:00')"
        )
        repository.connection.execute(
            """
            INSERT INTO listings (
                listing_id, canonical_url, source_url, title, brand, size_label, condition_label,
                price_amount_cents, price_currency, total_price_amount_cents, total_price_currency,
                image_url, primary_catalog_id, primary_root_catalog_id, first_discovered_at,
                last_discovered_at, last_seen_run_id, last_card_payload_json
            ) VALUES (
                9001, 'https://www.vinted.fr/items/9001-robe-noire', 'https://www.vinted.fr/items/9001-robe-noire?referrer=catalog',
                'Robe noire', 'Zara', 'M', 'Très bon état', 1250, '€', 1413, '€',
                'https://images1.vinted.net/t/women-9001.webp', 2001, 1904, '2026-03-17T10:05:00+00:00',
                '2026-03-17T10:05:00+00:00', 'run-1', '{"description_title": "Zara"}'
            )
            """
        )
        repository.connection.execute(
            """
            INSERT INTO listing_discoveries (
                run_id, listing_id, observed_at, source_catalog_id, source_page_number, source_url, card_position, raw_card_payload_json
            ) VALUES (
                'run-1', 9001, '2026-03-17T10:05:00+00:00', 2001, 1,
                'https://www.vinted.fr/items/9001-robe-noire?referrer=catalog', 1,
                '{"overlay_title": "Robe noire, marque: Zara, État: Très bon état, taille: M, 12,50 €, 14,13 € Protection acheteurs incluse", "description_title": "Zara", "description_subtitle": "M · Très bon état", "price_text": "12,50 €", "total_price_text": "14,13 €"}'
            )
            """
        )
        repository.connection.commit()

    reopened = RadarRepository(db_path)
    try:
        history = reopened.listing_history(9001, now="2026-03-17T12:00:00+00:00")
        assert reopened.count_rows("listing_observations") == 1
        assert history is not None
        assert history["summary"]["observation_count"] == 1
        assert history["timeline"][0]["title"] == "Robe noire"
    finally:
        reopened.close()
