from __future__ import annotations

import json
from typing import Any

from vinted_radar.card_payload import build_api_card_evidence
from vinted_radar.domain.events import EventEnvelope
from vinted_radar.domain.manifests import EvidenceManifest
from vinted_radar.platform.lake_writer import CollectorEvidencePublisher, ParquetLakeWriter
from vinted_radar.platform.object_store import S3ObjectStore
from vinted_radar.platform.outbox import PostgresOutbox

from tests.platform_test_fakes import FakePostgresConnection, FakeS3Client


def _sample_batch_event(*, row_count: int = 2) -> EventEnvelope:
    return EventEnvelope.create(
        schema_version=1,
        event_type="vinted.discovery.listing-seen.batch",
        aggregate_type="discovery-run",
        aggregate_id="run-20260328-a",
        occurred_at="2026-03-28T19:45:00+00:00",
        producer="vinted_radar.services.discovery",
        partition_key="1904",
        payload={
            "run_id": "run-20260328-a",
            "root_catalog_id": 1904,
            "row_count": row_count,
        },
        metadata={
            "capture_source": "api_catalog_page",
            "page_number": 1,
        },
        identity={
            "run_id": "run-20260328-a",
            "catalog_id": 2001,
            "page_number": 1,
            "observed_at": "2026-03-28T19:45:00+00:00",
        },
    )



def _sample_rows() -> list[dict[str, Any]]:
    return [
        {
            "listing_id": 901,
            "title": "Robe noire",
            "catalog_id": 2001,
            "card_position": 1,
            "raw_card": build_api_card_evidence(
                {
                    "title": "Robe noire",
                    "brand_title": "Sézane",
                    "size_title": "S",
                    "status": "Très bon état",
                    "status_id": 3,
                    "price": {"amount": "99.00", "currency_code": "EUR"},
                    "total_item_price": {"amount": "104.50", "currency_code": "EUR"},
                }
            ),
        },
        {
            "listing_id": 902,
            "title": "Jean brut",
            "catalog_id": 2002,
            "card_position": 2,
            "raw_card": build_api_card_evidence(
                {
                    "title": "Jean brut",
                    "brand_title": "A.P.C.",
                    "size_title": "M",
                    "status": "Bon état",
                    "status_id": 4,
                    "price": {"amount": "85.00", "currency_code": "EUR"},
                    "total_item_price": {"amount": "90.20", "currency_code": "EUR"},
                }
            ),
        },
    ]



def test_collector_evidence_publisher_writes_manifested_parquet_and_idempotent_outbox_rows() -> None:
    s3_client = FakeS3Client()
    object_store = S3ObjectStore(s3_client, bucket="vinted-radar-test")
    object_store.ensure_bucket()
    lake_writer = ParquetLakeWriter(
        object_store,
        raw_events_prefix="tenant-a/events/raw",
        manifests_prefix="tenant-a/manifests",
        parquet_prefix="tenant-a/parquet",
    )
    postgres_connection = FakePostgresConnection()
    publisher = CollectorEvidencePublisher(
        lake_writer=lake_writer,
        outbox=PostgresOutbox(postgres_connection),
        sinks=("clickhouse", "parquet", "clickhouse"),
    )

    batch_event = _sample_batch_event()
    rows = _sample_rows()

    first = publisher.emit_batch(
        batch_event=batch_event,
        rows=rows,
        manifest_type="listing-seen-evidence-batch",
        manifest_metadata={"projection": "collector-test"},
    )
    second = publisher.emit_batch(
        batch_event=batch_event,
        rows=rows,
        manifest_type="listing-seen-evidence-batch",
        manifest_metadata={"projection": "collector-test"},
    )

    assert first is not None
    assert second is not None
    assert first.lake_write is not None
    assert first.outbox_publish is not None
    assert second.outbox_publish is not None
    assert s3_client.put_calls == 3
    assert first.lake_write.manifest.manifest_id == second.lake_write.manifest.manifest_id
    assert first.outbox_publish.delivery_rows_created == 2
    assert first.outbox_publish.delivery_rows_existing == 0
    assert second.outbox_publish.delivery_rows_created == 0
    assert second.outbox_publish.delivery_rows_existing == 2
    assert set(postgres_connection.outbox) == {
        (batch_event.event_id, "clickhouse"),
        (batch_event.event_id, "parquet"),
    }

    manifest = EvidenceManifest.from_json(object_store.get_text(first.lake_write.manifest_object.key))
    assert manifest == first.lake_write.manifest
    assert manifest.metadata["projection"] == "collector-test"
    assert manifest.metadata["row_count"] == 2

    restored_rows = lake_writer.read_rows(first.lake_write.parquet_object.key)
    assert [row["listing_id"] for row in restored_rows] == [901, 902]
    assert restored_rows[0]["batch_event_type"] == "vinted.discovery.listing-seen.batch"
    assert json.loads(str(restored_rows[0]["raw_card"]))["evidence_source"] == "api"



def test_collector_evidence_publisher_returns_none_for_empty_batches() -> None:
    s3_client = FakeS3Client()
    object_store = S3ObjectStore(s3_client, bucket="vinted-radar-test")
    object_store.ensure_bucket()
    publisher = CollectorEvidencePublisher(
        lake_writer=ParquetLakeWriter(
            object_store,
            raw_events_prefix="tenant-a/events/raw",
            manifests_prefix="tenant-a/manifests",
            parquet_prefix="tenant-a/parquet",
        ),
        outbox=PostgresOutbox(FakePostgresConnection()),
        sinks=("parquet",),
    )

    result = publisher.emit_batch(batch_event=_sample_batch_event(row_count=0), rows=[])

    assert result is None
    assert s3_client.put_calls == 0
