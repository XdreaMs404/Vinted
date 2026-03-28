from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.platform.bootstrap import (
    ObjectStorageStatus,
    PlatformBootstrapReport,
    SchemaSystemStatus,
    bootstrap_data_platform,
    doctor_data_platform,
)
from vinted_radar.platform.config import load_platform_config
from vinted_radar.platform.migrations import load_sql_migrations


class FakeQueryResult:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    @property
    def result_rows(self):
        return [list(row) for row in self._rows]


class FakePostgresConnection:
    def __init__(self) -> None:
        self.migration_table_exists = False
        self.applied_versions: dict[int, str] = {}
        self.executed_sql: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> FakeQueryResult:
        normalized = " ".join(sql.split())
        self.executed_sql.append(normalized)
        if "SELECT 1" in normalized and "information_schema.tables" not in normalized:
            return FakeQueryResult([(1,)])
        if "information_schema.tables" in normalized:
            return FakeQueryResult([(self.migration_table_exists,)])
        if normalized.startswith("CREATE TABLE IF NOT EXISTS platform_schema_migrations"):
            self.migration_table_exists = True
            return FakeQueryResult()
        if normalized.startswith("SELECT version, checksum FROM platform_schema_migrations"):
            rows = [(version, checksum) for version, checksum in sorted(self.applied_versions.items())]
            return FakeQueryResult(rows)
        if normalized.startswith("INSERT INTO platform_schema_migrations"):
            assert params is not None
            version, _name, checksum = params
            self.applied_versions[int(version)] = str(checksum)
            return FakeQueryResult()
        return FakeQueryResult()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.database_exists = False
        self.migration_table_exists = False
        self.applied_versions: dict[int, str] = {}
        self.command_log: list[str] = []
        self.closed = False

    def command(self, sql: str):
        normalized = " ".join(sql.split())
        self.command_log.append(normalized)
        if normalized == "SELECT 1":
            return 1
        if normalized == "EXISTS DATABASE vinted_radar":
            return 1 if self.database_exists else 0
        if normalized == "CREATE DATABASE IF NOT EXISTS vinted_radar":
            self.database_exists = True
            return None
        if normalized == "EXISTS TABLE vinted_radar.platform_schema_migrations":
            return 1 if self.migration_table_exists else 0
        if normalized.startswith("CREATE TABLE IF NOT EXISTS vinted_radar.platform_schema_migrations"):
            self.migration_table_exists = True
            return None
        if normalized.startswith("INSERT INTO vinted_radar.platform_schema_migrations"):
            values_chunk = normalized.split("VALUES", 1)[1].strip().lstrip("(").rstrip(")")
            version_text, _name, checksum = [part.strip() for part in values_chunk.split(",", 2)]
            self.applied_versions[int(version_text)] = checksum.strip("'")
            return None
        return None

    def query(self, sql: str) -> FakeQueryResult:
        normalized = " ".join(sql.split())
        self.command_log.append(normalized)
        if normalized.startswith("SELECT version, checksum FROM vinted_radar.platform_schema_migrations"):
            rows = [(version, checksum) for version, checksum in sorted(self.applied_versions.items())]
            return FakeQueryResult(rows)
        return FakeQueryResult()

    def close(self) -> None:
        self.closed = True


class FakeS3Error(Exception):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class FakeS3Client:
    def __init__(self) -> None:
        self.bucket_exists = False
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_exists:
            raise FakeS3Error("404")

    def create_bucket(self, *, Bucket: str, CreateBucketConfiguration: dict[str, object] | None = None) -> None:
        self.bucket_exists = True

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[Key] = bytes(Body)

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.deleted.append(Key)
        self.objects.pop(Key, None)


def _write_migration_fixture(root: Path) -> tuple[Path, Path]:
    postgres_dir = root / "postgres"
    clickhouse_dir = root / "clickhouse"
    postgres_dir.mkdir(parents=True)
    clickhouse_dir.mkdir(parents=True)
    (postgres_dir / "V001__platform_bootstrap_audit.sql").write_text(
        "CREATE TABLE IF NOT EXISTS platform_bootstrap_audit (event_id BIGSERIAL PRIMARY KEY);",
        encoding="utf-8",
    )
    (postgres_dir / "V002__platform_event_outbox.sql").write_text(
        "CREATE TABLE IF NOT EXISTS platform_outbox (outbox_id BIGSERIAL PRIMARY KEY);",
        encoding="utf-8",
    )
    (clickhouse_dir / "V001__platform_bootstrap_audit.sql").write_text(
        "CREATE TABLE IF NOT EXISTS platform_bootstrap_audit (component String) ENGINE = MergeTree ORDER BY component;",
        encoding="utf-8",
    )
    return postgres_dir, clickhouse_dir


def test_load_sql_migrations_requires_contiguous_versions(tmp_path: Path) -> None:
    migration_dir = tmp_path / "postgres"
    migration_dir.mkdir()
    (migration_dir / "V001__init.sql").write_text("SELECT 1;", encoding="utf-8")
    (migration_dir / "V003__gap.sql").write_text("SELECT 3;", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected migration version"):
        load_sql_migrations(migration_dir)


def test_bootstrap_data_platform_applies_pending_migrations_and_bootstraps_object_store(monkeypatch, tmp_path: Path) -> None:
    postgres_dir, clickhouse_dir = _write_migration_fixture(tmp_path)
    postgres = FakePostgresConnection()
    clickhouse = FakeClickHouseClient()
    s3 = FakeS3Client()

    monkeypatch.setattr("vinted_radar.platform.bootstrap._connect_postgres", lambda dsn: postgres)
    monkeypatch.setattr("vinted_radar.platform.bootstrap._get_clickhouse_client", lambda config, database: clickhouse)
    monkeypatch.setattr("vinted_radar.platform.bootstrap._create_s3_client", lambda config: s3)

    report = bootstrap_data_platform(
        config=load_platform_config(env={}),
        postgres_migrations_dir=postgres_dir,
        clickhouse_migrations_dir=clickhouse_dir,
    )

    assert report.ok is True
    assert report.postgres.ok is True
    assert report.postgres.applied_this_run == (1, 2)
    assert report.postgres.current_version == 2
    assert report.clickhouse.ok is True
    assert report.clickhouse.applied_this_run == (1,)
    assert report.clickhouse.current_version == 1
    assert report.object_storage.ok is True
    assert report.object_storage.bucket_created is True
    assert sorted(report.object_storage.write_checked_prefixes) == ["manifests", "parquet", "raw_events"]
    assert len(report.object_storage.ensured_marker_keys) == 3
    assert report.as_dict()["config"]["postgres"]["dsn"] == "postgresql://***@127.0.0.1:5432/vinted_radar"


def test_doctor_data_platform_flags_missing_schema_and_bucket(monkeypatch, tmp_path: Path) -> None:
    postgres_dir, clickhouse_dir = _write_migration_fixture(tmp_path)
    postgres = FakePostgresConnection()
    clickhouse = FakeClickHouseClient()
    s3 = FakeS3Client()

    monkeypatch.setattr("vinted_radar.platform.bootstrap._connect_postgres", lambda dsn: postgres)
    monkeypatch.setattr("vinted_radar.platform.bootstrap._get_clickhouse_client", lambda config, database: clickhouse)
    monkeypatch.setattr("vinted_radar.platform.bootstrap._create_s3_client", lambda config: s3)

    report = doctor_data_platform(
        config=load_platform_config(env={}),
        postgres_migrations_dir=postgres_dir,
        clickhouse_migrations_dir=clickhouse_dir,
    )

    assert report.ok is False
    assert report.postgres.ok is False
    assert report.postgres.pending_versions == (1, 2)
    assert report.clickhouse.ok is False
    assert report.clickhouse.pending_versions == (1,)
    assert report.object_storage.ok is False
    assert report.object_storage.error == "bucket-missing"


def test_platform_bootstrap_cli_renders_table_output(monkeypatch) -> None:
    runner = CliRunner()
    report = PlatformBootstrapReport(
        mode="bootstrap",
        ok=True,
        config=load_platform_config(env={}).as_redacted_dict(),
        postgres=SchemaSystemStatus(
            name="postgres",
            ok=True,
            endpoint="postgresql://***@127.0.0.1:5432/vinted_radar",
            migration_dir="infra/postgres/migrations",
            expected_version=2,
            available_version=2,
            current_version=2,
            applied_versions=(1, 2),
            pending_versions=(),
            applied_this_run=(1, 2),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail="PostgreSQL reachable; schema v2/2; applied V001, V002",
        ),
        clickhouse=SchemaSystemStatus(
            name="clickhouse",
            ok=True,
            endpoint="http://127.0.0.1:8123 / vinted_radar",
            migration_dir="infra/clickhouse/migrations",
            expected_version=1,
            available_version=1,
            current_version=1,
            applied_versions=(1,),
            pending_versions=(),
            applied_this_run=(1,),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail="ClickHouse reachable; schema v1/1; applied V001",
        ),
        object_storage=ObjectStorageStatus(
            ok=True,
            endpoint_url="http://127.0.0.1:9000",
            bucket="vinted-radar",
            region="us-east-1",
            prefixes={
                "raw_events": "vinted-radar/events/raw",
                "manifests": "vinted-radar/manifests",
                "parquet": "vinted-radar/parquet",
            },
            bucket_exists=True,
            bucket_created=True,
            ensured_marker_keys=("vinted-radar/events/raw/.prefix",),
            write_checked_prefixes=("raw_events", "manifests", "parquet"),
            detail="bucket ready; write probe ok",
        ),
        check_writes=True,
    )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: load_platform_config(env={}))
    monkeypatch.setattr("vinted_radar.cli.bootstrap_data_platform", lambda **kwargs: report)

    result = runner.invoke(app, ["platform-bootstrap"])

    assert result.exit_code == 0
    assert "Mode: bootstrap" in result.stdout
    assert "PostgreSQL: ok" in result.stdout
    assert "ClickHouse: ok" in result.stdout
    assert "Object storage: ok" in result.stdout
    assert "Healthy: yes" in result.stdout


def test_platform_doctor_cli_exits_non_zero_when_checks_fail(monkeypatch) -> None:
    runner = CliRunner()
    report = PlatformBootstrapReport(
        mode="doctor",
        ok=False,
        config=load_platform_config(env={}).as_redacted_dict(),
        postgres=SchemaSystemStatus(
            name="postgres",
            ok=False,
            endpoint="postgresql://***@127.0.0.1:5432/vinted_radar",
            migration_dir="infra/postgres/migrations",
            expected_version=2,
            available_version=2,
            current_version=0,
            applied_versions=(),
            pending_versions=(1, 2),
            applied_this_run=(),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail="PostgreSQL reachable but unhealthy: pending migrations V001, V002",
            error="pending",
        ),
        clickhouse=SchemaSystemStatus(
            name="clickhouse",
            ok=False,
            endpoint="http://127.0.0.1:8123 / vinted_radar",
            migration_dir="infra/clickhouse/migrations",
            expected_version=1,
            available_version=1,
            current_version=0,
            applied_versions=(),
            pending_versions=(1,),
            applied_this_run=(),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail="ClickHouse reachable but unhealthy: pending migrations V001",
            error="pending",
        ),
        object_storage=ObjectStorageStatus(
            ok=False,
            endpoint_url="http://127.0.0.1:9000",
            bucket="vinted-radar",
            region="us-east-1",
            prefixes={
                "raw_events": "vinted-radar/events/raw",
                "manifests": "vinted-radar/manifests",
                "parquet": "vinted-radar/parquet",
            },
            bucket_exists=False,
            bucket_created=False,
            ensured_marker_keys=(),
            write_checked_prefixes=(),
            detail="bucket missing",
            error="bucket-missing",
        ),
        check_writes=True,
    )

    monkeypatch.setattr("vinted_radar.cli.load_platform_config", lambda: load_platform_config(env={}))
    monkeypatch.setattr("vinted_radar.cli.doctor_data_platform", lambda **kwargs: report)

    result = runner.invoke(app, ["platform-doctor"])

    assert result.exit_code == 1
    assert "Mode: doctor" in result.stdout
    assert "Healthy: no" in result.stdout
