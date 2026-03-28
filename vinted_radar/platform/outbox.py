from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from typing import Any

from vinted_radar.domain.events import EventEnvelope, canonical_json, ensure_json_object
from vinted_radar.domain.manifests import EvidenceManifest


@dataclass(frozen=True, slots=True)
class OutboxPublishResult:
    event_id: str
    sinks: tuple[str, ...]
    event_created: bool
    manifest_id: str | None
    manifest_created: bool
    delivery_rows_created: int
    delivery_rows_existing: int

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "sinks": list(self.sinks),
            "event_created": self.event_created,
            "manifest_id": self.manifest_id,
            "manifest_created": self.manifest_created,
            "delivery_rows_created": self.delivery_rows_created,
            "delivery_rows_existing": self.delivery_rows_existing,
        }


@dataclass(frozen=True, slots=True)
class ClaimedOutboxRecord:
    outbox_id: int
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
    event: EventEnvelope

    def as_dict(self) -> dict[str, object]:
        payload = self.event.as_dict()
        payload.update(
            {
                "outbox_id": self.outbox_id,
                "sink": self.sink,
                "status": self.status,
                "available_at": self.available_at,
                "claimed_at": self.claimed_at,
                "claimed_by": self.claimed_by,
                "attempt_count": self.attempt_count,
                "delivered_at": self.delivered_at,
                "last_error": self.last_error,
                "locked_until": self.locked_until,
                "manifest_id": self.manifest_id,
            }
        )
        return payload


_INSERT_EVENT_SQL = """
INSERT INTO platform_events (
    event_id,
    schema_version,
    event_type,
    aggregate_type,
    aggregate_id,
    occurred_at,
    producer,
    partition_key,
    payload_json,
    metadata_json,
    payload_checksum
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
ON CONFLICT (event_id) DO NOTHING
RETURNING event_id
"""

_INSERT_MANIFEST_SQL = """
INSERT INTO platform_evidence_manifests (
    manifest_id,
    event_id,
    schema_version,
    manifest_type,
    generated_at,
    bucket,
    entries_json,
    metadata_json,
    checksum_algorithm,
    checksum
) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
ON CONFLICT (manifest_id) DO NOTHING
RETURNING manifest_id
"""

_INSERT_OUTBOX_SQL = """
INSERT INTO platform_outbox (
    event_id,
    sink,
    status,
    available_at,
    manifest_id
) VALUES (%s, %s, 'pending', %s, %s)
ON CONFLICT (event_id, sink) DO NOTHING
RETURNING outbox_id
"""

_CLAIM_OUTBOX_SQL = """
WITH claimable AS (
    SELECT o.outbox_id
    FROM platform_outbox AS o
    WHERE o.sink = %s
      AND o.delivered_at IS NULL
      AND o.available_at <= %s
      AND (
        o.status IN ('pending', 'failed')
        OR (o.status = 'processing' AND o.locked_until IS NOT NULL AND o.locked_until <= %s)
      )
    ORDER BY o.available_at ASC, o.outbox_id ASC
    LIMIT %s
    FOR UPDATE SKIP LOCKED
),
updated AS (
    UPDATE platform_outbox AS o
    SET status = 'processing',
        claimed_at = %s,
        claimed_by = %s,
        locked_until = %s,
        attempt_count = o.attempt_count + 1,
        last_attempt_at = %s
    FROM claimable
    WHERE o.outbox_id = claimable.outbox_id
    RETURNING
        o.outbox_id,
        o.event_id,
        o.sink,
        o.status,
        o.available_at,
        o.claimed_at,
        o.claimed_by,
        o.attempt_count,
        o.delivered_at,
        o.last_error,
        o.locked_until,
        o.manifest_id
)
SELECT
    updated.outbox_id,
    updated.event_id,
    updated.sink,
    updated.status,
    updated.available_at,
    updated.claimed_at,
    updated.claimed_by,
    updated.attempt_count,
    updated.delivered_at,
    updated.last_error,
    updated.locked_until,
    updated.manifest_id,
    e.schema_version,
    e.event_type,
    e.aggregate_type,
    e.aggregate_id,
    e.occurred_at,
    e.producer,
    e.partition_key,
    e.payload_json::text,
    e.metadata_json::text,
    e.payload_checksum
FROM updated
JOIN platform_events AS e ON e.event_id = updated.event_id
ORDER BY updated.outbox_id ASC
"""

_MARK_DELIVERED_SQL = """
UPDATE platform_outbox
SET status = 'delivered',
    delivered_at = %s,
    locked_until = NULL,
    claimed_at = NULL,
    claimed_by = NULL,
    last_error = NULL
WHERE event_id = %s AND sink = %s
RETURNING outbox_id
"""

_MARK_FAILED_SQL = """
UPDATE platform_outbox
SET status = 'failed',
    last_error = %s,
    available_at = %s,
    locked_until = NULL,
    claimed_at = NULL,
    claimed_by = NULL
WHERE event_id = %s AND sink = %s
RETURNING outbox_id
"""

_SELECT_MANIFEST_SQL = """
SELECT
    manifest_id,
    event_id,
    schema_version,
    manifest_type,
    generated_at,
    bucket,
    entries_json::text,
    metadata_json::text,
    checksum_algorithm,
    checksum
FROM platform_evidence_manifests
WHERE manifest_id = %s
"""


class PostgresOutbox:
    def __init__(self, connection: object) -> None:
        self.connection = connection

    def publish(
        self,
        event: EventEnvelope,
        *,
        sinks: Iterable[str],
        manifest: EvidenceManifest | None = None,
        available_at: str | None = None,
    ) -> OutboxPublishResult:
        normalized_sinks = _normalize_sinks(sinks)
        if not normalized_sinks:
            raise ValueError("sinks cannot be empty")
        if manifest is not None and manifest.event_id != event.event_id:
            raise ValueError("manifest.event_id must match event.event_id")

        ready_at = event.occurred_at if available_at is None else available_at
        event_created = False
        manifest_created = False
        delivery_rows_created = 0
        try:
            event_result = self.connection.execute(
                _INSERT_EVENT_SQL,
                (
                    event.event_id,
                    event.schema_version,
                    event.event_type,
                    event.aggregate_type,
                    event.aggregate_id,
                    event.occurred_at,
                    event.producer,
                    event.partition_key,
                    canonical_json(event.payload),
                    canonical_json(event.metadata),
                    event.payload_checksum,
                ),
            )
            event_created = _fetchone_exists(event_result)

            manifest_id: str | None = None
            if manifest is not None:
                manifest_result = self.connection.execute(
                    _INSERT_MANIFEST_SQL,
                    (
                        manifest.manifest_id,
                        manifest.event_id,
                        manifest.schema_version,
                        manifest.manifest_type,
                        manifest.generated_at,
                        manifest.bucket,
                        canonical_json([entry.as_dict() for entry in manifest.entries]),
                        canonical_json(manifest.metadata),
                        manifest.checksum_algorithm,
                        manifest.checksum,
                    ),
                )
                manifest_created = _fetchone_exists(manifest_result)
                manifest_id = manifest.manifest_id
            else:
                manifest_id = None

            for sink in normalized_sinks:
                outbox_result = self.connection.execute(
                    _INSERT_OUTBOX_SQL,
                    (event.event_id, sink, ready_at, manifest_id),
                )
                if _fetchone_exists(outbox_result):
                    delivery_rows_created += 1

            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

        return OutboxPublishResult(
            event_id=event.event_id,
            sinks=normalized_sinks,
            event_created=event_created,
            manifest_id=None if manifest is None else manifest.manifest_id,
            manifest_created=manifest_created,
            delivery_rows_created=delivery_rows_created,
            delivery_rows_existing=len(normalized_sinks) - delivery_rows_created,
        )

    def claim_batch(
        self,
        sink: str,
        *,
        consumer_id: str,
        limit: int = 100,
        lease_seconds: int = 60,
        now: str | None = None,
    ) -> tuple[ClaimedOutboxRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be >= 1")
        claim_time = _utc_now() if now is None else now
        locked_until = _isoformat_utc(_parse_timestamp(claim_time) + timedelta(seconds=lease_seconds))
        try:
            result = self.connection.execute(
                _CLAIM_OUTBOX_SQL,
                (
                    sink,
                    claim_time,
                    claim_time,
                    limit,
                    claim_time,
                    consumer_id,
                    locked_until,
                    claim_time,
                ),
            )
            rows = tuple(_fetchall(result))
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise
        return tuple(_claimed_record_from_row(row) for row in rows)

    def mark_delivered(self, *, event_id: str, sink: str, delivered_at: str | None = None) -> bool:
        completed_at = _utc_now() if delivered_at is None else delivered_at
        try:
            result = self.connection.execute(_MARK_DELIVERED_SQL, (completed_at, event_id, sink))
            updated = _fetchone_exists(result)
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise
        return updated

    def mark_failed(
        self,
        *,
        event_id: str,
        sink: str,
        error: str,
        failed_at: str | None = None,
        retry_at: str | None = None,
    ) -> bool:
        failure_time = _utc_now() if failed_at is None else failed_at
        next_attempt = failure_time if retry_at is None else retry_at
        try:
            result = self.connection.execute(_MARK_FAILED_SQL, (error, next_attempt, event_id, sink))
            updated = _fetchone_exists(result)
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise
        return updated

    def fetch_manifest(self, manifest_id: str) -> EvidenceManifest | None:
        row = _fetchone(self.connection.execute(_SELECT_MANIFEST_SQL, (manifest_id,)))
        if row is None:
            return None
        entries_payload = _decode_json(_row_get(row, "entries_json", 6))
        metadata_payload = _decode_json(_row_get(row, "metadata_json", 7))
        manifest_payload = {
            "manifest_id": _row_get(row, "manifest_id", 0),
            "event_id": _row_get(row, "event_id", 1),
            "schema_version": _row_get(row, "schema_version", 2),
            "manifest_type": _row_get(row, "manifest_type", 3),
            "generated_at": _row_get(row, "generated_at", 4),
            "bucket": _row_get(row, "bucket", 5),
            "entries": entries_payload,
            "metadata": metadata_payload,
            "checksum_algorithm": _row_get(row, "checksum_algorithm", 8),
            "checksum": _row_get(row, "checksum", 9),
        }
        return EvidenceManifest.from_dict(manifest_payload)


def _claimed_record_from_row(row: object) -> ClaimedOutboxRecord:
    payload = _decode_json(_row_get(row, "payload_json", 19))
    metadata = _decode_json(_row_get(row, "metadata_json", 20))
    event = EventEnvelope.from_dict(
        {
            "schema_version": _row_get(row, "schema_version", 12),
            "event_id": _row_get(row, "event_id", 1),
            "event_type": _row_get(row, "event_type", 13),
            "aggregate_type": _row_get(row, "aggregate_type", 14),
            "aggregate_id": _row_get(row, "aggregate_id", 15),
            "occurred_at": _row_get(row, "occurred_at", 16),
            "producer": _row_get(row, "producer", 17),
            "partition_key": _row_get(row, "partition_key", 18),
            "payload": payload,
            "metadata": metadata,
            "payload_checksum": _row_get(row, "payload_checksum", 21),
        }
    )
    return ClaimedOutboxRecord(
        outbox_id=int(_row_get(row, "outbox_id", 0)),
        sink=str(_row_get(row, "sink", 2)),
        status=str(_row_get(row, "status", 3)),
        available_at=str(_row_get(row, "available_at", 4)),
        claimed_at=_optional_str(_row_get(row, "claimed_at", 5)),
        claimed_by=_optional_str(_row_get(row, "claimed_by", 6)),
        attempt_count=int(_row_get(row, "attempt_count", 7)),
        delivered_at=_optional_str(_row_get(row, "delivered_at", 8)),
        last_error=_optional_str(_row_get(row, "last_error", 9)),
        locked_until=_optional_str(_row_get(row, "locked_until", 10)),
        manifest_id=_optional_str(_row_get(row, "manifest_id", 11)),
        event=event,
    )


def _normalize_sinks(sinks: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for sink in sinks:
        candidate = str(sink).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return tuple(normalized)


def _row_get(row: object, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    if isinstance(row, Sequence):
        return row[index]
    raise TypeError(f"Unsupported row type: {type(row).__name__}")


def _decode_json(value: object) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(value, str):
        decoded = json.loads(value)
    else:
        decoded = value
    if isinstance(decoded, dict):
        return ensure_json_object(decoded, field_name="json payload")
    if isinstance(decoded, list):
        return [ensure_json_object(item, field_name="json list item") for item in decoded]
    raise ValueError("Expected JSON object or list")


def _fetchone(result: object) -> object | None:
    fetchone = getattr(result, "fetchone", None)
    return None if not callable(fetchone) else fetchone()


def _fetchall(result: object) -> list[object]:
    fetchall = getattr(result, "fetchall", None)
    if not callable(fetchall):
        return []
    return list(fetchall())


def _fetchone_exists(result: object) -> bool:
    return _fetchone(result) is not None


def _commit_quietly(connection: object) -> None:
    commit = getattr(connection, "commit", None)
    if callable(commit):
        commit()


def _rollback_quietly(connection: object) -> None:
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        rollback()


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_timestamp(value: str) -> datetime:
    candidate = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


__all__ = [
    "ClaimedOutboxRecord",
    "OutboxPublishResult",
    "PostgresOutbox",
]
