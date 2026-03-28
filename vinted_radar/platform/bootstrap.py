from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import re
import uuid
from urllib.parse import urlsplit

from vinted_radar.platform.config import PlatformConfig, load_platform_config, redact_url_credentials
from vinted_radar.platform.migrations import (
    MigrationRunResult,
    SqlMigration,
    clickhouse_migrations_dir as default_clickhouse_migrations_dir,
    iter_sql_statements,
    postgres_migrations_dir as default_postgres_migrations_dir,
    run_versioned_migrations,
)

_POSTGRES_MIGRATION_TABLE = "platform_schema_migrations"
_CLICKHOUSE_MIGRATION_TABLE = "platform_schema_migrations"
_OBJECT_STORAGE_PREFIX_NAMES = ("raw_events", "manifests", "parquet")
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class SchemaSystemStatus:
    name: str
    ok: bool
    endpoint: str
    migration_dir: str
    expected_version: int
    available_version: int | None
    current_version: int | None
    applied_versions: tuple[int, ...]
    pending_versions: tuple[int, ...]
    applied_this_run: tuple[int, ...]
    unexpected_versions: tuple[int, ...]
    mismatched_checksums: tuple[int, ...]
    detail: str
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "endpoint": self.endpoint,
            "migration_dir": self.migration_dir,
            "expected_version": self.expected_version,
            "available_version": self.available_version,
            "current_version": self.current_version,
            "applied_versions": list(self.applied_versions),
            "pending_versions": list(self.pending_versions),
            "applied_this_run": list(self.applied_this_run),
            "unexpected_versions": list(self.unexpected_versions),
            "mismatched_checksums": list(self.mismatched_checksums),
            "detail": self.detail,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class ObjectStorageStatus:
    ok: bool
    endpoint_url: str
    bucket: str
    region: str
    prefixes: dict[str, str]
    bucket_exists: bool
    bucket_created: bool
    ensured_marker_keys: tuple[str, ...]
    write_checked_prefixes: tuple[str, ...]
    detail: str
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "endpoint_url": self.endpoint_url,
            "bucket": self.bucket,
            "region": self.region,
            "prefixes": dict(self.prefixes),
            "bucket_exists": self.bucket_exists,
            "bucket_created": self.bucket_created,
            "ensured_marker_keys": list(self.ensured_marker_keys),
            "write_checked_prefixes": list(self.write_checked_prefixes),
            "detail": self.detail,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class PlatformBootstrapReport:
    mode: str
    ok: bool
    config: dict[str, object]
    postgres: SchemaSystemStatus
    clickhouse: SchemaSystemStatus
    object_storage: ObjectStorageStatus
    check_writes: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "check_writes": self.check_writes,
            "config": self.config,
            "postgres": self.postgres.as_dict(),
            "clickhouse": self.clickhouse.as_dict(),
            "object_storage": self.object_storage.as_dict(),
        }


def bootstrap_data_platform(
    *,
    config: PlatformConfig | None = None,
    postgres_migrations_dir: str | Path | None = None,
    clickhouse_migrations_dir: str | Path | None = None,
    check_writes: bool = True,
) -> PlatformBootstrapReport:
    resolved_config = load_platform_config() if config is None else config
    return _run_platform_checks(
        mode="bootstrap",
        config=resolved_config,
        postgres_migrations_dir=postgres_migrations_dir,
        clickhouse_migrations_dir=clickhouse_migrations_dir,
        apply_migrations=True,
        create_bucket=True,
        ensure_prefix_markers=True,
        check_writes=check_writes,
    )


def doctor_data_platform(
    *,
    config: PlatformConfig | None = None,
    postgres_migrations_dir: str | Path | None = None,
    clickhouse_migrations_dir: str | Path | None = None,
    check_writes: bool = True,
) -> PlatformBootstrapReport:
    resolved_config = load_platform_config() if config is None else config
    return _run_platform_checks(
        mode="doctor",
        config=resolved_config,
        postgres_migrations_dir=postgres_migrations_dir,
        clickhouse_migrations_dir=clickhouse_migrations_dir,
        apply_migrations=False,
        create_bucket=False,
        ensure_prefix_markers=False,
        check_writes=check_writes,
    )


def _run_platform_checks(
    *,
    mode: str,
    config: PlatformConfig,
    postgres_migrations_dir: str | Path | None,
    clickhouse_migrations_dir: str | Path | None,
    apply_migrations: bool,
    create_bucket: bool,
    ensure_prefix_markers: bool,
    check_writes: bool,
) -> PlatformBootstrapReport:
    resolved_postgres_dir = Path(postgres_migrations_dir) if postgres_migrations_dir is not None else default_postgres_migrations_dir()
    resolved_clickhouse_dir = Path(clickhouse_migrations_dir) if clickhouse_migrations_dir is not None else default_clickhouse_migrations_dir()
    postgres_status = _check_postgres(
        config=config,
        migration_dir=resolved_postgres_dir,
        apply_migrations=apply_migrations,
    )
    clickhouse_status = _check_clickhouse(
        config=config,
        migration_dir=resolved_clickhouse_dir,
        apply_migrations=apply_migrations,
    )
    object_storage_status = _check_object_storage(
        config=config,
        create_bucket=create_bucket,
        ensure_prefix_markers=ensure_prefix_markers,
        check_writes=check_writes,
    )
    return PlatformBootstrapReport(
        mode=mode,
        ok=postgres_status.ok and clickhouse_status.ok and object_storage_status.ok,
        config=config.as_redacted_dict(),
        postgres=postgres_status,
        clickhouse=clickhouse_status,
        object_storage=object_storage_status,
        check_writes=check_writes,
    )


def _check_postgres(
    *,
    config: PlatformConfig,
    migration_dir: Path,
    apply_migrations: bool,
) -> SchemaSystemStatus:
    connection = None
    endpoint = redact_url_credentials(config.postgres.dsn)
    try:
        connection = _connect_postgres(config.postgres.dsn)
        connection.execute("SELECT 1").fetchone()
        result = run_versioned_migrations(
            backend=_PostgresMigrationBackend(connection),
            directory=migration_dir,
            expected_version=config.postgres.schema_version,
            apply=apply_migrations,
        )
        return SchemaSystemStatus(
            name="postgres",
            ok=result.healthy,
            endpoint=endpoint,
            migration_dir=str(migration_dir),
            expected_version=config.postgres.schema_version,
            available_version=result.available_version,
            current_version=result.current_version,
            applied_versions=result.applied_versions,
            pending_versions=result.pending_versions,
            applied_this_run=result.applied_this_run,
            unexpected_versions=result.unexpected_versions,
            mismatched_checksums=result.mismatched_checksums,
            detail=_build_schema_detail("PostgreSQL", result, apply_migrations=apply_migrations),
        )
    except Exception as exc:  # noqa: BLE001
        return SchemaSystemStatus(
            name="postgres",
            ok=False,
            endpoint=endpoint,
            migration_dir=str(migration_dir),
            expected_version=config.postgres.schema_version,
            available_version=None,
            current_version=None,
            applied_versions=(),
            pending_versions=(),
            applied_this_run=(),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail=f"PostgreSQL bootstrap failed: {type(exc).__name__}: {exc}",
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        _close_quietly(connection)


def _check_clickhouse(
    *,
    config: PlatformConfig,
    migration_dir: Path,
    apply_migrations: bool,
) -> SchemaSystemStatus:
    client = None
    endpoint = f"{config.clickhouse.url} / {config.clickhouse.database}"
    try:
        client = _get_clickhouse_client(config, database="default")
        client.command("SELECT 1")
        result = run_versioned_migrations(
            backend=_ClickHouseMigrationBackend(
                client=client,
                database=config.clickhouse.database,
                database_client_factory=lambda: _get_clickhouse_client(
                    config,
                    database=config.clickhouse.database,
                ),
            ),
            directory=migration_dir,
            expected_version=config.clickhouse.schema_version,
            apply=apply_migrations,
        )
        return SchemaSystemStatus(
            name="clickhouse",
            ok=result.healthy,
            endpoint=endpoint,
            migration_dir=str(migration_dir),
            expected_version=config.clickhouse.schema_version,
            available_version=result.available_version,
            current_version=result.current_version,
            applied_versions=result.applied_versions,
            pending_versions=result.pending_versions,
            applied_this_run=result.applied_this_run,
            unexpected_versions=result.unexpected_versions,
            mismatched_checksums=result.mismatched_checksums,
            detail=_build_schema_detail("ClickHouse", result, apply_migrations=apply_migrations),
        )
    except Exception as exc:  # noqa: BLE001
        return SchemaSystemStatus(
            name="clickhouse",
            ok=False,
            endpoint=endpoint,
            migration_dir=str(migration_dir),
            expected_version=config.clickhouse.schema_version,
            available_version=None,
            current_version=None,
            applied_versions=(),
            pending_versions=(),
            applied_this_run=(),
            unexpected_versions=(),
            mismatched_checksums=(),
            detail=f"ClickHouse bootstrap failed: {type(exc).__name__}: {exc}",
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        _close_quietly(client)


def _check_object_storage(
    *,
    config: PlatformConfig,
    create_bucket: bool,
    ensure_prefix_markers: bool,
    check_writes: bool,
) -> ObjectStorageStatus:
    client = None
    prefixes = {
        "raw_events": config.storage.raw_events,
        "manifests": config.storage.manifests,
        "parquet": config.storage.parquet,
    }
    try:
        client = _create_s3_client(config)
        bucket_exists = _bucket_exists(client, config.object_storage.bucket)
        bucket_created = False
        if not bucket_exists and create_bucket:
            _create_bucket(
                client=client,
                bucket=config.object_storage.bucket,
                region=config.object_storage.region,
            )
            bucket_exists = True
            bucket_created = True
        if not bucket_exists:
            return ObjectStorageStatus(
                ok=False,
                endpoint_url=config.object_storage.endpoint_url,
                bucket=config.object_storage.bucket,
                region=config.object_storage.region,
                prefixes=prefixes,
                bucket_exists=False,
                bucket_created=False,
                ensured_marker_keys=(),
                write_checked_prefixes=(),
                detail=f"Object-store bucket '{config.object_storage.bucket}' is missing.",
                error="bucket-missing",
            )

        ensured_marker_keys: list[str] = []
        if ensure_prefix_markers:
            for prefix_name in _OBJECT_STORAGE_PREFIX_NAMES:
                marker_key = _prefix_marker_key(prefixes[prefix_name])
                client.put_object(Bucket=config.object_storage.bucket, Key=marker_key, Body=b"")
                ensured_marker_keys.append(marker_key)

        write_checked_prefixes: list[str] = []
        if check_writes:
            for prefix_name in _OBJECT_STORAGE_PREFIX_NAMES:
                probe_key = f"{prefixes[prefix_name].rstrip('/')}/_doctor/{uuid.uuid4().hex}.probe"
                client.put_object(Bucket=config.object_storage.bucket, Key=probe_key, Body=b"platform-doctor")
                client.delete_object(Bucket=config.object_storage.bucket, Key=probe_key)
                write_checked_prefixes.append(prefix_name)

        detail_parts = [
            f"bucket '{config.object_storage.bucket}' ready",
        ]
        if bucket_created:
            detail_parts.append("created during bootstrap")
        if ensured_marker_keys:
            detail_parts.append(f"ensured {len(ensured_marker_keys)} prefix marker object(s)")
        if write_checked_prefixes:
            detail_parts.append(f"write probe ok for {', '.join(write_checked_prefixes)}")
        return ObjectStorageStatus(
            ok=True,
            endpoint_url=config.object_storage.endpoint_url,
            bucket=config.object_storage.bucket,
            region=config.object_storage.region,
            prefixes=prefixes,
            bucket_exists=True,
            bucket_created=bucket_created,
            ensured_marker_keys=tuple(ensured_marker_keys),
            write_checked_prefixes=tuple(write_checked_prefixes),
            detail="; ".join(detail_parts),
        )
    except Exception as exc:  # noqa: BLE001
        return ObjectStorageStatus(
            ok=False,
            endpoint_url=config.object_storage.endpoint_url,
            bucket=config.object_storage.bucket,
            region=config.object_storage.region,
            prefixes=prefixes,
            bucket_exists=False,
            bucket_created=False,
            ensured_marker_keys=(),
            write_checked_prefixes=(),
            detail=f"Object-store bootstrap failed: {type(exc).__name__}: {exc}",
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        _close_quietly(client)


def _build_schema_detail(provider: str, result: MigrationRunResult, *, apply_migrations: bool) -> str:
    if result.healthy:
        if apply_migrations and result.applied_this_run:
            applied = ", ".join(f"V{version:03d}" for version in result.applied_this_run)
            return f"{provider} reachable; schema v{result.current_version}/{result.expected_version}; applied {applied}"
        return f"{provider} reachable; schema v{result.current_version}/{result.expected_version}; no pending migrations"

    issues: list[str] = []
    if result.pending_versions:
        issues.append(
            "pending migrations " + ", ".join(f"V{version:03d}" for version in result.pending_versions)
        )
    if result.unexpected_versions:
        issues.append(
            "unexpected applied versions " + ", ".join(f"V{version:03d}" for version in result.unexpected_versions)
        )
    if result.mismatched_checksums:
        issues.append(
            "checksum mismatch for " + ", ".join(f"V{version:03d}" for version in result.mismatched_checksums)
        )
    if result.available_version < result.expected_version:
        issues.append(f"only V{result.available_version:03d} available locally")
    if not issues:
        issues.append("schema version mismatch")
    return f"{provider} reachable but unhealthy: {'; '.join(issues)}"


class _PostgresMigrationBackend:
    def __init__(self, connection: object) -> None:
        self.connection = connection

    def fetch_applied_versions(self, *, create_if_missing: bool) -> Mapping[int, str]:
        exists = bool(
            self.connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = %s
                )
                """,
                (_POSTGRES_MIGRATION_TABLE,),
            ).fetchone()[0]
        )
        if not exists:
            if not create_if_missing:
                return {}
            self.connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_POSTGRES_MIGRATION_TABLE} (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            self.connection.commit()
        rows = self.connection.execute(
            f"SELECT version, checksum FROM {_POSTGRES_MIGRATION_TABLE} ORDER BY version"
        ).fetchall()
        return {int(row[0]): str(row[1]) for row in rows}

    def apply_migration(self, migration: SqlMigration) -> None:
        try:
            for statement in iter_sql_statements(migration.sql):
                self.connection.execute(statement)
            self.connection.execute(
                f"INSERT INTO {_POSTGRES_MIGRATION_TABLE} (version, name, checksum) VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
            self.connection.commit()
        except Exception:  # noqa: BLE001
            self.connection.rollback()
            raise


class _ClickHouseMigrationBackend:
    def __init__(self, *, client: object, database: str, database_client_factory: Callable[[], object]) -> None:
        self.client = client
        self.database = _safe_identifier(database, field_name="ClickHouse database")
        self.database_client_factory = database_client_factory

    def fetch_applied_versions(self, *, create_if_missing: bool) -> Mapping[int, str]:
        database_exists = bool(int(self.client.command(f"EXISTS DATABASE {self.database}")))
        if not database_exists:
            if not create_if_missing:
                return {}
            self.client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
        table_exists = bool(int(self.client.command(f"EXISTS TABLE {self.database}.{_CLICKHOUSE_MIGRATION_TABLE}")))
        if not table_exists:
            if not create_if_missing:
                return {}
            self.client.command(
                f"""
                CREATE TABLE IF NOT EXISTS {self.database}.{_CLICKHOUSE_MIGRATION_TABLE} (
                    version UInt32,
                    name String,
                    checksum String,
                    applied_at DateTime DEFAULT now()
                )
                ENGINE = MergeTree
                ORDER BY version
                """
            )
        rows = self.client.query(
            f"SELECT version, checksum FROM {self.database}.{_CLICKHOUSE_MIGRATION_TABLE} ORDER BY version"
        ).result_rows
        return {int(row[0]): str(row[1]) for row in rows}

    def apply_migration(self, migration: SqlMigration) -> None:
        migration_client = self.database_client_factory()
        same_client = migration_client is self.client
        try:
            for statement in iter_sql_statements(migration.sql):
                migration_client.command(statement)
        finally:
            if not same_client:
                _close_quietly(migration_client)
        self.client.command(
            f"INSERT INTO {self.database}.{_CLICKHOUSE_MIGRATION_TABLE} (version, name, checksum) VALUES ({migration.version}, '{migration.name}', '{migration.checksum}')"
        )


def _connect_postgres(dsn: str):
    import psycopg

    return psycopg.connect(dsn)


def _get_clickhouse_client(config: PlatformConfig, *, database: str):
    import clickhouse_connect

    parts = urlsplit(config.clickhouse.url)
    return clickhouse_connect.get_client(
        host=parts.hostname or "127.0.0.1",
        port=parts.port or (8443 if parts.scheme == "https" else 8123),
        username=config.clickhouse.username,
        password=config.clickhouse.password,
        database=database,
        secure=parts.scheme == "https",
    )


def _create_s3_client(config: PlatformConfig):
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=config.object_storage.endpoint_url,
        aws_access_key_id=config.object_storage.access_key_id,
        aws_secret_access_key=config.object_storage.secret_access_key,
        region_name=config.object_storage.region,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


def _bucket_exists(client: object, bucket: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket)
        return True
    except Exception as exc:  # noqa: BLE001
        code = _error_code(exc)
        if code in {"404", "NoSuchBucket", "NotFound"}:
            return False
        raise


def _create_bucket(*, client: object, bucket: str, region: str) -> None:
    if region == "us-east-1":
        client.create_bucket(Bucket=bucket)
        return
    client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": region},
    )


def _prefix_marker_key(prefix: str) -> str:
    return f"{prefix.rstrip('/')}/.prefix"


def _error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return None if code is None else str(code)


def _close_quietly(resource: object | None) -> None:
    if resource is None:
        return
    for method_name in ("close", "close_connections"):
        method = getattr(resource, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:  # noqa: BLE001
                pass
            return


def _safe_identifier(value: str, *, field_name: str) -> str:
    if not _SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{field_name} must contain only letters, digits, and underscores, and cannot start with a digit")
    return value


__all__ = [
    "ObjectStorageStatus",
    "PlatformBootstrapReport",
    "SchemaSystemStatus",
    "bootstrap_data_platform",
    "doctor_data_platform",
]
