from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str,
        ContinuationToken: str | None = None,
    ) -> dict[str, Any]:
        keys = sorted(
            key
            for (bucket, key) in self.objects
            if bucket == Bucket and key.startswith(Prefix)
        )
        start_index = 0 if ContinuationToken is None else int(ContinuationToken)
        page = keys[start_index : start_index + 1000]
        next_index = start_index + len(page)
        return {
            "Contents": [{"Key": key} for key in page],
            "IsTruncated": next_index < len(keys),
            "NextContinuationToken": None if next_index >= len(keys) else str(next_index),
        }

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


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
