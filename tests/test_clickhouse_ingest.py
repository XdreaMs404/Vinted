from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from tests.platform_test_fakes import FakePostgresConnection
from vinted_radar.cli import app
from vinted_radar.domain.events import EventEnvelope, deterministic_uuid
from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry
from vinted_radar.platform.clickhouse_ingest import (
    CLICKHOUSE_INGEST_CONSUMER,
    ClickHouseIngestReport,
    ClickHouseIngestService,
    ClickHouseIngestStatusSnapshot,
    ClickHouseIngestedRecord,
)
from vinted_radar.platform.outbox import PostgresOutbox


class FakeLakeWriter:
    def __init__(self, rows_by_key: dict[str, list[dict[str, object]]]) -> None:
        self.rows_by_key = rows_by_key

    def read_rows(self, key: str) -> list[dict[str, object]]:
        return [dict(row) for row in self.rows_by_key[key]]


class FakeClickHouseResult:
    def __init__(self, rows: list[list[object]] | None = None) -> None:
        self.result_rows = rows or []


class RecordingClickHouseClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {}
        self.insert_calls: list[dict[str, object]] = []
        self.fail_table: str | None = None

    def query(self, sql: str) -> FakeClickHouseResult:
        match = re.search(r"FROM\s+[A-Za-z0-9_]+\.([A-Za-z0-9_]+)\s+WHERE\s+source_event_id\s*=\s*'([^']+)'", sql)
        if match is None:
            return FakeClickHouseResult([])
        table, source_event_id = match.group(1), match.group(2)
        rows = [
            [row["event_id"]]
            for row in self.tables.get(table, [])
            if row.get("source_event_id") == source_event_id
        ]
        return FakeClickHouseResult(rows)

    def insert(self, *, table: str, data, column_names, database: str | None = None) -> None:
        if self.fail_table == table:
            raise RuntimeError("clickhouse unavailable")
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


class RecordingCheckpointRepository:
    def __init__(self) -> None:
        self.checkpoints: dict[tuple[str, str], dict[str, object]] = {}

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


class ConstantNow:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def _sample_listing_seen_batch() -> tuple[EventEnvelope, EvidenceManifest, str, list[dict[str, object]]]:
    event = EventEnvelope.create(
        schema_version=1,
        event_type="vinted.discovery.listing-seen.batch",
        aggregate_type="discovery-run",
        aggregate_id="run-20260331-a",
        occurred_at="2026-03-31T06:00:00+00:00",
        producer="vinted_radar.services.discovery",
        partition_key="1904",
        payload={"run_id": "run-20260331-a", "row_count": 2, "catalog_id": 2001},
        metadata={"capture_source": "api_catalog_page", "root_title": "Homme"},
    )
    parquet_key = f"tenant-a/parquet/{event.event_id}.parquet"
    manifest = EvidenceManifest.from_event(
        event,
        bucket="vinted-radar",
        entries=[
            EvidenceManifestEntry.from_bytes(
                logical_name="parquet-batch",
                object_key=parquet_key,
                data=b"parquet-batch",
                content_type="application/vnd.apache.parquet",
            )
        ],
        metadata={"row_count": 2},
    )
    rows = [
        {
            "batch_event_id": event.event_id,
            "batch_event_type": event.event_type,
            "batch_event_schema_version": 1,
            "batch_event_occurred_at": event.occurred_at,
            "batch_event_occurred_on": "2026-03-31",
            "batch_event_partition_key": event.partition_key,
            "batch_event_producer": event.producer,
            "row_index": 0,
            "run_id": "run-20260331-a",
            "observed_at": "2026-03-31T06:00:00+00:00",
            "catalog_id": 2001,
            "root_catalog_id": 1904,
            "root_title": "Homme",
            "catalog_title": "Vestes",
            "catalog_path": "Homme > Vestes",
            "page_number": 1,
            "card_position": 1,
            "listing_id": 901,
            "canonical_url": "https://www.vinted.fr/items/901-veste",
            "source_url": "https://www.vinted.fr/items/901-veste?ref=cat",
            "title": "Veste laine",
            "brand": "Sézane",
            "size_label": "M",
            "condition_label": "Très bon état",
            "price_amount_cents": 9900,
            "price_currency": "EUR",
            "total_price_amount_cents": 10450,
            "total_price_currency": "EUR",
            "image_url": "https://images.vinted.net/901.webp",
            "raw_card": {"title": "Veste laine", "evidence_source": "api"},
        },
        {
            "batch_event_id": event.event_id,
            "batch_event_type": event.event_type,
            "batch_event_schema_version": 1,
            "batch_event_occurred_at": event.occurred_at,
            "batch_event_occurred_on": "2026-03-31",
            "batch_event_partition_key": event.partition_key,
            "batch_event_producer": event.producer,
            "row_index": 1,
            "run_id": "run-20260331-a",
            "observed_at": "2026-03-31T06:00:00+00:00",
            "catalog_id": 2001,
            "root_catalog_id": 1904,
            "root_title": "Homme",
            "catalog_title": "Vestes",
            "catalog_path": "Homme > Vestes",
            "page_number": 1,
            "card_position": 2,
            "listing_id": 902,
            "canonical_url": "https://www.vinted.fr/items/902-manteau",
            "source_url": "https://www.vinted.fr/items/902-manteau?ref=cat",
            "title": "Manteau droit",
            "brand": "A.P.C.",
            "size_label": "L",
            "condition_label": "Bon état",
            "price_amount_cents": 12500,
            "price_currency": "EUR",
            "total_price_amount_cents": 13100,
            "total_price_currency": "EUR",
            "image_url": "https://images.vinted.net/902.webp",
            "raw_card": {"title": "Manteau droit", "evidence_source": "api"},
        },
    ]
    return event, manifest, parquet_key, rows


def _sample_probe_batch() -> tuple[EventEnvelope, EvidenceManifest, str, list[dict[str, object]]]:
    event = EventEnvelope.create(
        schema_version=1,
        event_type="vinted.state-refresh.probe.batch",
        aggregate_type="state-refresh",
        aggregate_id="all",
        occurred_at="2026-03-31T07:00:00+00:00",
        producer="vinted_radar.services.state_refresh",
        partition_key="901",
        payload={"reference_now": "2026-03-31T07:00:00+00:00", "row_count": 1, "probed_listing_ids": [901]},
        metadata={"capture_source": "item_page_probe", "mode": "bulk"},
    )
    parquet_key = f"tenant-a/parquet/{event.event_id}.parquet"
    manifest = EvidenceManifest.from_event(
        event,
        bucket="vinted-radar",
        entries=[
            EvidenceManifestEntry.from_bytes(
                logical_name="parquet-batch",
                object_key=parquet_key,
                data=b"probe-batch",
                content_type="application/vnd.apache.parquet",
            )
        ],
        metadata={"row_count": 1},
    )
    rows = [
        {
            "batch_event_id": event.event_id,
            "batch_event_type": event.event_type,
            "batch_event_schema_version": 1,
            "batch_event_occurred_at": event.occurred_at,
            "batch_event_partition_key": event.partition_key,
            "batch_event_producer": event.producer,
            "row_index": 0,
            "reference_now": "2026-03-31T07:00:00+00:00",
            "targeted_listing_id": None,
            "listing_id": 901,
            "probed_at": "2026-03-31T07:00:00+00:00",
            "requested_url": "https://www.vinted.fr/items/901-veste",
            "final_url": "https://www.vinted.fr/items/901-veste",
            "probe_outcome": "active",
            "response_status": 200,
            "reason": "buy_signal_open",
            "detail": {"reason": "buy_signal_open", "can_buy": True, "is_closed": False},
            "error_message": None,
        }
    ]
    return event, manifest, parquet_key, rows


def _service_for(*, event: EventEnvelope, manifest: EvidenceManifest, parquet_key: str, rows: list[dict[str, object]], now: str = "2026-03-31T08:00:00+00:00"):
    connection = FakePostgresConnection()
    outbox = PostgresOutbox(connection)
    outbox.publish(event, sinks=["clickhouse"], manifest=manifest)
    repository = RecordingCheckpointRepository()
    client = RecordingClickHouseClient()
    service = ClickHouseIngestService(
        repository=repository,
        outbox=outbox,
        lake_writer=FakeLakeWriter({parquet_key: rows}),
        clickhouse_client=client,
        database="vinted_radar",
        now_provider=ConstantNow(now),
    )
    return service, repository, connection, client


def test_clickhouse_ingest_projects_listing_seen_batches_and_updates_checkpoint() -> None:
    event, manifest, parquet_key, rows = _sample_listing_seen_batch()
    service, repository, connection, client = _service_for(
        event=event,
        manifest=manifest,
        parquet_key=parquet_key,
        rows=rows,
    )

    report = service.ingest_available(now="2026-03-31T08:00:00+00:00")

    assert report.claimed_count == 1
    assert report.processed_count == 1
    assert report.skipped_count == 0
    inserted_rows = client.tables["fact_listing_seen_events"]
    assert len(inserted_rows) == 2
    assert inserted_rows[0]["source_event_id"] == event.event_id
    assert inserted_rows[0]["listing_id"] == 901
    assert inserted_rows[0]["primary_catalog_id"] == 2001
    assert json.loads(str(inserted_rows[0]["raw_card_json"]))["evidence_source"] == "api"
    assert json.loads(str(inserted_rows[0]["metadata_json"]))["capture_source"] == "api_catalog_page"
    assert connection.outbox[(event.event_id, "clickhouse")].status == "delivered"

    checkpoint = repository.outbox_checkpoint(consumer_name=CLICKHOUSE_INGEST_CONSUMER, sink="clickhouse")
    assert checkpoint is not None
    assert checkpoint["status"] == "lagging"
    assert checkpoint["last_event_id"] == event.event_id
    assert checkpoint["metadata"]["row_count"] == 2
    assert checkpoint["metadata"]["inserted_row_count"] == 2


def test_clickhouse_ingest_projects_probe_batches_with_nullable_dimensions() -> None:
    event, manifest, parquet_key, rows = _sample_probe_batch()
    service, repository, connection, client = _service_for(
        event=event,
        manifest=manifest,
        parquet_key=parquet_key,
        rows=rows,
    )

    report = service.ingest_available(now="2026-03-31T08:05:00+00:00")

    assert report.processed_count == 1
    inserted = client.tables["fact_listing_probe_events"]
    assert len(inserted) == 1
    assert inserted[0]["listing_id"] == 901
    assert inserted[0]["probe_outcome"] == "active"
    assert inserted[0]["primary_catalog_id"] is None
    assert json.loads(str(inserted[0]["detail_json"]))["reason"] == "buy_signal_open"
    assert connection.outbox[(event.event_id, "clickhouse")].status == "delivered"
    checkpoint = repository.outbox_checkpoint(consumer_name=CLICKHOUSE_INGEST_CONSUMER, sink="clickhouse")
    assert checkpoint is not None
    assert checkpoint["metadata"]["target_table"] == "fact_listing_probe_events"


def test_clickhouse_ingest_only_inserts_missing_rows_on_replay() -> None:
    event, manifest, parquet_key, rows = _sample_listing_seen_batch()
    service, repository, connection, client = _service_for(
        event=event,
        manifest=manifest,
        parquet_key=parquet_key,
        rows=rows,
    )
    first_row_event_id = deterministic_uuid(
        "clickhouse.fact-listing-seen",
        {
            "source_event_id": event.event_id,
            "manifest_id": manifest.manifest_id,
            "row_index": 0,
            "listing_id": 901,
            "observed_at": "2026-03-31T06:00:00+00:00",
        },
    )
    client.tables["fact_listing_seen_events"] = [
        {"event_id": first_row_event_id, "source_event_id": event.event_id}
    ]

    report = service.ingest_available(now="2026-03-31T08:10:00+00:00")

    assert report.processed_count == 1
    assert report.records[0].inserted_row_count == 1
    assert report.records[0].existing_row_count == 1
    assert len(client.tables["fact_listing_seen_events"]) == 2
    assert client.insert_calls[-1]["row_count"] == 1
    assert connection.outbox[(event.event_id, "clickhouse")].status == "delivered"
    checkpoint = repository.outbox_checkpoint(consumer_name=CLICKHOUSE_INGEST_CONSUMER, sink="clickhouse")
    assert checkpoint is not None
    assert checkpoint["metadata"]["existing_row_count"] == 1


def test_clickhouse_ingest_marks_failure_and_exposes_checkpoint_error_state() -> None:
    event, manifest, parquet_key, rows = _sample_listing_seen_batch()
    service, repository, connection, client = _service_for(
        event=event,
        manifest=manifest,
        parquet_key=parquet_key,
        rows=rows,
        now="2026-03-31T08:20:00+00:00",
    )
    client.fail_table = "fact_listing_seen_events"

    with pytest.raises(RuntimeError, match="clickhouse unavailable"):
        service.ingest_available(now="2026-03-31T08:20:00+00:00")

    stored = connection.outbox[(event.event_id, "clickhouse")]
    assert stored.status == "failed"
    assert stored.available_at == "2026-03-31T08:20:30+00:00"
    snapshot = service.current_status()
    assert snapshot.status == "failed"
    assert snapshot.last_event_id == event.event_id
    assert snapshot.last_error == "RuntimeError: clickhouse unavailable"
    assert snapshot.metadata["retry_at"] == "2026-03-31T08:20:30+00:00"
    checkpoint = repository.outbox_checkpoint(consumer_name=CLICKHOUSE_INGEST_CONSUMER, sink="clickhouse")
    assert checkpoint is not None
    assert checkpoint["status"] == "failed"


def test_clickhouse_ingest_cli_renders_worker_report(monkeypatch) -> None:
    class FakeService:
        def __init__(self) -> None:
            self.closed = False

        def ingest_available(self, *, limit: int, lease_seconds: int, consumer_name: str | None = None):
            assert limit == 100
            assert lease_seconds == 60
            assert consumer_name == CLICKHOUSE_INGEST_CONSUMER
            return ClickHouseIngestReport(
                consumer_name=CLICKHOUSE_INGEST_CONSUMER,
                sink="clickhouse",
                claimed_count=1,
                processed_count=1,
                skipped_count=0,
                records=(
                    ClickHouseIngestedRecord(
                        source_event_id="evt-1",
                        event_type="vinted.discovery.listing-seen.batch",
                        manifest_id="manifest-1",
                        row_count=2,
                        inserted_row_count=2,
                        existing_row_count=0,
                        target_table="fact_listing_seen_events",
                        projection_status="projected",
                    ),
                ),
            )

        def close(self) -> None:
            self.closed = True

    fake_service = FakeService()
    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        "vinted_radar.cli.ClickHouseIngestService",
        SimpleNamespace(from_environment=lambda **kwargs: fake_service),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["clickhouse-ingest"])

    assert result.exit_code == 0
    assert "ClickHouse ingest consumer: clickhouse-serving-ingest" in result.stdout
    assert "Claimed rows: 1" in result.stdout
    assert "fact_listing_seen_events" in result.stdout
    assert fake_service.closed is True


def test_clickhouse_ingest_status_cli_emits_json_checkpoint() -> None:
    runner = CliRunner()
    snapshot = ClickHouseIngestStatusSnapshot(
        consumer_name=CLICKHOUSE_INGEST_CONSUMER,
        sink="clickhouse",
        checkpoint_exists=True,
        status="lagging",
        updated_at="2026-03-31T08:30:00+00:00",
        last_outbox_id=42,
        last_event_id="evt-42",
        last_manifest_id="manifest-42",
        last_claimed_at="2026-03-31T08:29:00+00:00",
        last_delivered_at="2026-03-31T08:29:30+00:00",
        lag_seconds=610.0,
        last_error=None,
        metadata={"target_table": "fact_listing_seen_events", "row_count": 2},
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: SimpleNamespace())
        monkeypatch.setattr("vinted_radar.cli.load_clickhouse_ingest_status", lambda **kwargs: snapshot)
        result = runner.invoke(app, ["clickhouse-ingest-status", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "lagging"
    assert payload["last_outbox_id"] == 42
    assert payload["metadata"]["target_table"] == "fact_listing_seen_events"
