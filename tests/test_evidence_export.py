from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tests.platform_test_fakes import FakeS3Client
from vinted_radar.card_payload import build_api_card_evidence
from vinted_radar.cli import app
from vinted_radar.db import connect_database
from vinted_radar.platform.config import OBJECT_STORE_BUCKET_ENV, OBJECT_STORE_PREFIX_ENV, load_platform_config
from vinted_radar.platform.lake_writer import ParquetLakeWriter
from vinted_radar.platform.object_store import S3ObjectStore
from vinted_radar.repository import RadarRepository
from vinted_radar.services.evidence_export import HistoricalEvidenceExporter
from vinted_radar.services.evidence_lookup import EvidenceLookupService


class ListableFakeS3Client(FakeS3Client):
    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str,
        ContinuationToken: str | None = None,
    ) -> dict[str, object]:
        keys = sorted(
            key
            for bucket, key in self.objects.keys()
            if bucket == Bucket and key.startswith(Prefix)
        )
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }



def _seed_legacy_evidence_db(db_path: Path) -> dict[str, object]:
    connection = connect_database(db_path)
    legacy_raw_card = {
        "title": "Robe noire",
        "brand_title": "Sézane",
        "size_title": "S",
        "status": "Très bon état",
        "status_id": 3,
        "price": {"amount": "99.00", "currency_code": "EUR"},
        "total_item_price": {"amount": "104.50", "currency_code": "EUR"},
    }
    minimal_raw_card = build_api_card_evidence(
        {
            "title": "Jean brut",
            "brand_title": "A.P.C.",
            "size_title": "M",
            "status": "Bon état",
            "status_id": 4,
            "price": {"amount": "85.00", "currency_code": "EUR"},
            "total_item_price": {"amount": "90.20", "currency_code": "EUR"},
        }
    )
    probe_id = "probe-20260328T200500-a1b2c3d4"

    with connection:
        connection.execute(
            """
            INSERT INTO discovery_runs (
                run_id, started_at, finished_at, status, root_scope, page_limit,
                max_leaf_categories, request_delay_seconds,
                total_seed_catalogs, total_leaf_catalogs, scanned_leaf_catalogs,
                successful_scans, failed_scans, raw_listing_hits, unique_listing_hits, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-legacy-001",
                "2026-03-28T19:40:00+00:00",
                "2026-03-28T19:46:00+00:00",
                "completed",
                "women",
                1,
                1,
                0.0,
                1,
                1,
                1,
                1,
                0,
                2,
                2,
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO catalogs (
                catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code,
                url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1904,
                1904,
                "Femmes",
                None,
                "Femmes",
                "women",
                "https://www.vinted.fr/catalog",
                "Femmes",
                0,
                0,
                1,
                0,
                "2026-03-28T19:39:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO catalogs (
                catalog_id, root_catalog_id, root_title, parent_catalog_id, title, code,
                url, path, depth, is_leaf, allow_browsing_subcategories, order_index, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2001,
                1904,
                "Femmes",
                1904,
                "Robes",
                "dresses",
                "https://www.vinted.fr/catalog?catalog[]=2001",
                "Femmes > Robes",
                1,
                1,
                0,
                1,
                "2026-03-28T19:39:00+00:00",
            ),
        )

        listings = [
            (
                9001,
                "https://www.vinted.fr/items/9001-robe-noire",
                "https://www.vinted.fr/items/9001-robe-noire?foo=bar",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "https://images.example/9001.webp",
                None,
                None,
                None,
                None,
                None,
                None,
                2001,
                1904,
                "2026-03-28T19:45:00+00:00",
                "2026-03-28T19:45:00+00:00",
                "run-legacy-001",
                json.dumps(legacy_raw_card, ensure_ascii=False, sort_keys=True),
            ),
            (
                9002,
                "https://www.vinted.fr/items/9002-jean-brut",
                "https://www.vinted.fr/items/9002-jean-brut?foo=bar",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "https://images.example/9002.webp",
                None,
                None,
                None,
                None,
                None,
                None,
                2001,
                1904,
                "2026-03-28T19:45:05+00:00",
                "2026-03-28T19:45:05+00:00",
                "run-legacy-001",
                json.dumps(minimal_raw_card, ensure_ascii=False, sort_keys=True),
            ),
        ]
        connection.executemany(
            """
            INSERT INTO listings (
                listing_id, canonical_url, source_url, title, brand, size_label, condition_label,
                price_amount_cents, price_currency, total_price_amount_cents, total_price_currency,
                image_url, favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts,
                primary_catalog_id, primary_root_catalog_id,
                first_discovered_at, last_discovered_at, last_seen_run_id, last_card_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            listings,
        )

        connection.executemany(
            """
            INSERT INTO listing_discoveries (
                run_id, listing_id, observed_at, source_catalog_id, source_page_number,
                source_url, card_position, raw_card_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "run-legacy-001",
                    9001,
                    "2026-03-28T19:45:00+00:00",
                    2001,
                    1,
                    "https://www.vinted.fr/items/9001-robe-noire?foo=bar",
                    1,
                    json.dumps(legacy_raw_card, ensure_ascii=False, sort_keys=True),
                ),
                (
                    "run-legacy-001",
                    9002,
                    "2026-03-28T19:45:05+00:00",
                    2001,
                    1,
                    "https://www.vinted.fr/items/9002-jean-brut?foo=bar",
                    2,
                    json.dumps(minimal_raw_card, ensure_ascii=False, sort_keys=True),
                ),
            ],
        )

        connection.executemany(
            """
            INSERT INTO listing_observations (
                run_id, listing_id, observed_at, canonical_url, source_url,
                source_catalog_id, source_page_number, first_card_position, sighting_count,
                title, brand, size_label, condition_label,
                price_amount_cents, price_currency, total_price_amount_cents, total_price_currency,
                image_url, raw_card_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "run-legacy-001",
                    9001,
                    "2026-03-28T19:45:00+00:00",
                    "https://www.vinted.fr/items/9001-robe-noire",
                    "https://www.vinted.fr/items/9001-robe-noire?foo=bar",
                    2001,
                    1,
                    1,
                    2,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "https://images.example/9001.webp",
                    json.dumps(legacy_raw_card, ensure_ascii=False, sort_keys=True),
                ),
                (
                    "run-legacy-001",
                    9002,
                    "2026-03-28T19:45:05+00:00",
                    "https://www.vinted.fr/items/9002-jean-brut",
                    "https://www.vinted.fr/items/9002-jean-brut?foo=bar",
                    2001,
                    1,
                    2,
                    1,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "https://images.example/9002.webp",
                    json.dumps(minimal_raw_card, ensure_ascii=False, sort_keys=True),
                ),
            ],
        )

        connection.execute(
            """
            INSERT INTO item_page_probes (
                probe_id, listing_id, probed_at, requested_url, final_url,
                response_status, probe_outcome, detail_json, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                probe_id,
                9001,
                "2026-03-28T20:05:00+00:00",
                "https://www.vinted.fr/items/9001-robe-noire",
                "https://www.vinted.fr/items/9001-robe-noire",
                403,
                "unknown",
                json.dumps(
                    {
                        "reason": "anti_bot_challenge",
                        "html_excerpt": "<title>Just a moment...</title>",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "Challenge page returned instead of item detail.",
            ),
        )

    connection.close()
    return {
        "legacy_raw_card": legacy_raw_card,
        "minimal_raw_card": minimal_raw_card,
        "probe_id": probe_id,
    }



def test_historical_evidence_export_writes_discovery_observation_and_probe_batches(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    _seed_legacy_evidence_db(db_path)

    client = ListableFakeS3Client()
    object_store = S3ObjectStore(client, bucket="vinted-radar-test")
    object_store.ensure_bucket()
    writer = ParquetLakeWriter(
        object_store,
        raw_events_prefix="tenant-a/events/raw",
        manifests_prefix="tenant-a/manifests",
        parquet_prefix="tenant-a/parquet",
    )
    exporter = HistoricalEvidenceExporter(
        RadarRepository(db_path),
        writer,
    )

    try:
        report = exporter.export()
    finally:
        exporter.close()

    assert report.total_batches == 3
    assert report.total_rows == 5
    assert report.batch_counts == {"discoveries": 1, "observations": 1, "probes": 1}
    assert report.row_counts == {"discoveries": 2, "observations": 2, "probes": 1}

    discovery_batch = next(batch for batch in report.batches if batch.dataset == "discoveries")
    observation_batch = next(batch for batch in report.batches if batch.dataset == "observations")
    probe_batch = next(batch for batch in report.batches if batch.dataset == "probes")

    discovery_rows = writer.read_rows(discovery_batch.parquet_object_key)
    observation_rows = writer.read_rows(observation_batch.parquet_object_key)
    probe_rows = writer.read_rows(probe_batch.parquet_object_key)

    discovery_by_listing = {int(row["listing_id"]): row for row in discovery_rows}
    observation_by_listing = {int(row["listing_id"]): row for row in observation_rows}

    assert discovery_by_listing[9001]["title"] == "Robe noire"
    assert json.loads(str(discovery_by_listing[9001]["raw_card"]))["brand_title"] == "Sézane"
    assert json.loads(str(discovery_by_listing[9002]["raw_card"]))["evidence_source"] == "api"

    assert observation_by_listing[9001]["sighting_count"] == 2
    assert observation_by_listing[9001]["price_amount_cents"] == 9900
    assert observation_by_listing[9002]["condition_label"] == "Bon état"

    assert probe_rows[0]["probe_id"] == "probe-20260328T200500-a1b2c3d4"
    assert json.loads(str(probe_rows[0]["detail"]))["reason"] == "anti_bot_challenge"



def test_evidence_lookup_service_resolves_manifest_reference_to_decoded_probe_fragment(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    seeded = _seed_legacy_evidence_db(db_path)

    client = ListableFakeS3Client()
    object_store = S3ObjectStore(client, bucket="vinted-radar-test")
    object_store.ensure_bucket()
    writer = ParquetLakeWriter(
        object_store,
        raw_events_prefix="tenant-a/events/raw",
        manifests_prefix="tenant-a/manifests",
        parquet_prefix="tenant-a/parquet",
    )
    exporter = HistoricalEvidenceExporter(
        RadarRepository(db_path),
        writer,
    )

    try:
        report = exporter.export()
    finally:
        exporter.close()

    probe_batch = next(batch for batch in report.batches if batch.dataset == "probes")
    lookup = EvidenceLookupService(
        object_store,
        raw_events_prefix="tenant-a/events/raw",
        manifests_prefix="tenant-a/manifests",
    )

    result = lookup.inspect(
        manifest_id=probe_batch.manifest_id,
        probe_id=str(seeded["probe_id"]),
        field_path="row.detail.reason",
    )

    assert result.event.event_type == "vinted.backfill.probe.batch"
    assert result.fragment_root == "row"
    assert result.fragment == "anti_bot_challenge"
    assert result.matched_row is not None
    assert result.matched_row["probe_id"] == seeded["probe_id"]



def test_evidence_export_and_inspect_cli_round_trip(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    _seed_legacy_evidence_db(db_path)

    client = ListableFakeS3Client()
    config = load_platform_config(
        env={
            OBJECT_STORE_BUCKET_ENV: "vinted-radar-test",
            OBJECT_STORE_PREFIX_ENV: "tenant-a",
        }
    )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: config)
    monkeypatch.setattr("vinted_radar.platform.object_store.create_s3_client", lambda _config: client)

    runner = CliRunner()
    export_result = runner.invoke(app, ["evidence-export", "--db", str(db_path), "--format", "json"])

    assert export_result.exit_code == 0, export_result.stderr
    export_payload = json.loads(export_result.stdout)
    assert export_payload["batch_counts"] == {"discoveries": 1, "observations": 1, "probes": 1}

    discovery_batch = next(batch for batch in export_payload["batches"] if batch["dataset"] == "discoveries")
    inspect_result = runner.invoke(
        app,
        [
            "evidence-inspect",
            "--event-id",
            discovery_batch["event_id"],
            "--listing-id",
            "9001",
            "--field-path",
            "row.raw_card.price.amount",
            "--format",
            "json",
        ],
    )

    assert inspect_result.exit_code == 0, inspect_result.stderr
    inspect_payload = json.loads(inspect_result.stdout)
    assert inspect_payload["fragment"] == "99.00"
    assert inspect_payload["matched_row"]["listing_id"] == 9001
    assert inspect_payload["event"]["event_type"] == "vinted.backfill.discovery.batch"
