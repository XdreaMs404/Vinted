from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from vinted_radar.domain.events import build_listing_observed_event
from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry
from vinted_radar.models import ListingCard
from vinted_radar.platform.outbox import PostgresOutbox


class FakeQueryResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


@dataclass
class _OutboxRow:
    outbox_id: int
    event_id: str
    sink: str
    status: str
    available_at: str
    claimed_at: str | None
    claimed_by: str | None
    attempt_count: int
    delivered_at: str | None
    last_error: str | None
    locked_until: str | None
    manifest_id: str | None


class FakePostgresConnection:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.manifests: dict[str, dict[str, Any]] = {}
        self.outbox: dict[tuple[str, str], _OutboxRow] = {}
        self.executed_sql: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self._next_outbox_id = 1

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> FakeQueryResult:
        normalized = " ".join(sql.split())
        self.executed_sql.append(normalized)
        if normalized.startswith("INSERT INTO platform_events"):
            assert params is not None
            event_id = str(params[0])
            if event_id in self.events:
                return FakeQueryResult()
            self.events[event_id] = {
                "event_id": event_id,
                "schema_version": int(params[1]),
                "event_type": str(params[2]),
                "aggregate_type": str(params[3]),
                "aggregate_id": str(params[4]),
                "occurred_at": str(params[5]),
                "producer": str(params[6]),
                "partition_key": str(params[7]),
                "payload_json": str(params[8]),
                "metadata_json": str(params[9]),
                "payload_checksum": str(params[10]),
            }
            return FakeQueryResult([{"event_id": event_id}])
        if normalized.startswith("INSERT INTO platform_evidence_manifests"):
            assert params is not None
            manifest_id = str(params[0])
            if manifest_id in self.manifests:
                return FakeQueryResult()
            self.manifests[manifest_id] = {
                "manifest_id": manifest_id,
                "event_id": str(params[1]),
                "schema_version": int(params[2]),
                "manifest_type": str(params[3]),
                "generated_at": str(params[4]),
                "bucket": str(params[5]),
                "entries_json": str(params[6]),
                "metadata_json": str(params[7]),
                "checksum_algorithm": str(params[8]),
                "checksum": str(params[9]),
            }
            return FakeQueryResult([{"manifest_id": manifest_id}])
        if normalized.startswith("INSERT INTO platform_outbox"):
            assert params is not None
            event_id = str(params[0])
            sink = str(params[1])
            key = (event_id, sink)
            if key in self.outbox:
                return FakeQueryResult()
            row = _OutboxRow(
                outbox_id=self._next_outbox_id,
                event_id=event_id,
                sink=sink,
                status="pending",
                available_at=str(params[2]),
                claimed_at=None,
                claimed_by=None,
                attempt_count=0,
                delivered_at=None,
                last_error=None,
                locked_until=None,
                manifest_id=None if params[3] is None else str(params[3]),
            )
            self._next_outbox_id += 1
            self.outbox[key] = row
            return FakeQueryResult([{"outbox_id": row.outbox_id}])
        if normalized.startswith("WITH claimable AS"):
            assert params is not None
            sink = str(params[0])
            claim_time = str(params[1])
            limit = int(params[3])
            consumer_id = str(params[5])
            locked_until = str(params[6])
            rows: list[dict[str, Any]] = []
            claimable = [
                row
                for row in sorted(self.outbox.values(), key=lambda item: (item.available_at, item.outbox_id))
                if row.sink == sink
                and row.delivered_at is None
                and row.available_at <= claim_time
                and (
                    row.status in {"pending", "failed"}
                    or (row.status == "processing" and row.locked_until is not None and row.locked_until <= claim_time)
                )
            ][:limit]
            for row in claimable:
                row.status = "processing"
                row.claimed_at = claim_time
                row.claimed_by = consumer_id
                row.locked_until = locked_until
                row.attempt_count += 1
                event = self.events[row.event_id]
                rows.append(
                    {
                        "outbox_id": row.outbox_id,
                        "event_id": row.event_id,
                        "sink": row.sink,
                        "status": row.status,
                        "available_at": row.available_at,
                        "claimed_at": row.claimed_at,
                        "claimed_by": row.claimed_by,
                        "attempt_count": row.attempt_count,
                        "delivered_at": row.delivered_at,
                        "last_error": row.last_error,
                        "locked_until": row.locked_until,
                        "manifest_id": row.manifest_id,
                        "schema_version": event["schema_version"],
                        "event_type": event["event_type"],
                        "aggregate_type": event["aggregate_type"],
                        "aggregate_id": event["aggregate_id"],
                        "occurred_at": event["occurred_at"],
                        "producer": event["producer"],
                        "partition_key": event["partition_key"],
                        "payload_json": event["payload_json"],
                        "metadata_json": event["metadata_json"],
                        "payload_checksum": event["payload_checksum"],
                    }
                )
            return FakeQueryResult(rows)
        if normalized.startswith("UPDATE platform_outbox SET status = 'delivered'"):
            assert params is not None
            delivered_at = str(params[0])
            key = (str(params[1]), str(params[2]))
            row = self.outbox.get(key)
            if row is None:
                return FakeQueryResult()
            row.status = "delivered"
            row.delivered_at = delivered_at
            row.locked_until = None
            row.claimed_at = None
            row.claimed_by = None
            row.last_error = None
            return FakeQueryResult([{"outbox_id": row.outbox_id}])
        if normalized.startswith("UPDATE platform_outbox SET status = 'failed'"):
            assert params is not None
            error = str(params[0])
            retry_at = str(params[1])
            key = (str(params[2]), str(params[3]))
            row = self.outbox.get(key)
            if row is None:
                return FakeQueryResult()
            row.status = "failed"
            row.last_error = error
            row.available_at = retry_at
            row.locked_until = None
            row.claimed_at = None
            row.claimed_by = None
            return FakeQueryResult([{"outbox_id": row.outbox_id}])
        if normalized.startswith("SELECT manifest_id, event_id, schema_version"):
            assert params is not None
            manifest = self.manifests.get(str(params[0]))
            return FakeQueryResult([] if manifest is None else [manifest])
        raise AssertionError(f"Unexpected SQL: {normalized}")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _sample_listing() -> ListingCard:
    return ListingCard(
        listing_id=901,
        source_url="https://www.vinted.fr/items/901-robe?referrer=catalog",
        canonical_url="https://www.vinted.fr/items/901-robe",
        title="Robe",
        brand="Sézane",
        size_label="S",
        condition_label="Très bon état",
        price_amount_cents=9900,
        price_currency="€",
        total_price_amount_cents=10450,
        total_price_currency="€",
        image_url="https://images1.vinted.net/t/robe.webp",
        favourite_count=17,
        view_count=223,
        user_id=41,
        user_login="alice",
        user_profile_url="https://www.vinted.fr/member/41",
        created_at_ts=1711092000,
        source_catalog_id=2001,
        source_root_catalog_id=1904,
        raw_card={"id": 901, "title": "Robe"},
    )


def _sample_event_and_manifest() -> tuple[Any, EvidenceManifest]:
    event = build_listing_observed_event(
        _sample_listing(),
        run_id="run-20260328-a",
        observed_at="2026-03-28T18:30:00+00:00",
        source_page_number=1,
        card_position=2,
    )
    event_entry = EvidenceManifestEntry.from_bytes(
        logical_name="event-envelope",
        object_key=event.object_key("tenant-a/events/raw"),
        data=event.to_json().encode("utf-8"),
        content_type="application/json",
    )
    manifest = EvidenceManifest.from_event(
        event,
        bucket="vinted-radar",
        entries=[event_entry],
        metadata={"projection": "clickhouse"},
    )
    return event, manifest


def test_publish_is_idempotent_per_event_and_sink() -> None:
    connection = FakePostgresConnection()
    outbox = PostgresOutbox(connection)
    event, manifest = _sample_event_and_manifest()

    first = outbox.publish(event, sinks=["clickhouse", "parquet", "clickhouse"], manifest=manifest)
    second = outbox.publish(event, sinks=["clickhouse", "parquet"], manifest=manifest)

    assert first.event_created is True
    assert first.manifest_created is True
    assert first.delivery_rows_created == 2
    assert first.delivery_rows_existing == 0
    assert second.event_created is False
    assert second.manifest_created is False
    assert second.delivery_rows_created == 0
    assert second.delivery_rows_existing == 2
    assert set(connection.outbox) == {(event.event_id, "clickhouse"), (event.event_id, "parquet")}
    restored = outbox.fetch_manifest(manifest.manifest_id)
    assert restored == manifest


def test_claim_fail_retry_and_deliver_flow_stays_idempotent() -> None:
    connection = FakePostgresConnection()
    outbox = PostgresOutbox(connection)
    event, manifest = _sample_event_and_manifest()
    outbox.publish(event, sinks=["clickhouse"], manifest=manifest)

    claimed = outbox.claim_batch(
        "clickhouse",
        consumer_id="worker-a",
        limit=10,
        lease_seconds=30,
        now="2026-03-28T18:30:00+00:00",
    )

    assert len(claimed) == 1
    assert claimed[0].event.event_id == event.event_id
    assert claimed[0].attempt_count == 1
    assert claimed[0].manifest_id == manifest.manifest_id

    failed = outbox.mark_failed(
        event_id=event.event_id,
        sink="clickhouse",
        error="temporary ClickHouse timeout",
        failed_at="2026-03-28T18:30:10+00:00",
        retry_at="2026-03-28T18:31:00+00:00",
    )
    too_early = outbox.claim_batch(
        "clickhouse",
        consumer_id="worker-b",
        now="2026-03-28T18:30:30+00:00",
    )
    retried = outbox.claim_batch(
        "clickhouse",
        consumer_id="worker-b",
        now="2026-03-28T18:31:05+00:00",
    )
    delivered = outbox.mark_delivered(
        event_id=event.event_id,
        sink="clickhouse",
        delivered_at="2026-03-28T18:31:10+00:00",
    )
    after_delivery = outbox.claim_batch(
        "clickhouse",
        consumer_id="worker-c",
        now="2026-03-28T18:31:20+00:00",
    )

    assert failed is True
    assert too_early == ()
    assert len(retried) == 1
    assert retried[0].attempt_count == 2
    assert retried[0].last_error == "temporary ClickHouse timeout"
    assert delivered is True
    assert after_delivery == ()
    stored = connection.outbox[(event.event_id, "clickhouse")]
    assert stored.status == "delivered"
    assert stored.delivered_at == "2026-03-28T18:31:10+00:00"
