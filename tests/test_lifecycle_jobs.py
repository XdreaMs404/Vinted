from __future__ import annotations

from dataclasses import replace
import json
from typing import Any

from typer.testing import CliRunner

from tests.platform_test_fakes import FakeQueryResult, FakeS3Client, FakeS3Error
from vinted_radar.cli import app
from vinted_radar.platform.config import (
    ARCHIVES_PREFIX_ENV,
    OBJECT_STORE_ARCHIVES_RETENTION_CLASS_ENV,
    OBJECT_STORE_ARCHIVES_RETENTION_DAYS_ENV,
    OBJECT_STORE_MANIFESTS_RETENTION_CLASS_ENV,
    OBJECT_STORE_MANIFESTS_RETENTION_DAYS_ENV,
    OBJECT_STORE_PARQUET_RETENTION_CLASS_ENV,
    OBJECT_STORE_PARQUET_RETENTION_DAYS_ENV,
    OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS_ENV,
    OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS_ENV,
    POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS_ENV,
    POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS_ENV,
    POSTGRES_OUTBOX_FAILED_RETENTION_DAYS_ENV,
    POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS_ENV,
    load_platform_config,
)
from vinted_radar.services.lifecycle import LifecycleReport, run_lifecycle_jobs


class LifecycleFakeS3Client(FakeS3Client):
    def __init__(self) -> None:
        super().__init__()
        self.lifecycle_configuration: dict[str, object] | None = None

    def get_bucket_lifecycle_configuration(self, *, Bucket: str) -> dict[str, object]:
        if self.lifecycle_configuration is None:
            raise FakeS3Error("NoSuchLifecycleConfiguration")
        return self.lifecycle_configuration

    def put_bucket_lifecycle_configuration(self, *, Bucket: str, LifecycleConfiguration: dict[str, object]) -> None:
        self.lifecycle_configuration = json.loads(json.dumps(LifecycleConfiguration))


class LifecycleFakePostgresConnection:
    def __init__(self) -> None:
        self.bootstrap_audit = [
            {
                "event_id": 1,
                "component": "postgres",
                "status": "ok",
                "detail": {"note": "old"},
                "recorded_at": "2025-01-01T00:00:00+00:00",
            },
            {
                "event_id": 2,
                "component": "clickhouse",
                "status": "ok",
                "detail": {"note": "recent"},
                "recorded_at": "2026-03-15T00:00:00+00:00",
            },
        ]
        self.outbox = [
            {
                "outbox_id": 10,
                "event_id": "evt-delivered-old",
                "sink": "clickhouse",
                "status": "delivered",
                "available_at": "2025-12-01T00:00:00+00:00",
                "claimed_at": None,
                "claimed_by": None,
                "locked_until": None,
                "attempt_count": 1,
                "last_attempt_at": "2025-12-01T00:10:00+00:00",
                "delivered_at": "2025-12-01T00:10:00+00:00",
                "last_error": None,
                "manifest_id": "man-delivered-old",
                "created_at": "2025-12-01T00:00:00+00:00",
            },
            {
                "outbox_id": 11,
                "event_id": "evt-failed-old",
                "sink": "clickhouse",
                "status": "failed",
                "available_at": "2025-12-15T00:00:00+00:00",
                "claimed_at": None,
                "claimed_by": None,
                "locked_until": None,
                "attempt_count": 3,
                "last_attempt_at": "2025-12-15T00:10:00+00:00",
                "delivered_at": None,
                "last_error": "timeout",
                "manifest_id": "man-failed-old",
                "created_at": "2025-12-15T00:00:00+00:00",
            },
            {
                "outbox_id": 12,
                "event_id": "evt-delivered-recent",
                "sink": "clickhouse",
                "status": "delivered",
                "available_at": "2026-03-30T00:00:00+00:00",
                "claimed_at": None,
                "claimed_by": None,
                "locked_until": None,
                "attempt_count": 1,
                "last_attempt_at": "2026-03-30T00:10:00+00:00",
                "delivered_at": "2026-03-30T00:10:00+00:00",
                "last_error": None,
                "manifest_id": "man-delivered-recent",
                "created_at": "2026-03-30T00:00:00+00:00",
            },
        ]
        self.runtime_cycles = [
            {
                "cycle_id": "cycle-old",
                "started_at": "2025-11-01T00:00:00+00:00",
                "finished_at": "2025-11-01T00:10:00+00:00",
                "mode": "continuous",
                "status": "completed",
                "phase": "completed",
                "interval_seconds": 1800.0,
                "state_probe_limit": 5,
                "discovery_run_id": "run-old",
                "state_probed_count": 2,
                "tracked_listings": 20,
                "first_pass_only": 1,
                "fresh_followup": 2,
                "aging_followup": 3,
                "stale_followup": 4,
                "last_error": None,
                "state_refresh_summary_json": {"status": "healthy"},
                "config_json": {"page_limit": 1},
                "last_event_id": None,
                "last_manifest_id": None,
                "projected_at": "2025-11-01T00:10:00+00:00",
            },
            {
                "cycle_id": "cycle-keep",
                "started_at": "2026-03-30T00:00:00+00:00",
                "finished_at": "2026-03-30T00:10:00+00:00",
                "mode": "continuous",
                "status": "completed",
                "phase": "completed",
                "interval_seconds": 1800.0,
                "state_probe_limit": 5,
                "discovery_run_id": "run-keep",
                "state_probed_count": 1,
                "tracked_listings": 10,
                "first_pass_only": 1,
                "fresh_followup": 1,
                "aging_followup": 0,
                "stale_followup": 0,
                "last_error": None,
                "state_refresh_summary_json": {"status": "healthy"},
                "config_json": {"page_limit": 1},
                "last_event_id": None,
                "last_manifest_id": None,
                "projected_at": "2026-03-30T00:10:00+00:00",
            },
        ]
        self.runtime_controller = {
            "active_cycle_id": None,
            "latest_cycle_id": "cycle-keep",
        }
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> FakeQueryResult:
        normalized = " ".join(sql.split())
        params = params or ()
        if normalized.startswith("SELECT event_id, component, status, detail, recorded_at FROM platform_bootstrap_audit"):
            cutoff = str(params[0])
            rows = [row for row in self.bootstrap_audit if str(row["recorded_at"]) < cutoff]
            rows.sort(key=lambda row: (str(row["recorded_at"]), int(row["event_id"])))
            return FakeQueryResult(rows)
        if normalized.startswith("SELECT outbox_id, event_id, sink, status, available_at, claimed_at, claimed_by, locked_until, attempt_count, last_attempt_at, delivered_at, last_error, manifest_id, created_at FROM platform_outbox WHERE status = 'delivered'"):
            cutoff = str(params[0])
            rows = [row for row in self.outbox if row["status"] == "delivered" and str(row["delivered_at"] or "") < cutoff]
            rows.sort(key=lambda row: (str(row["delivered_at"]), int(row["outbox_id"])))
            return FakeQueryResult(rows)
        if normalized.startswith("SELECT outbox_id, event_id, sink, status, available_at, claimed_at, claimed_by, locked_until, attempt_count, last_attempt_at, delivered_at, last_error, manifest_id, created_at FROM platform_outbox WHERE status = 'failed'"):
            cutoff = str(params[0])
            rows = [
                row
                for row in self.outbox
                if row["status"] == "failed" and str(row["last_attempt_at"] or row["created_at"]) < cutoff
            ]
            rows.sort(key=lambda row: (str(row["last_attempt_at"] or row["created_at"]), int(row["outbox_id"])))
            return FakeQueryResult(rows)
        if normalized.startswith("SELECT cycle_id, started_at, finished_at, mode, status, phase, interval_seconds, state_probe_limit, discovery_run_id, state_probed_count, tracked_listings, first_pass_only, fresh_followup, aging_followup, stale_followup, last_error, state_refresh_summary_json, config_json, last_event_id, last_manifest_id, projected_at FROM platform_runtime_cycles"):
            cutoff = str(params[0])
            rows = [row for row in self.runtime_cycles if str(row["finished_at"] or "") < cutoff]
            rows.sort(key=lambda row: (str(row["finished_at"]), str(row["cycle_id"])))
            return FakeQueryResult(rows)
        if normalized == "SELECT active_cycle_id, latest_cycle_id FROM platform_runtime_controller_state WHERE controller_id = %s":
            return FakeQueryResult([self.runtime_controller])
        if normalized.startswith("DELETE FROM platform_bootstrap_audit WHERE event_id IN"):
            ids = set(params)
            self.bootstrap_audit = [row for row in self.bootstrap_audit if row["event_id"] not in ids]
            return FakeQueryResult([])
        if normalized.startswith("DELETE FROM platform_outbox WHERE outbox_id IN"):
            ids = set(params)
            self.outbox = [row for row in self.outbox if row["outbox_id"] not in ids]
            return FakeQueryResult([])
        if normalized.startswith("DELETE FROM platform_runtime_cycles WHERE cycle_id IN"):
            ids = set(params)
            self.runtime_cycles = [row for row in self.runtime_cycles if row["cycle_id"] not in ids]
            return FakeQueryResult([])
        raise AssertionError(f"Unexpected SQL: {normalized}")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RecordingClickHouseClient:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def command(self, sql: str):
        self.commands.append(" ".join(sql.split()))
        return None


def test_load_platform_config_includes_lifecycle_defaults_and_overrides() -> None:
    config = load_platform_config(env={})

    assert config.storage.archives == "vinted-radar/archives"
    assert config.lifecycle.postgres.as_dict() == {
        "bootstrap_audit_retention_days": 30,
        "delivered_outbox_retention_days": 14,
        "failed_outbox_retention_days": 30,
        "runtime_cycles_retention_days": 90,
    }
    assert config.lifecycle.object_storage.as_dict() == {
        "raw_events": {"retention_class": "transient-evidence", "retention_days": 730},
        "manifests": {"retention_class": "audit-manifest", "retention_days": 3650},
        "parquet": {"retention_class": "warehouse", "retention_days": 3650},
        "archives": {"retention_class": "archive", "retention_days": 3650},
    }

    overridden = load_platform_config(
        env={
            ARCHIVES_PREFIX_ENV: "/tenant-a/archives/",
            POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS_ENV: "7",
            POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS_ENV: "5",
            POSTGRES_OUTBOX_FAILED_RETENTION_DAYS_ENV: "21",
            POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS_ENV: "45",
            OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS_ENV: "90",
            OBJECT_STORE_MANIFESTS_RETENTION_DAYS_ENV: "365",
            OBJECT_STORE_PARQUET_RETENTION_DAYS_ENV: "730",
            OBJECT_STORE_ARCHIVES_RETENTION_DAYS_ENV: "180",
            OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS_ENV: "raw-hot",
            OBJECT_STORE_MANIFESTS_RETENTION_CLASS_ENV: "manifest-warm",
            OBJECT_STORE_PARQUET_RETENTION_CLASS_ENV: "warehouse-cold",
            OBJECT_STORE_ARCHIVES_RETENTION_CLASS_ENV: "archive-cold",
        }
    )

    assert overridden.storage.archives == "tenant-a/archives"
    assert overridden.lifecycle.postgres.delivered_outbox_retention_days == 5
    assert overridden.lifecycle.object_storage.archives.as_dict() == {
        "retention_class": "archive-cold",
        "retention_days": 180,
    }


def test_run_lifecycle_jobs_applies_ttl_prunes_postgres_and_sets_bucket_rules() -> None:
    config = load_platform_config(env={})
    postgres = LifecycleFakePostgresConnection()
    clickhouse = RecordingClickHouseClient()
    s3 = LifecycleFakeS3Client()
    s3.buckets.add(config.object_storage.bucket)
    s3.put_object(
        Bucket=config.object_storage.bucket,
        Key=f"{config.storage.raw_events}/sample.json",
        Body=b"{}",
        ContentType="application/json",
        Metadata={},
    )
    s3.put_object(
        Bucket=config.object_storage.bucket,
        Key=f"{config.storage.manifests}/sample.json",
        Body=b"{}",
        ContentType="application/json",
        Metadata={},
    )
    s3.put_object(
        Bucket=config.object_storage.bucket,
        Key=f"{config.storage.parquet}/sample.parquet",
        Body=b"PAR1",
        ContentType="application/octet-stream",
        Metadata={},
    )

    report = run_lifecycle_jobs(
        config=config,
        apply=True,
        reference_now="2026-03-31T10:00:00+00:00",
        postgres_connection=postgres,
        clickhouse_client=clickhouse,
        object_store_client=s3,
    )

    assert report.ok is True
    assert report.posture.bounded is True
    assert len(clickhouse.commands) == 7
    assert any("ALTER TABLE vinted_radar.fact_listing_seen_events MODIFY TTL observed_at + INTERVAL 730 DAY" in command for command in clickhouse.commands)

    postgres_actions = {action.table + ":" + action.key_column + ":" + str(action.retention_days): action for action in report.postgres.actions}
    assert postgres_actions["platform_bootstrap_audit:event_id:30"].deleted_rows == 1
    assert postgres_actions["platform_outbox:outbox_id:14"].deleted_rows == 1
    assert postgres_actions["platform_outbox:outbox_id:30"].deleted_rows == 1
    assert postgres_actions["platform_runtime_cycles:cycle_id:90"].deleted_rows == 1
    assert postgres_actions["platform_runtime_cycles:cycle_id:90"].protected_rows == 0
    assert postgres.commits == 4
    assert [row["event_id"] for row in postgres.bootstrap_audit] == [2]
    assert [row["outbox_id"] for row in postgres.outbox] == [12]
    assert [row["cycle_id"] for row in postgres.runtime_cycles] == ["cycle-keep"]

    archive_keys = sorted(
        key
        for (bucket, key) in s3.objects.keys()
        if bucket == config.object_storage.bucket and key.startswith(f"{config.storage.archives}/postgres/")
    )
    assert len(archive_keys) == 4
    assert s3.lifecycle_configuration is not None
    rule_ids = sorted(rule["ID"] for rule in list(s3.lifecycle_configuration.get("Rules") or []))
    assert rule_ids == [
        "archives-retention",
        "manifests-retention",
        "parquet-retention",
        "raw-events-retention",
    ]


def test_platform_lifecycle_cli_renders_table_output(monkeypatch) -> None:
    runner = CliRunner()
    config = load_platform_config(env={})
    fake_report = run_lifecycle_jobs(
        config=config,
        apply=False,
        reference_now="2026-03-31T10:00:00+00:00",
        postgres_connection=LifecycleFakePostgresConnection(),
        clickhouse_client=RecordingClickHouseClient(),
        object_store_client=LifecycleFakeS3Client(),
    )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: config)
    monkeypatch.setattr("vinted_radar.cli.run_lifecycle_jobs", lambda **kwargs: fake_report)

    result = runner.invoke(app, ["platform-lifecycle", "--dry-run"])

    assert result.exit_code == 0
    assert "Apply changes: no" in result.stdout
    assert "ClickHouse TTL:" in result.stdout
    assert "PostgreSQL prune/archive:" in result.stdout
    assert "Object-storage lifecycle:" in result.stdout
    assert "Storage posture:" in result.stdout
