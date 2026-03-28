from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from vinted_radar.http import FetchedPage
from vinted_radar.models import CatalogNode, ListingCard
from vinted_radar.platform.lake_writer import CollectorEvidencePublisher, ParquetLakeWriter
from vinted_radar.platform.object_store import S3ObjectStore
from vinted_radar.platform.outbox import PostgresOutbox
from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryRunReport, DiscoveryService, _build_api_catalog_url
from vinted_radar.services.runtime import RadarRuntimeOptions, RadarRuntimeService
from vinted_radar.services.state_refresh import StateRefreshReport, StateRefreshService

from tests.platform_test_fakes import FakePostgresConnection, FakeS3Client


class PersistingDiscoveryService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.repository = RadarRepository(db_path)
        self.last_options = None

    def run(self, options) -> DiscoveryRunReport:
        self.last_options = options
        run_id = self.repository.start_run(
            root_scope=options.root_scope,
            page_limit=options.page_limit,
            max_leaf_categories=options.max_leaf_categories,
            request_delay_seconds=options.request_delay,
        )
        synced_at = "2026-03-20T10:00:00+00:00"
        observed_at = "2026-03-20T10:05:00+00:00"
        root_catalog = CatalogNode(
            catalog_id=1904,
            root_catalog_id=1904,
            root_title="Femmes",
            parent_catalog_id=None,
            title="Femmes",
            code="WOMEN_ROOT",
            url="https://www.vinted.fr/catalog/1904-women",
            path=("Femmes",),
            depth=0,
            is_leaf=False,
            allow_browsing_subcategories=True,
            order_index=0,
        )
        leaf_catalog = CatalogNode(
            catalog_id=2001,
            root_catalog_id=1904,
            root_title="Femmes",
            parent_catalog_id=1904,
            title="Robes",
            code="WOMEN_DRESSES",
            url="https://www.vinted.fr/catalog/2001-womens-dresses",
            path=("Femmes", "Robes"),
            depth=1,
            is_leaf=True,
            allow_browsing_subcategories=True,
            order_index=10,
        )
        listing = ListingCard(
            listing_id=9001,
            source_url="https://www.vinted.fr/items/9001?referrer=catalog",
            canonical_url="https://www.vinted.fr/items/9001-runtime",
            title="Runtime robe",
            brand="Zara",
            size_label="M",
            condition_label="Très bon état",
            price_amount_cents=1500,
            price_currency="€",
            total_price_amount_cents=1650,
            total_price_currency="€",
            image_url="https://images/9001.webp",
            source_catalog_id=2001,
            source_root_catalog_id=1904,
            raw_card={"overlay_title": "Runtime robe"},
        )
        self.repository.upsert_catalogs([root_catalog, leaf_catalog], synced_at=synced_at)
        self.repository.update_run_catalog_totals(run_id, total_seed_catalogs=2, total_leaf_catalogs=1)
        self.repository.record_catalog_scan(
            run_id=run_id,
            catalog_id=2001,
            page_number=1,
            requested_url=leaf_catalog.url,
            fetched_at=observed_at,
            response_status=200,
            success=True,
            listing_count=1,
            pagination_total_pages=1,
            next_page_url=None,
            error_message=None,
        )
        self.repository.upsert_listing(
            listing,
            discovered_at=observed_at,
            primary_catalog_id=2001,
            primary_root_catalog_id=1904,
            run_id=run_id,
        )
        self.repository.record_listing_discovery(
            run_id=run_id,
            listing=listing,
            observed_at=observed_at,
            source_catalog_id=2001,
            source_page_number=1,
            card_position=1,
        )
        self.repository.record_listing_observation(
            run_id=run_id,
            listing=listing,
            observed_at=observed_at,
            source_catalog_id=2001,
            source_page_number=1,
            card_position=1,
        )
        self.repository.complete_run(
            run_id,
            status="completed",
            scanned_leaf_catalogs=1,
            successful_scans=1,
            failed_scans=0,
            raw_listing_hits=1,
            unique_listing_hits=1,
        )
        return DiscoveryRunReport(
            run_id=run_id,
            total_seed_catalogs=2,
            total_leaf_catalogs=1,
            scanned_leaf_catalogs=1,
            successful_scans=1,
            failed_scans=0,
            raw_listing_hits=1,
            unique_listing_hits=1,
        )


class FailingDiscoveryService:
    def __init__(self, db_path: Path, message: str = "discovery exploded") -> None:
        self.repository = RadarRepository(db_path)
        self.message = message

    def run(self, options) -> DiscoveryRunReport:
        raise RuntimeError(self.message)


class FakeStateRefreshService:
    def __init__(self, db_path: Path) -> None:
        self.repository = RadarRepository(db_path)
        self.refresh_calls: list[dict[str, object]] = []

    def refresh(
        self,
        *,
        limit: int = 10,
        listing_id: int | None = None,
        now: str | None = None,
        include_state_summary: bool = True,
    ) -> StateRefreshReport:
        self.refresh_calls.append(
            {
                "limit": limit,
                "listing_id": listing_id,
                "now": now,
                "include_state_summary": include_state_summary,
            }
        )
        probed_ids = [9001] if limit else []
        return StateRefreshReport(
            probed_count=len(probed_ids),
            probed_listing_ids=probed_ids,
            probe_summary={
                "status": "healthy",
                "requested_limit": limit,
                "selected_target_count": len(probed_ids),
                "probed_count": len(probed_ids),
                "direct_signal_count": len(probed_ids),
                "inconclusive_probe_count": 0,
                "degraded_probe_count": 0,
                "anti_bot_challenge_count": 0,
                "http_error_count": 0,
                "transport_error_count": 0,
                "outcome_counts": {
                    "active": len(probed_ids),
                    "sold": 0,
                    "unavailable": 0,
                    "deleted": 0,
                    "unknown": 0,
                },
                "reason_counts": {"buy_signal_open": len(probed_ids)},
                "degraded_listing_ids": [],
            },
            state_summary={
                "generated_at": now or "2026-03-20T10:10:00+00:00",
                "overall": {"tracked_listings": 1},
                "by_root": [],
            },
        )


class DiscoveryFactorySequence:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.call_count = 0

    def __call__(self, *, db_path: str, timeout_seconds: float, request_delay: float, proxies: list[str] | None = None):
        self.call_count += 1
        if self.call_count == 1:
            return FailingDiscoveryService(self.db_path)
        return PersistingDiscoveryService(self.db_path)


class StateFactory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def __call__(self, *, db_path: str, timeout_seconds: float, request_delay: float, proxies: list[str] | None = None):
        return FakeStateRefreshService(self.db_path)


class CapturingStateFactory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.calls: list[dict[str, object]] = []
        self.services: list[FakeStateRefreshService] = []

    def __call__(self, *, db_path: str, timeout_seconds: float, request_delay: float, proxies: list[str] | None = None):
        self.calls.append(
            {
                "db_path": db_path,
                "timeout_seconds": timeout_seconds,
                "request_delay": request_delay,
                "proxies": proxies,
            }
        )
        service = FakeStateRefreshService(self.db_path)
        self.services.append(service)
        return service


class CapturingDiscoveryFactory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.calls: list[dict[str, object]] = []
        self.services: list[PersistingDiscoveryService] = []

    def __call__(self, *, db_path: str, timeout_seconds: float, request_delay: float, proxies: list[str] | None = None):
        self.calls.append(
            {
                "db_path": db_path,
                "timeout_seconds": timeout_seconds,
                "request_delay": request_delay,
                "proxies": proxies,
            }
        )
        service = PersistingDiscoveryService(self.db_path)
        self.services.append(service)
        return service


class FakeClock:
    def __init__(self, start_at: str) -> None:
        self.current = datetime.fromisoformat(start_at).astimezone(UTC)

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)

    def iso(self) -> str:
        return self.current.replace(microsecond=0).isoformat()


def test_runtime_service_persists_completed_cycle_and_runtime_status(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=lambda **kwargs: PersistingDiscoveryService(db_path),
        state_refresh_service_factory=lambda **kwargs: FakeStateRefreshService(db_path),
    )

    report = runtime.run_cycle(
        RadarRuntimeOptions(
            page_limit=1,
            max_leaf_categories=1,
            root_scope="women",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=3,
        ),
        mode="batch",
    )

    assert report.status == "completed"
    assert report.phase == "completed"
    assert report.discovery_run_id is not None
    assert report.tracked_listings == 1
    assert report.freshness_counts["first-pass-only"] == 1
    assert report.state_probed_count == 1
    assert report.state_refresh_summary is not None
    assert report.state_refresh_summary["status"] == "healthy"

    with RadarRepository(db_path) as repository:
        status = repository.runtime_status(limit=5)

    latest = status["latest_cycle"]
    assert latest is not None
    assert latest["cycle_id"] == report.cycle_id
    assert latest["status"] == "completed"
    assert latest["mode"] == "batch"
    assert latest["discovery_run_id"] == report.discovery_run_id
    assert latest["tracked_listings"] == 1
    assert latest["state_probe_limit"] == 3
    assert latest["state_refresh_summary"]["status"] == "healthy"
    assert latest["state_refresh_summary"]["direct_signal_count"] == 1
    assert status["controller"] is not None
    assert status["controller"]["status"] == "idle"
    assert status["controller"]["latest_cycle_id"] == report.cycle_id
    assert status["totals"]["completed_cycles"] == 1
    assert status["latest_failure"] is None


def test_runtime_service_passes_proxy_pool_to_discovery_and_state_refresh_factories(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    discovery_factory = CapturingDiscoveryFactory(db_path)
    state_factory = CapturingStateFactory(db_path)
    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=discovery_factory,
        state_refresh_service_factory=state_factory,
    )

    report = runtime.run_cycle(
        RadarRuntimeOptions(
            page_limit=1,
            max_leaf_categories=1,
            root_scope="women",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=3,
            proxies=("http://proxy-a:8080", "http://proxy-b:8080"),
        ),
        mode="batch",
    )

    assert report.status == "completed"
    assert discovery_factory.calls == [
        {
            "db_path": str(db_path),
            "timeout_seconds": 5.0,
            "request_delay": 0.0,
            "proxies": ["http://proxy-a:8080", "http://proxy-b:8080"],
        }
    ]
    assert state_factory.calls == [
        {
            "db_path": str(db_path),
            "timeout_seconds": 5.0,
            "request_delay": 0.0,
            "proxies": ["http://proxy-a:8080", "http://proxy-b:8080"],
        }
    ]



def test_runtime_service_skips_global_state_summary_during_runtime_cycles(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    discovery_factory = CapturingDiscoveryFactory(db_path)
    state_factory = CapturingStateFactory(db_path)
    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=discovery_factory,
        state_refresh_service_factory=state_factory,
    )

    report = runtime.run_cycle(
        RadarRuntimeOptions(
            page_limit=1,
            max_leaf_categories=1,
            root_scope="women",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=3,
        ),
        mode="batch",
    )

    assert report.status == "completed"
    assert len(state_factory.services) == 1
    assert state_factory.services[0].refresh_calls == [
        {
            "limit": 3,
            "listing_id": None,
            "now": None,
            "include_state_summary": False,
        }
    ]



def test_runtime_service_passes_high_value_filters_to_discovery_service(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    discovery_factory = CapturingDiscoveryFactory(db_path)
    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=discovery_factory,
        state_refresh_service_factory=lambda **kwargs: FakeStateRefreshService(db_path),
    )

    report = runtime.run_cycle(
        RadarRuntimeOptions(
            page_limit=2,
            max_leaf_categories=4,
            root_scope="both",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=3,
            min_price=85.0,
            target_catalogs=(2001, 3001),
            target_brands=("Chanel", "Hermès"),
        ),
        mode="batch",
    )

    assert report.status == "completed"
    assert len(discovery_factory.services) == 1
    forwarded_options = discovery_factory.services[0].last_options
    assert forwarded_options is not None
    assert forwarded_options.min_price == 85.0
    assert forwarded_options.target_catalogs == (2001, 3001)
    assert forwarded_options.target_brands == ("Chanel", "Hermès")


def test_runtime_service_defaults_to_bounded_discovery_options(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    discovery_factory = CapturingDiscoveryFactory(db_path)
    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=discovery_factory,
        state_refresh_service_factory=lambda **kwargs: FakeStateRefreshService(db_path),
    )

    report = runtime.run_cycle(
        RadarRuntimeOptions(
            page_limit=1,
            max_leaf_categories=1,
            root_scope="women",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=3,
        ),
        mode="batch",
    )

    assert report.status == "completed"
    assert len(discovery_factory.services) == 1
    forwarded_options = discovery_factory.services[0].last_options
    assert forwarded_options is not None
    assert forwarded_options.min_price == 30.0
    assert forwarded_options.max_price == 0.0


def test_runtime_service_continuous_mode_keeps_failed_cycle_visible_and_continues(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    clock = FakeClock("2026-03-23T10:00:00+00:00")
    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=DiscoveryFactorySequence(db_path),
        state_refresh_service_factory=StateFactory(db_path),
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )

    reports = runtime.run_continuous(
        RadarRuntimeOptions(
            page_limit=1,
            max_leaf_categories=1,
            root_scope="women",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=2,
        ),
        interval_seconds=0.1,
        max_cycles=2,
        continue_on_error=True,
    )

    assert len(reports) == 2
    assert reports[0].status == "failed"
    assert reports[0].phase == "discovery"
    assert "discovery exploded" in str(reports[0].last_error)
    assert reports[1].status == "completed"

    with RadarRepository(db_path) as repository:
        status = repository.runtime_status(limit=5, now=clock.iso())

    assert status["status"] == "idle"
    assert status["totals"]["failed_cycles"] == 1
    assert status["totals"]["completed_cycles"] == 1
    assert status["latest_failure"] is not None
    assert status["latest_failure"]["phase"] == "discovery"
    assert "discovery exploded" in str(status["latest_failure"]["last_error"])



def test_runtime_service_continuous_mode_observes_pause_and_resume_between_cycles(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    clock = FakeClock("2026-03-23T11:00:00+00:00")
    resume_requested = {"value": False}

    def sleep(seconds: float) -> None:
        with RadarRepository(db_path) as repository:
            controller = repository.runtime_controller_state(now=clock.iso()) or {}
            if controller.get("status") == "paused" and not resume_requested["value"]:
                repository.request_runtime_resume(requested_at=clock.iso())
                resume_requested["value"] = True
        clock.sleep(seconds)

    runtime = RadarRuntimeService(
        db_path,
        discovery_service_factory=lambda **kwargs: PersistingDiscoveryService(db_path),
        state_refresh_service_factory=lambda **kwargs: FakeStateRefreshService(db_path),
        sleep_fn=sleep,
        now_fn=clock.now,
    )

    callback_count = {"value": 0}

    def on_cycle_complete(report) -> None:
        callback_count["value"] += 1
        if callback_count["value"] == 1:
            with RadarRepository(db_path) as repository:
                repository.request_runtime_pause(requested_at=clock.iso())

    reports = runtime.run_continuous(
        RadarRuntimeOptions(
            page_limit=1,
            max_leaf_categories=1,
            root_scope="women",
            request_delay=0.0,
            timeout_seconds=5.0,
            state_refresh_limit=2,
        ),
        interval_seconds=5.0,
        max_cycles=2,
        continue_on_error=True,
        on_cycle_complete=on_cycle_complete,
    )

    assert len(reports) == 2
    assert reports[0].status == "completed"
    assert reports[1].status == "completed"
    assert resume_requested["value"] is True

    with RadarRepository(db_path) as repository:
        status = repository.runtime_status(limit=5, now=clock.iso())

    assert status["status"] == "idle"
    assert status["controller"] is not None
    assert status["controller"]["latest_cycle_id"] == reports[-1].cycle_id
