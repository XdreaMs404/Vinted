from __future__ import annotations

import json
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from vinted_radar.card_payload import build_api_card_evidence
from vinted_radar.domain.events import EventEnvelope
from vinted_radar.domain.manifests import EvidenceManifest
from vinted_radar.platform.lake_writer import PARQUET_CONTENT_TYPE, ParquetLakeWriter
from vinted_radar.platform.object_store import S3ObjectStore


class FakeS3Error(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.put_calls = 0

    def head_bucket(self, *, Bucket: str) -> None:
        if Bucket not in self.buckets:
            raise FakeS3Error("404")

    def create_bucket(self, *, Bucket: str, CreateBucketConfiguration: dict[str, object] | None = None) -> None:
        self.buckets.add(Bucket)

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        record = self.objects.get((Bucket, Key))
        if record is None:
            raise FakeS3Error("NoSuchKey")
        return {
            "ContentType": record["ContentType"],
            "ContentLength": len(record["Body"]),
            "Metadata": dict(record["Metadata"]),
            "ETag": record["ETag"],
        }

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        Metadata: dict[str, str],
    ) -> dict[str, str]:
        self.put_calls += 1
        etag = f"etag-{self.put_calls}"
        self.objects[(Bucket, Key)] = {
            "Body": Body,
            "ContentType": ContentType,
            "Metadata": dict(Metadata),
            "ETag": etag,
        }
        return {"ETag": etag}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        record = self.objects.get((Bucket, Key))
        if record is None:
            raise FakeS3Error("NoSuchKey")
        return {
            "Body": FakeBody(record["Body"]),
            "ContentType": record["ContentType"],
            "ContentLength": len(record["Body"]),
            "Metadata": dict(record["Metadata"]),
            "ETag": record["ETag"],
        }

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)



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
            "capture": {"page_number": 1, "card_position": 1},
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
            "capture": {"page_number": 1, "card_position": 2},
        },
    ]



def test_lake_writer_writes_deterministic_manifested_parquet_batches() -> None:
    client = FakeS3Client()
    store = S3ObjectStore(client, bucket="vinted-radar-test")
    assert store.ensure_bucket() is True

    writer = ParquetLakeWriter(
        store,
        raw_events_prefix="tenant-a/events/raw",
        manifests_prefix="tenant-a/manifests",
        parquet_prefix="tenant-a/parquet",
    )
    batch_event = _sample_batch_event()
    rows = _sample_rows()

    first = writer.write_batch(
        batch_event=batch_event,
        rows=rows,
        manifest_metadata={"projection": "lake-writer-test"},
    )
    second = writer.write_batch(
        batch_event=batch_event,
        rows=rows,
        manifest_metadata={"projection": "lake-writer-test"},
    )

    assert client.put_calls == 3
    assert first.event_object.key == batch_event.object_key("tenant-a/events/raw")
    assert first.parquet_object.key == (
        f"tenant-a/parquet/v1/event_type=vinted-discovery-listing-seen-batch/"
        f"occurred_on=2026-03-28/{batch_event.event_id}.parquet"
    )
    assert first.manifest_object.key == first.manifest.object_key("tenant-a/manifests")
    assert first.parquet_object.content_type == PARQUET_CONTENT_TYPE
    assert first.parquet_object.checksum == second.parquet_object.checksum
    assert first.manifest.manifest_id == second.manifest.manifest_id
    assert first.partition == {
        "event_type": "vinted-discovery-listing-seen-batch",
        "occurred_on": "2026-03-28",
        "schema_version": "v1",
    }

    stored_manifest = EvidenceManifest.from_json(store.get_text(first.manifest_object.key))
    assert stored_manifest == first.manifest
    assert [entry.logical_name for entry in stored_manifest.entries] == ["batch-event", "parquet-batch"]
    assert stored_manifest.metadata["projection"] == "lake-writer-test"
    assert stored_manifest.metadata["row_count"] == 2

    round_trip_rows = writer.read_rows(first.parquet_object.key)
    assert [row["listing_id"] for row in round_trip_rows] == [901, 902]
    assert round_trip_rows[0]["batch_event_id"] == batch_event.event_id
    assert round_trip_rows[0]["row_index"] == 0
    assert json.loads(str(round_trip_rows[0]["raw_card"]))["evidence_source"] == "api"
    assert json.loads(str(round_trip_rows[1]["capture"])) == {"card_position": 2, "page_number": 1}

    parquet_bytes = store.get_bytes(first.parquet_object.key).data
    parquet_file = pq.ParquetFile(pa.BufferReader(parquet_bytes))
    assert parquet_file.metadata.num_rows == 2
    assert parquet_file.metadata.row_group(0).column(0).compression == "ZSTD"
    assert parquet_file.schema_arrow.metadata[b"parquet_schema_version"] == b"1"
    assert parquet_file.schema_arrow.metadata[b"parquet_compression"] == b"zstd"



def test_object_store_rejects_reusing_a_key_for_different_bytes() -> None:
    client = FakeS3Client()
    store = S3ObjectStore(client, bucket="vinted-radar-test")
    store.ensure_bucket()

    store.put_text(key="tenant-a/manifests/example.json", text="first")

    with pytest.raises(ValueError, match="already exists with checksum"):
        store.put_text(key="tenant-a/manifests/example.json", text="second")



def test_lake_writer_round_trips_against_minio(
    data_platform_stack,
    object_storage_client_factory,
) -> None:
    client = object_storage_client_factory()
    close = getattr(client, "close", None)
    try:
        writer = ParquetLakeWriter.from_config(data_platform_stack.config, client=client)
        assert writer.object_store.ensure_bucket() is True

        batch_event = _sample_batch_event()
        rows = _sample_rows()
        result = writer.write_batch(
            batch_event=batch_event,
            rows=rows,
            manifest_metadata={"projection": "minio-integration"},
        )

        restored_event = EventEnvelope.from_json(writer.object_store.get_text(result.event_object.key))
        restored_manifest = EvidenceManifest.from_json(writer.object_store.get_text(result.manifest_object.key))
        restored_rows = writer.read_rows(result.parquet_object.key)

        assert restored_event == batch_event
        assert restored_manifest == result.manifest
        assert [row["listing_id"] for row in restored_rows] == [901, 902]
        assert restored_manifest.entries[1].checksum == result.parquet_object.checksum
        assert writer.object_store.head(result.parquet_object.key).checksum == result.parquet_object.checksum
        assert result.manifest.metadata["projection"] == "minio-integration"
    finally:
        if callable(close):
            close()
