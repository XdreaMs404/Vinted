from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from tests.platform_test_fakes import FakePostgresConnection, FakeS3Client
from vinted_radar.cli import app
from vinted_radar.domain.events import EventEnvelope
from vinted_radar.domain.manifests import EvidenceManifest
from vinted_radar.models import CatalogNode, ListingCard
from vinted_radar.platform.clickhouse_ingest import ClickHouseIngestService
from vinted_radar.platform.config import OBJECT_STORE_BUCKET_ENV, OBJECT_STORE_PREFIX_ENV, load_platform_config
from vinted_radar.platform.lake_writer import ParquetLakeWriter
from vinted_radar.platform.object_store import S3ObjectStore
from vinted_radar.platform.outbox import PostgresOutbox
from vinted_radar.services.full_backfill import FullBackfillReport, run_full_backfill
from vinted_radar.services.postgres_backfill import PostgresBackfillReport
from vinted_radar.repository import RadarRepository


class SpyMutableTruthRepository:
    def __init__(self) -> None:
        self.discovery_runs: dict[str, dict[str, object]] = {}
        self.catalogs: dict[int, dict[str, object]] = {}
        self.listing_identities: dict[int, dict[str, object]] = {}
        self.listing_presence_summaries: dict[int, dict[str, object]] = {}
        self.listing_current_states: dict[int, dict[str, object]] = {}
        self.refresh_calls: list[tuple[int, str, str | None, str | None]] = []
        self.runtime_cycles: list[tuple[dict[str, object], str]] = []
        self.runtime_controllers: list[tuple[dict[str, object], str]] = []
        self.checkpoints: dict[tuple[str, str], dict[str, object]] = {}

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

    def project_runtime_cycle_snapshot(self, *, cycle: dict[str, object], event_id: str) -> None:
        self.runtime_cycles.append((dict(cycle), event_id))

    def project_runtime_controller_snapshot(self, *, controller: dict[str, object], event_id: str) -> None:
        self.runtime_controllers.append((dict(controller), event_id))

    def update_outbox_checkpoint(
        self,
        *,
        consumer_name: str,
        sink: str,
        last_outbox_id: int | None,
        last_event_id: str | None,
        last_manifest_id: str | None,
        last_claimed_at: str | None,
        last_delivered_at: str | None,
        status: str,
        lag_seconds: float | None,
        last_error: str | None,
        metadata: dict[str, object] | None = None,
        updated_at: str | None = None,
    ) -> None:
        self.checkpoints[(consumer_name, sink)] = {
            "consumer_name": consumer_name,
            "sink": sink,
            "last_outbox_id": last_outbox_id,
            "last_event_id": last_event_id,
            "last_manifest_id": last_manifest_id,
            "last_claimed_at": last_claimed_at,
            "last_delivered_at": last_delivered_at,
            "status": status,
            "lag_seconds": lag_seconds,
            "last_error": last_error,
            "metadata": dict(metadata or {}),
            "updated_at": updated_at,
        }

    def outbox_checkpoint(self, *, consumer_name: str, sink: str) -> dict[str, object] | None:
        checkpoint = self.checkpoints.get((consumer_name, sink))
        return None if checkpoint is None else dict(checkpoint)


class RecordingClickHouseClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {}
        self.insert_calls: list[dict[str, object]] = []

    def query(self, sql: str):
        match = re.search(r"FROM\s+[A-Za-z0-9_]+\.([A-Za-z0-9_]+)\s+WHERE\s+source_event_id\s*=\s*'([^']+)'", sql)
        rows: list[list[object]] = []
        if match is not None:
            table, source_event_id = match.group(1), match.group(2)
            rows = [
                [row["event_id"]]
                for row in self.tables.get(table, [])
                if row.get("source_event_id") == source_event_id
            ]
        return SimpleNamespace(result_rows=rows)

    def insert(self, *, table: str, data, column_names, database: str | None = None) -> None:
        rows = [dict(zip(column_names, row, strict=False)) for row in data]
        self.tables.setdefault(table, []).extend(rows)
        self.insert_calls.append(
            {
                "table": table,
                "database": database,
                "column_names": list(column_names),
                "row_count": len(rows),
            }
        )


class ConstantNow:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def _build_config() -> object:
    return load_platform_config(
        env={
            OBJECT_STORE_BUCKET_ENV: "vinted-radar-test",
            OBJECT_STORE_PREFIX_ENV: "tenant-a",
        }
    )


def _build_writer(client: FakeS3Client) -> ParquetLakeWriter:
    object_store = S3ObjectStore(client, bucket="vinted-radar-test")
    object_store.ensure_bucket()
    return ParquetLakeWriter(
        object_store,
        raw_events_prefix="tenant-a/events/raw",
        manifests_prefix="tenant-a/manifests",
        parquet_prefix="tenant-a/parquet",
    )


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
            listing_count=2,
            pagination_total_pages=1,
            next_page_url=None,
            error_message=None,
        )
        listing_a = ListingCard(
            listing_id=9001,
            source_url="https://www.vinted.fr/items/9001-runtime?ref=catalog",
            canonical_url="https://www.vinted.fr/items/9001-runtime",
            title="Runtime robe",
            brand="Zara",
            size_label="M",
            condition_label="Très bon état",
            price_amount_cents=1500,
            price_currency="EUR",
            total_price_amount_cents=1650,
            total_price_currency="EUR",
            image_url="https://images/9001.webp",
            favourite_count=5,
            view_count=21,
            user_id=41,
            user_login="alice",
            user_profile_url="https://www.vinted.fr/member/41",
            created_at_ts=1710928800,
            source_catalog_id=2001,
            source_root_catalog_id=1904,
            raw_card={"overlay_title": "Runtime robe", "brand_title": "Zara"},
        )
        listing_b = ListingCard(
            listing_id=9002,
            source_url="https://www.vinted.fr/items/9002-coat?ref=catalog",
            canonical_url="https://www.vinted.fr/items/9002-coat",
            title="Coat noir",
            brand="Sézane",
            size_label="L",
            condition_label="Bon état",
            price_amount_cents=2400,
            price_currency="EUR",
            total_price_amount_cents=2600,
            total_price_currency="EUR",
            image_url="https://images/9002.webp",
            favourite_count=8,
            view_count=34,
            user_id=42,
            user_login="bob",
            user_profile_url="https://www.vinted.fr/member/42",
            created_at_ts=1710929900,
            source_catalog_id=2001,
            source_root_catalog_id=1904,
            raw_card={"overlay_title": "Coat noir", "brand_title": "Sézane"},
        )
        for card_position, listing, observed_at in (
            (1, listing_a, "2026-03-20T10:05:00+00:00"),
            (2, listing_b, "2026-03-20T10:05:05+00:00"),
        ):
            repository.upsert_listing(
                listing,
                discovered_at=observed_at,
                primary_catalog_id=2001,
                primary_root_catalog_id=1904,
                run_id=run_id,
            )
            repository.record_listing_discovery(
                run_id=run_id,
                listing=listing,
                observed_at=observed_at,
                source_catalog_id=2001,
                source_page_number=1,
                card_position=card_position,
            )
            repository.record_listing_observation(
                run_id=run_id,
                listing=listing,
                observed_at=observed_at,
                source_catalog_id=2001,
                source_page_number=1,
                card_position=card_position,
            )
        repository.record_item_page_probe(
            listing_id=9001,
            probed_at="2026-03-20T10:08:00+00:00",
            requested_url=listing_a.canonical_url,
            final_url=listing_a.canonical_url,
            response_status=200,
            probe_outcome="active",
            detail={"reason": "buy_signal_open", "can_buy": True},
            error_message=None,
        )
        repository.complete_run(
            run_id,
            status="completed",
            scanned_leaf_catalogs=1,
            successful_scans=1,
            failed_scans=0,
            raw_listing_hits=2,
            unique_listing_hits=2,
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
            tracked_listings=2,
            freshness_counts={
                "first-pass-only": 2,
                "fresh-followup": 0,
                "aging-followup": 0,
                "stale-followup": 0,
            },
            state_refresh_summary={"status": "healthy", "direct_signal_count": 1},
        )
    return run_id, cycle_id


def test_full_backfill_pipeline_projects_postgres_writes_manifests_and_ingests_clickhouse(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    run_id, cycle_id = _seed_source_db(db_path)
    config = _build_config()
    repository = SpyMutableTruthRepository()
    postgres_connection = FakePostgresConnection()
    outbox = PostgresOutbox(postgres_connection)
    s3_client = FakeS3Client()
    writer = _build_writer(s3_client)
    clickhouse_client = RecordingClickHouseClient()
    clickhouse_ingest = ClickHouseIngestService(
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_client=clickhouse_client,
        database=config.clickhouse.database,
        now_provider=ConstantNow("2026-03-20T10:09:00+00:00"),
    )
    checkpoint_path = tmp_path / "full-backfill-checkpoint.json"

    report = run_full_backfill(
        db_path,
        config=config,
        reference_now="2026-03-21T00:00:00+00:00",
        batch_size=1,
        checkpoint_path=checkpoint_path,
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_ingest=clickhouse_ingest,
    )

    assert report.dry_run is False
    assert report.resumed_from_checkpoint is False
    assert report.checkpoint_completed is True
    assert report.postgres_backfill.discovery_runs == 1
    assert report.postgres_backfill.catalogs == 2
    assert report.postgres_backfill.listing_identities == 2
    assert report.postgres_backfill.runtime_cycles == 1
    assert report.postgres_backfill.runtime_controller_rows == 1
    assert report.clickhouse_claimed_count == 3
    assert report.clickhouse_processed_count == 3
    assert report.clickhouse_skipped_count == 0

    dataset_by_name = {dataset.dataset: dataset for dataset in report.datasets}
    assert dataset_by_name["discoveries"].completed_batches == 2
    assert dataset_by_name["discoveries"].completed_rows == 2
    assert dataset_by_name["observations"].completed_batches == 2
    assert dataset_by_name["observations"].completed_rows == 2
    assert dataset_by_name["probes"].completed_batches == 1
    assert dataset_by_name["runtime-cycles"].completed_batches == 1
    assert dataset_by_name["runtime-controller"].completed_batches == 1

    assert repository.discovery_runs[run_id]["status"] == "completed"
    assert repository.catalogs[2001]["last_run_id"] == run_id
    assert repository.listing_current_states[9001]["latest_probe_outcome"] == "active"
    assert repository.runtime_cycles[0][0]["cycle_id"] == cycle_id
    assert repository.runtime_controllers[0][0]["status"] == "idle"

    assert set(clickhouse_client.tables) == {"fact_listing_seen_events", "fact_listing_probe_events"}
    assert len(clickhouse_client.tables["fact_listing_seen_events"]) == 2
    assert len(clickhouse_client.tables["fact_listing_probe_events"]) == 1
    assert clickhouse_client.tables["fact_listing_probe_events"][0]["probe_outcome"] == "active"

    raw_event_payloads = [
        EventEnvelope.from_json(record["Body"].decode("utf-8"))
        for (bucket, key), record in s3_client.objects.items()
        if bucket == "vinted-radar-test" and key.startswith("tenant-a/events/raw/") and key.endswith(".json")
    ]
    manifest_payloads = [
        EvidenceManifest.from_json(record["Body"].decode("utf-8"))
        for (bucket, key), record in s3_client.objects.items()
        if bucket == "vinted-radar-test" and key.startswith("tenant-a/manifests/") and key.endswith(".json")
    ]

    event_types = sorted(event.event_type for event in raw_event_payloads)
    assert event_types == [
        "vinted.backfill.observation.batch",
        "vinted.backfill.observation.batch",
        "vinted.backfill.runtime-controller.batch",
        "vinted.backfill.runtime-cycle.batch",
        "vinted.discovery.listing-seen.batch",
        "vinted.discovery.listing-seen.batch",
        "vinted.state-refresh.probe.batch",
    ]
    assert len(manifest_payloads) == 7
    assert all(manifest.metadata["capture_source"] == "sqlite_backfill" for manifest in manifest_payloads)

    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload["completed"] is True
    assert checkpoint_payload["datasets"]["discoveries"]["completed_batches"] == 2
    assert checkpoint_payload["clickhouse"]["processed_count"] == 3



def test_full_backfill_dry_run_inspects_without_writing_targets_or_checkpoint(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_source_db(db_path)
    config = _build_config()
    repository = SpyMutableTruthRepository()
    postgres_connection = FakePostgresConnection()
    outbox = PostgresOutbox(postgres_connection)
    s3_client = FakeS3Client()
    writer = _build_writer(s3_client)
    clickhouse_client = RecordingClickHouseClient()
    clickhouse_ingest = ClickHouseIngestService(
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_client=clickhouse_client,
        database=config.clickhouse.database,
        now_provider=ConstantNow("2026-03-20T10:09:00+00:00"),
    )
    checkpoint_path = tmp_path / "full-backfill-checkpoint.json"

    report = run_full_backfill(
        db_path,
        config=config,
        reference_now="2026-03-21T00:00:00+00:00",
        batch_size=1,
        dry_run=True,
        checkpoint_path=checkpoint_path,
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_ingest=clickhouse_ingest,
    )

    assert report.dry_run is True
    assert report.postgres_backfill.listing_current_states == 2
    assert repository.discovery_runs == {}
    assert repository.catalogs == {}
    assert repository.listing_current_states == {}
    assert postgres_connection.outbox == {}
    assert clickhouse_client.insert_calls == []
    assert [key for bucket, key in s3_client.objects if bucket == "vinted-radar-test" and key.endswith(".json")] == []
    assert checkpoint_path.exists() is False



def test_full_backfill_resume_skips_completed_postgres_stage_and_prior_batches(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_source_db(db_path)
    config = _build_config()
    repository = SpyMutableTruthRepository()
    postgres_connection = FakePostgresConnection()
    outbox = PostgresOutbox(postgres_connection)
    s3_client = FakeS3Client()
    writer = _build_writer(s3_client)
    clickhouse_client = RecordingClickHouseClient()
    clickhouse_ingest = ClickHouseIngestService(
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_client=clickhouse_client,
        database=config.clickhouse.database,
        now_provider=ConstantNow("2026-03-20T10:09:00+00:00"),
    )
    checkpoint_path = tmp_path / "resume-checkpoint.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "version": 1,
                "sqlite_db_path": str(db_path),
                "reference_now": "2026-03-21T00:00:00+00:00",
                "sync_runtime_control": True,
                "updated_at": "2026-03-21T00:00:00+00:00",
                "completed": False,
                "postgres_backfill": {
                    "completed": True,
                    "report": PostgresBackfillReport(
                        sqlite_db_path=str(db_path),
                        postgres_dsn=config.postgres.dsn,
                        reference_now="2026-03-21T00:00:00+00:00",
                        discovery_runs=1,
                        catalogs=2,
                        listing_identities=2,
                        listing_presence_summaries=2,
                        listing_current_states=2,
                        runtime_cycles=1,
                        runtime_controller_rows=1,
                    ).as_dict(),
                },
                "datasets": {
                    "discoveries": {
                        "completed_batches": 1,
                        "completed_rows": 1,
                        "last_group_key": "run_id=resume/catalog_id=2001/page_number=1/chunk=0",
                        "last_event_id": "event-a",
                        "last_manifest_id": "manifest-a",
                    }
                },
                "clickhouse": {
                    "claimed_count": 1,
                    "processed_count": 1,
                    "skipped_count": 0,
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report = run_full_backfill(
        db_path,
        config=config,
        batch_size=1,
        checkpoint_path=checkpoint_path,
        repository=repository,
        outbox=outbox,
        lake_writer=writer,
        clickhouse_ingest=clickhouse_ingest,
    )

    assert report.resumed_from_checkpoint is True
    assert repository.discovery_runs == {}
    assert repository.catalogs == {}
    dataset_by_name = {dataset.dataset: dataset for dataset in report.datasets}
    assert dataset_by_name["discoveries"].completed_batches == 2
    assert dataset_by_name["discoveries"].skipped_batches == 1
    assert report.clickhouse_claimed_count == 2
    assert report.clickhouse_processed_count == 2
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload["completed"] is True
    assert checkpoint_payload["datasets"]["discoveries"]["completed_batches"] == 2
    assert checkpoint_payload["clickhouse"]["processed_count"] == 3



def test_full_backfill_cli_renders_json_and_forwards_options(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    config = _build_config()

    def fake_run_full_backfill(
        sqlite_db_path: Path,
        *,
        config: object,
        reference_now: str | None,
        batch_size: int,
        dry_run: bool,
        sync_runtime_control: bool,
        checkpoint_path: Path,
        reset_checkpoint: bool,
        clickhouse_lease_seconds: int,
    ) -> FullBackfillReport:
        captured["sqlite_db_path"] = sqlite_db_path
        captured["config"] = config
        captured["reference_now"] = reference_now
        captured["batch_size"] = batch_size
        captured["dry_run"] = dry_run
        captured["sync_runtime_control"] = sync_runtime_control
        captured["checkpoint_path"] = checkpoint_path
        captured["reset_checkpoint"] = reset_checkpoint
        captured["clickhouse_lease_seconds"] = clickhouse_lease_seconds
        return FullBackfillReport(
            sqlite_db_path=str(sqlite_db_path),
            postgres_dsn=config.postgres.dsn,
            clickhouse_url=config.clickhouse.url,
            clickhouse_database=config.clickhouse.database,
            object_store_bucket=config.object_storage.bucket,
            reference_now=reference_now or "2026-03-21T00:00:00+00:00",
            dry_run=dry_run,
            resumed_from_checkpoint=False,
            checkpoint_path=str(checkpoint_path),
            checkpoint_completed=False,
            postgres_backfill=PostgresBackfillReport(
                sqlite_db_path=str(sqlite_db_path),
                postgres_dsn=config.postgres.dsn,
                reference_now=reference_now or "2026-03-21T00:00:00+00:00",
                discovery_runs=1,
                catalogs=2,
                listing_identities=2,
                listing_presence_summaries=2,
                listing_current_states=2,
                runtime_cycles=1,
                runtime_controller_rows=1,
            ),
            datasets=(),
            clickhouse_claimed_count=0,
            clickhouse_processed_count=0,
            clickhouse_skipped_count=0,
        )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: config)
    monkeypatch.setattr("vinted_radar.cli.run_full_backfill", fake_run_full_backfill)
    runner = CliRunner()

    db_path = tmp_path / "source.db"
    checkpoint_path = tmp_path / "resume.json"
    result = runner.invoke(
        app,
        [
            "full-backfill",
            "--db",
            str(db_path),
            "--batch-size",
            "250",
            "--dry-run",
            "--skip-runtime-control",
            "--now",
            "2026-03-21T00:00:00+00:00",
            "--checkpoint",
            str(checkpoint_path),
            "--reset-checkpoint",
            "--lease-seconds",
            "90",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["sqlite_db_path"] == str(db_path)
    assert payload["postgres_backfill"]["listing_current_states"] == 2
    assert captured["sqlite_db_path"] == db_path
    assert captured["config"] is config
    assert captured["reference_now"] == "2026-03-21T00:00:00+00:00"
    assert captured["batch_size"] == 250
    assert captured["dry_run"] is True
    assert captured["sync_runtime_control"] is False
    assert captured["checkpoint_path"] == checkpoint_path
    assert captured["reset_checkpoint"] is True
    assert captured["clickhouse_lease_seconds"] == 90
