from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from vinted_radar.http import FetchedPage
from vinted_radar.platform.config import (
    ENABLE_CLICKHOUSE_WRITES_ENV,
    ENABLE_OBJECT_STORAGE_WRITES_ENV,
    ENABLE_POLYGLOT_READS_ENV,
    ENABLE_POSTGRES_WRITES_ENV,
    load_platform_config,
)
from vinted_radar.platform.lake_writer import CollectorEvidencePublisher
from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryService, _build_api_catalog_url
from vinted_radar.services.runtime import RadarRuntimeOptions, RadarRuntimeService
from vinted_radar.services.state_refresh import StateRefreshService

FIXTURES = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.skipif(shutil.which("docker") is None, reason="docker binary is required for the cutover smoke stack test")


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



def _make_api_item(
    item_id: int,
    *,
    title: str,
    brand: str,
    size: str,
    status_id: int,
    price: str,
    total_price: str,
    image_url: str,
    user_id: int,
    user_login: str,
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": title,
        "url": f"/items/{item_id}-{title.lower().replace(' ', '-')}",
        "brand_title": brand,
        "size_title": size,
        "status_id": status_id,
        "price": {"amount": price, "currency_code": "EUR"},
        "total_item_price": {"amount": total_price, "currency_code": "EUR"},
        "photo": {
            "url": image_url,
            "high_resolution": {"timestamp": 1711101600 + item_id},
        },
        "favourite_count": 10 + (item_id % 5),
        "view_count": 100 + (item_id % 11),
        "user": {
            "id": user_id,
            "login": user_login,
            "profile_url": f"https://www.vinted.fr/member/{user_id}",
        },
    }



def _make_api_page(items: list[dict[str, object]], *, current_page: int, total_pages: int) -> str:
    return json.dumps(
        {
            "items": items,
            "pagination": {
                "current_page": current_page,
                "total_pages": total_pages,
                "per_page": 96,
                "total_entries": len(items),
            },
        }
    )



def _item_page_html(
    listing_id: int,
    *,
    can_buy: bool,
    is_closed: bool,
    is_hidden: bool,
    is_reserved: bool,
) -> str:
    return (
        '<html><head><title>Item</title></head><body><script>'
        f'{{"item_id":{listing_id},"can_buy":{str(can_buy).lower()},"is_closed":{str(is_closed).lower()},'
        f'"is_hidden":{str(is_hidden).lower()},"is_reserved":{str(is_reserved).lower()}}}'
        "</script></body></html>"
    )



def _build_cutover_env(data_platform_stack) -> dict[str, str]:
    env = dict(data_platform_stack.env)
    env.update(
        {
            ENABLE_POSTGRES_WRITES_ENV: "true",
            ENABLE_CLICKHOUSE_WRITES_ENV: "true",
            ENABLE_OBJECT_STORAGE_WRITES_ENV: "true",
            ENABLE_POLYGLOT_READS_ENV: "true",
        }
    )
    return env



def test_live_cutover_smoke_proof_runs_real_cycle_and_verifier(
    data_platform_stack,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    env = _build_cutover_env(data_platform_stack)
    config = load_platform_config(env=env)
    db_path = tmp_path / "cutover-smoke.db"

    bootstrap = subprocess.run(
        [sys.executable, "-m", "vinted_radar.cli", "platform-bootstrap"],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr

    catalog_root = (FIXTURES / "catalog-root.html").read_text(encoding="utf-8")
    women_api_url = _build_api_catalog_url(2001, 1)
    api_items = [
        _make_api_item(
            9001,
            title="Robe active",
            brand="Zara",
            size="M",
            status_id=3,
            price="39.00",
            total_price="42.50",
            image_url="https://images1.vinted.net/t/women-9001.webp",
            user_id=41,
            user_login="alice",
        ),
        _make_api_item(
            9002,
            title="Robe soldée",
            brand="Maje",
            size="S",
            status_id=4,
            price="55.00",
            total_price="59.00",
            image_url="https://images1.vinted.net/t/women-9002.webp",
            user_id=42,
            user_login="bruno",
        ),
    ]
    pages = {
        "https://www.vinted.fr/catalog": FetchedPage("https://www.vinted.fr/catalog", 200, catalog_root),
        women_api_url: FetchedPage(women_api_url, 200, _make_api_page(api_items, current_page=1, total_pages=1)),
        "https://www.vinted.fr/items/9001-robe-active": FetchedPage(
            "https://www.vinted.fr/items/9001-robe-active",
            200,
            _item_page_html(9001, can_buy=True, is_closed=False, is_hidden=False, is_reserved=False),
        ),
        "https://www.vinted.fr/items/9002-robe-soldée": FetchedPage(
            "https://www.vinted.fr/items/9002-robe-soldée",
            200,
            _item_page_html(9002, can_buy=False, is_closed=True, is_hidden=False, is_reserved=False),
        ),
    }

    def discovery_factory(**kwargs) -> DiscoveryService:
        return DiscoveryService(
            repository=RadarRepository(db_path),
            http_client=FakeHttpClient(pages),
            evidence_publisher=CollectorEvidencePublisher.from_environment(config=config),
            mutable_truth_repository=PostgresMutableTruthRepository.from_dsn(config.postgres.dsn),
        )

    def state_refresh_factory(**kwargs) -> StateRefreshService:
        return StateRefreshService(
            repository=RadarRepository(db_path),
            http_client=FakeHttpClient(pages),
            evidence_publisher=CollectorEvidencePublisher.from_environment(config=config),
            mutable_truth_repository=PostgresMutableTruthRepository.from_dsn(config.postgres.dsn),
        )

    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=discovery_factory,
        state_refresh_service_factory=state_refresh_factory,
        control_plane_repository=PostgresMutableTruthRepository.from_dsn(config.postgres.dsn),
    )
    try:
        report = runtime.run_cycle(
            RadarRuntimeOptions(
                page_limit=1,
                max_leaf_categories=1,
                root_scope="women",
                request_delay=0.0,
                timeout_seconds=5.0,
                state_refresh_limit=2,
                min_price=0.0,
                max_price=0.0,
                target_catalogs=(2001,),
            ),
            mode="batch",
        )
    finally:
        runtime.close()

    assert report.status == "completed"
    assert report.discovery_run_id is not None
    assert report.state_probed_count == 2

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_cutover_stack.py",
            "--db-path",
            str(db_path),
            "--listing-id",
            "9001",
            "--json",
        ],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    proof = json.loads(result.stdout)

    assert proof["cutover"]["mode"] == "polyglot-cutover"
    assert proof["doctor"]["ok"] is True
    assert proof["clickhouse_ingest"]["status"]["status"] != "failed"
    assert any(report_row["claimed_count"] > 0 for report_row in proof["clickhouse_ingest"]["reports"])
    assert proof["dashboard"]["primary_payload_source"] == "clickhouse.overview_snapshot"

    audit_summary = proof["platform_audit"]["summary"]
    assert audit_summary["reconciliation_status"] == "match"
    assert audit_summary["current_state_status"] in {"healthy", "active"}
    assert audit_summary["analytical_status"] in {"healthy", "active"}
    assert audit_summary["lifecycle_status"] != "failed"
    assert audit_summary["backfill_status"] in {"healthy", "complete"}

    feature_marts = proof["feature_marts"]
    assert feature_marts["source"] == "clickhouse.feature_marts"
    assert feature_marts["listing_day_row_count"] >= 1
    assert feature_marts["change_fact_row_count"] >= 1
    assert proof["postgres_truth"]["latest_discovery_run_id"] in feature_marts["fresh_change_fact_run_ids"]
    assert feature_marts["evidence_pack_row_count"] >= 1
    assert any(
        "evidence-inspect --manifest-id" in command
        for command in feature_marts["evidence_drill_down"]["inspect_examples"]
    )

    route_parity = proof["clickhouse_route_parity"]
    assert route_parity["repository"]["dashboard_source"] == "repository.overview_snapshot"
    assert route_parity["clickhouse"]["dashboard_source"] == "clickhouse.overview_snapshot"
    assert route_parity["parity"] == {
        "dashboard_api": "match",
        "explorer_api": "match",
        "detail_api": "match",
        "health": "match",
    }

    serving_labels = {check["label"] for check in proof["serving"]["checks"]}
    assert serving_labels == {
        "overview",
        "explorer",
        "runtime",
        "runtime-api",
        "listing-detail",
        "listing-detail-api",
        "health",
    }

    assert proof["explorer"]["total_listings"] >= 1
    assert proof["postgres_truth"]["latest_discovery_run_status"] == "completed"
    assert proof["postgres_truth"]["latest_runtime_cycle"]["status"] == "completed"
    assert proof["object_storage"]["non_marker_counts"]["raw_events"] > 0
    assert proof["object_storage"]["non_marker_counts"]["manifests"] > 0
    assert proof["object_storage"]["non_marker_counts"]["parquet"] > 0
