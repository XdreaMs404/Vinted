from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.http import FetchedPage
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryService

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttpClient:
    def __init__(self, pages_by_run: list[dict[str, FetchedPage]]) -> None:
        self.pages_by_run = pages_by_run
        self.run_index = 0

    def start_next_run(self) -> None:
        self.active_pages = self.pages_by_run[self.run_index]
        self.run_index += 1

    def get_text(self, url: str) -> FetchedPage:
        return self.active_pages[url]


class SequenceClock:
    def __init__(self, timestamps: list[str]) -> None:
        self.timestamps = timestamps
        self.index = 0

    def __call__(self) -> str:
        value = self.timestamps[self.index]
        self.index += 1
        return value


def test_history_cli_surfaces_json_views_for_history_freshness_and_revisit_plan(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    women_page = (FIXTURES / "catalog-page-women.html").read_text(encoding="utf-8")
    women_page_run2 = (FIXTURES / "catalog-page-women-run2.html").read_text(encoding="utf-8")
    men_page = (FIXTURES / "catalog-page-men.html").read_text(encoding="utf-8")

    http_client = FakeHttpClient(
        [
            {
                "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
                "https://www.vinted.fr/catalog/2001-womens-dresses": FetchedPage("https://www.vinted.fr/catalog/2001-womens-dresses", 200, women_page),
                "https://www.vinted.fr/catalog/3001-men-trousers": FetchedPage("https://www.vinted.fr/catalog/3001-men-trousers", 200, men_page),
            },
            {
                "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
                "https://www.vinted.fr/catalog/2001-womens-dresses": FetchedPage("https://www.vinted.fr/catalog/2001-womens-dresses", 200, women_page_run2),
                "https://www.vinted.fr/catalog/3001-men-trousers": FetchedPage("https://www.vinted.fr/catalog/3001-men-trousers", 200, men_page),
            },
        ]
    )
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

    with RadarRepository(db_path) as repository:
        service = DiscoveryService(repository=repository, http_client=http_client, now_provider=clock)
        http_client.start_next_run()
        service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0))
        http_client.start_next_run()
        service.run(DiscoveryOptions(page_limit=1, max_leaf_categories=2, root_scope="both", request_delay=0.0))

    runner = CliRunner()

    freshness_result = runner.invoke(app, ["freshness", "--db", str(db_path), "--now", "2026-03-18T18:00:00+00:00", "--format", "json"])
    revisit_result = runner.invoke(app, ["revisit-plan", "--db", str(db_path), "--now", "2026-03-20T18:00:00+00:00", "--limit", "3", "--format", "json"])
    history_result = runner.invoke(app, ["history", "--db", str(db_path), "--listing-id", "9001", "--now", "2026-03-18T18:00:00+00:00", "--format", "json"])

    assert freshness_result.exit_code == 0
    assert revisit_result.exit_code == 0
    assert history_result.exit_code == 0

    freshness_payload = json.loads(freshness_result.stdout)
    revisit_payload = json.loads(revisit_result.stdout)
    history_payload = json.loads(history_result.stdout)

    assert freshness_payload["overall"]["fresh-followup"] == 2
    assert freshness_payload["overall"]["first-pass-only"] == 2
    assert revisit_payload[0]["listing_id"] == 9002
    assert history_payload["summary"]["observation_count"] == 2
    assert history_payload["timeline"][0]["price_amount_cents"] == 1500
