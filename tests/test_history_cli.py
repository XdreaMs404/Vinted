from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.http import FetchedPage
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryService, _build_api_catalog_url

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers: API JSON builders
# ---------------------------------------------------------------------------

def _make_api_item(item_id, *, title, brand, size, status_id, price, total_price, image_url):
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


def _make_api_page(items, *, current_page=1, total_pages=1, per_page=96):
    return json.dumps({
        "items": items,
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "per_page": per_page,
            "total_entries": len(items),
        },
    })


# Items matching the old HTML fixtures
WOMEN_ITEMS_RUN1 = [
    _make_api_item(9001, title="Robe noire", brand="Zara", size="M", status_id=3, price="12.50", total_price="14.13", image_url="https://images1.vinted.net/t/women-9001.webp"),
    _make_api_item(9002, title="Chemise vintage", brand="Sézane", size="S", status_id=4, price="22.00", total_price="24.20", image_url="https://images1.vinted.net/t/women-9002.webp"),
]
WOMEN_ITEMS_RUN2 = [
    _make_api_item(9001, title="Robe noire", brand="Zara", size="M", status_id=3, price="15.00", total_price="16.50", image_url="https://images1.vinted.net/t/women-9001.webp"),
    _make_api_item(9999, title="Pull côtelé", brand="Sandro", size="M", status_id=3, price="30.00", total_price="33.00", image_url="https://images1.vinted.net/t/women-9999.webp"),
]
MEN_ITEMS = [
    _make_api_item(9101, title="Pantalon cargo", brand="Carhartt", size="L", status_id=1, price="35.00", total_price="38.15", image_url="https://images1.vinted.net/t/men-9101.webp"),
]


# ---------------------------------------------------------------------------
# Fake HTTP client
# ---------------------------------------------------------------------------

class FakeHttpClient:
    def __init__(self, pages_by_run: list[dict[str, FetchedPage]]) -> None:
        self.pages_by_run = pages_by_run
        self.run_index = 0

    def start_next_run(self) -> None:
        self.active_pages = self.pages_by_run[self.run_index]
        self.run_index += 1

    def get_text(self, url: str) -> FetchedPage:
        return self.active_pages[url]

    async def get_text_async(self, url: str) -> FetchedPage:
        return self.get_text(url)


class SequenceClock:
    def __init__(self, timestamps: list[str]) -> None:
        self.timestamps = timestamps
        self.index = 0

    def __call__(self) -> str:
        value = self.timestamps[self.index]
        self.index += 1
        return value


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_history_cli_surfaces_json_views_for_history_freshness_and_revisit_plan(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")

    women_api_url = _build_api_catalog_url(2001, 1)
    men_api_url = _build_api_catalog_url(3001, 1)

    http_client = FakeHttpClient(
        [
            {
                "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
                women_api_url: FetchedPage(women_api_url, 200, _make_api_page(WOMEN_ITEMS_RUN1)),
                men_api_url: FetchedPage(men_api_url, 200, _make_api_page(MEN_ITEMS)),
            },
            {
                "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
                women_api_url: FetchedPage(women_api_url, 200, _make_api_page(WOMEN_ITEMS_RUN2)),
                men_api_url: FetchedPage(men_api_url, 200, _make_api_page(MEN_ITEMS)),
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
