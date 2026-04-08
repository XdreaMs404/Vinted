from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.models import CatalogNode, ListingCard
from vinted_radar.repository import RadarRepository
from vinted_radar.services.postgres_backfill import PostgresBackfillReport, backfill_postgres_mutable_truth


class SpyMutableTruthRepository:
    def __init__(self) -> None:
        self.discovery_runs: dict[str, dict[str, object]] = {}
        self.catalogs: dict[int, dict[str, object]] = {}
        self.listing_identities: dict[int, dict[str, object]] = {}
        self.listing_presence_summaries: dict[int, dict[str, object]] = {}
        self.listing_current_states: dict[int, dict[str, object]] = {}
        self.refresh_calls: list[tuple[int, str, str | None, str | None]] = []
        self.runtime_cycles: list[tuple[dict[str, object], str | None]] = []
        self.runtime_controllers: list[tuple[dict[str, object], str | None]] = []
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def _upsert_discovery_run(self, payload: dict[str, object]) -> None:
        self.discovery_runs[str(payload["run_id"])] = dict(payload)

    def _upsert_catalog(self, payload: dict[str, object]) -> None:
        self.catalogs[int(payload["catalog_id"])] = dict(payload)

    def _upsert_listing_identity(self, payload: dict[str, object]) -> None:
        self.listing_identities[int(payload["listing_id"])] = dict(payload)

    def _upsert_listing_presence_summary(self, payload: dict[str, object]) -> None:
        self.listing_presence_summaries[int(payload["listing_id"])] = dict(payload)

    def _default_listing_current_state(self, listing_id: int) -> dict[str, object]:
        return {
            "listing_id": listing_id,
            "state_code": "unknown",
            "state_label": "Inconnu",
            "basis_kind": "unknown",
            "confidence_label": "low",
            "confidence_score": 0.0,
            "sold_like": False,
            "seen_in_latest_primary_scan": False,
            "latest_primary_scan_run_id": None,
            "latest_primary_scan_at": None,
            "follow_up_miss_count": 0,
            "latest_follow_up_miss_at": None,
            "latest_probe_at": None,
            "latest_probe_response_status": None,
            "latest_probe_outcome": None,
            "latest_probe_error_message": None,
            "last_seen_age_hours": 0.0,
            "state_explanation_json": "{}",
            "last_event_id": None,
            "last_manifest_id": None,
            "projected_at": "2026-03-20T10:00:00+00:00",
        }

    def _upsert_listing_current_state_row(self, payload: dict[str, object]) -> None:
        self.listing_current_states[int(payload["listing_id"])] = dict(payload)

    def _refresh_projected_listing(
        self,
        listing_id: int,
        *,
        now: str,
        source_event_id: str | None,
        source_manifest_id: str | None,
    ) -> None:
        self.refresh_calls.append((listing_id, now, source_event_id, source_manifest_id))

    def project_runtime_cycle_snapshot(self, *, cycle: dict[str, object], event_id: str | None) -> None:
        self.runtime_cycles.append((dict(cycle), event_id))

    def project_runtime_controller_snapshot(self, *, controller: dict[str, object], event_id: str | None) -> None:
        self.runtime_controllers.append((dict(controller), event_id))


def _seed_source_db(db_path: Path) -> tuple[str, str]:
    with RadarRepository(db_path) as repository:
        run_id = repository.start_run(
            root_scope="women",
            page_limit=1,
            max_leaf_categories=1,
            request_delay_seconds=0.0,
        )
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
        repository.upsert_catalogs([root_catalog, leaf_catalog], synced_at="2026-03-20T10:00:00+00:00")
        repository.update_run_catalog_totals(run_id, total_seed_catalogs=2, total_leaf_catalogs=1)
        repository.record_catalog_scan(
            run_id=run_id,
            catalog_id=2001,
            page_number=1,
            requested_url=leaf_catalog.url,
            fetched_at="2026-03-20T10:05:00+00:00",
            response_status=200,
            success=True,
            listing_count=1,
            pagination_total_pages=1,
            next_page_url=None,
            error_message=None,
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
        repository.upsert_listing(
            listing,
            discovered_at="2026-03-20T10:05:00+00:00",
            primary_catalog_id=2001,
            primary_root_catalog_id=1904,
            run_id=run_id,
        )
        repository.record_listing_observation(
            run_id=run_id,
            listing=listing,
            observed_at="2026-03-20T10:05:00+00:00",
            source_catalog_id=2001,
            source_page_number=1,
            card_position=1,
        )
        repository.record_item_page_probe(
            listing_id=9001,
            probed_at="2026-03-20T10:08:00+00:00",
            requested_url=listing.canonical_url,
            final_url=listing.canonical_url,
            response_status=200,
            probe_outcome="active",
            detail={"reason": "buy_signal_open"},
            error_message=None,
        )
        repository.complete_run(
            run_id,
            status="completed",
            scanned_leaf_catalogs=1,
            successful_scans=1,
            failed_scans=0,
            raw_listing_hits=1,
            unique_listing_hits=1,
        )
        cycle_id = repository.start_runtime_cycle(
            mode="batch",
            phase="starting",
            interval_seconds=None,
            state_probe_limit=3,
            config={"state_refresh_limit": 3},
        )
        repository.complete_runtime_cycle(
            cycle_id,
            status="completed",
            phase="completed",
            discovery_run_id=run_id,
            state_probed_count=1,
            tracked_listings=1,
            freshness_counts={
                "first-pass-only": 1,
                "fresh-followup": 0,
                "aging-followup": 0,
                "stale-followup": 0,
            },
            last_error=None,
            state_refresh_summary={"status": "healthy", "direct_signal_count": 1},
        )
    return run_id, cycle_id


def test_backfill_postgres_mutable_truth_projects_sqlite_rows_into_mutable_truth(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    run_id, cycle_id = _seed_source_db(db_path)
    target = SpyMutableTruthRepository()
    fake_config = SimpleNamespace(postgres=SimpleNamespace(dsn="postgresql://user:secret@db.example/vinted_radar"))

    report = backfill_postgres_mutable_truth(
        db_path,
        repository=target,
        config=fake_config,
        reference_now="2026-03-21T00:00:00+00:00",
    )

    assert report.discovery_runs == 1
    assert report.catalogs == 2
    assert report.listing_identities == 1
    assert report.listing_presence_summaries == 1
    assert report.listing_current_states == 1
    assert report.runtime_cycles == 1
    assert report.runtime_controller_rows == 1
    assert report.as_dict()["postgres_dsn"] == "postgresql://***@db.example/vinted_radar"

    assert target.discovery_runs[run_id]["status"] == "completed"
    assert target.discovery_runs[run_id]["last_event_id"] is None
    assert target.catalogs[2001]["last_run_id"] == run_id
    assert target.catalogs[2001]["last_event_id"] is None
    assert target.listing_identities[9001]["canonical_url"] == "https://www.vinted.fr/items/9001-runtime"
    assert target.listing_identities[9001]["last_event_id"] is None
    assert target.listing_presence_summaries[9001]["freshness_bucket"] == "first-pass-only"
    assert target.listing_presence_summaries[9001]["last_event_id"] is None
    assert target.listing_current_states[9001]["latest_probe_outcome"] == "active"
    assert target.listing_current_states[9001]["last_event_id"] is None
    assert target.runtime_cycles[0][0]["cycle_id"] == cycle_id
    assert target.runtime_cycles[0][0]["status"] == "completed"
    assert target.runtime_cycles[0][1] is None
    assert target.runtime_controllers[0][0]["status"] == "idle"
    assert target.runtime_controllers[0][1] is None
    assert target.refresh_calls == [
        (
            9001,
            "2026-03-21T00:00:00+00:00",
            target.listing_current_states[9001]["last_event_id"],
            None,
        )
    ]
    assert target.closed is False


def test_backfill_postgres_mutable_truth_can_skip_runtime_control_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_source_db(db_path)
    target = SpyMutableTruthRepository()
    fake_config = SimpleNamespace(postgres=SimpleNamespace(dsn="postgresql://user:secret@db.example/vinted_radar"))

    report = backfill_postgres_mutable_truth(
        db_path,
        repository=target,
        config=fake_config,
        reference_now="2026-03-21T00:00:00+00:00",
        sync_runtime_control=False,
    )

    assert report.runtime_cycles == 0
    assert report.runtime_controller_rows == 0
    assert target.runtime_cycles == []
    assert target.runtime_controllers == []


def test_postgres_backfill_cli_renders_json_and_forwards_options(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    fake_config = SimpleNamespace(postgres=SimpleNamespace(dsn="postgresql://user:secret@db.example/vinted_radar"))

    def fake_backfill(
        sqlite_db_path: Path,
        *,
        config: object,
        reference_now: str | None,
        sync_runtime_control: bool,
    ) -> PostgresBackfillReport:
        captured["sqlite_db_path"] = sqlite_db_path
        captured["config"] = config
        captured["reference_now"] = reference_now
        captured["sync_runtime_control"] = sync_runtime_control
        return PostgresBackfillReport(
            sqlite_db_path=str(sqlite_db_path),
            postgres_dsn="postgresql://user:secret@db.example/vinted_radar",
            reference_now=reference_now or "2026-03-21T00:00:00+00:00",
            discovery_runs=4,
            catalogs=5,
            listing_identities=6,
            listing_presence_summaries=6,
            listing_current_states=6,
            runtime_cycles=0,
            runtime_controller_rows=0,
        )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: fake_config)
    monkeypatch.setattr("vinted_radar.cli.backfill_postgres_mutable_truth", fake_backfill)
    runner = CliRunner()

    db_path = tmp_path / "source.db"
    result = runner.invoke(
        app,
        [
            "postgres-backfill",
            "--db",
            str(db_path),
            "--skip-runtime-control",
            "--now",
            "2026-03-21T00:00:00+00:00",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sqlite_db_path"] == str(db_path)
    assert payload["postgres_dsn"] == "postgresql://***@db.example/vinted_radar"
    assert payload["runtime_cycles"] == 0
    assert payload["runtime_controller_rows"] == 0
    assert captured["sqlite_db_path"] == db_path
    assert captured["config"] is fake_config
    assert captured["reference_now"] == "2026-03-21T00:00:00+00:00"
    assert captured["sync_runtime_control"] is False
