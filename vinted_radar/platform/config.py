from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from vinted_radar.platform.clickhouse_schema import CLICKHOUSE_SERVING_SCHEMA_VERSION
from vinted_radar.platform.postgres_schema import POSTGRES_MUTABLE_SCHEMA_VERSION

POSTGRES_DSN_ENV = "VINTED_RADAR_PLATFORM_POSTGRES_DSN"
CLICKHOUSE_URL_ENV = "VINTED_RADAR_PLATFORM_CLICKHOUSE_URL"
CLICKHOUSE_DATABASE_ENV = "VINTED_RADAR_PLATFORM_CLICKHOUSE_DATABASE"
CLICKHOUSE_USERNAME_ENV = "VINTED_RADAR_PLATFORM_CLICKHOUSE_USERNAME"
CLICKHOUSE_PASSWORD_ENV = "VINTED_RADAR_PLATFORM_CLICKHOUSE_PASSWORD"
OBJECT_STORE_ENDPOINT_ENV = "VINTED_RADAR_PLATFORM_OBJECT_STORE_ENDPOINT"
OBJECT_STORE_BUCKET_ENV = "VINTED_RADAR_PLATFORM_OBJECT_STORE_BUCKET"
OBJECT_STORE_REGION_ENV = "VINTED_RADAR_PLATFORM_OBJECT_STORE_REGION"
OBJECT_STORE_ACCESS_KEY_ENV = "VINTED_RADAR_PLATFORM_OBJECT_STORE_ACCESS_KEY"
OBJECT_STORE_SECRET_KEY_ENV = "VINTED_RADAR_PLATFORM_OBJECT_STORE_SECRET_KEY"
OBJECT_STORE_PREFIX_ENV = "VINTED_RADAR_PLATFORM_OBJECT_STORE_PREFIX"
RAW_EVENTS_PREFIX_ENV = "VINTED_RADAR_PLATFORM_RAW_EVENTS_PREFIX"
MANIFESTS_PREFIX_ENV = "VINTED_RADAR_PLATFORM_MANIFESTS_PREFIX"
PARQUET_PREFIX_ENV = "VINTED_RADAR_PLATFORM_PARQUET_PREFIX"
ARCHIVES_PREFIX_ENV = "VINTED_RADAR_PLATFORM_ARCHIVES_PREFIX"
POSTGRES_SCHEMA_VERSION_ENV = "VINTED_RADAR_PLATFORM_POSTGRES_SCHEMA_VERSION"
CLICKHOUSE_SCHEMA_VERSION_ENV = "VINTED_RADAR_PLATFORM_CLICKHOUSE_SCHEMA_VERSION"
EVENT_SCHEMA_VERSION_ENV = "VINTED_RADAR_PLATFORM_EVENT_SCHEMA_VERSION"
MANIFEST_SCHEMA_VERSION_ENV = "VINTED_RADAR_PLATFORM_MANIFEST_SCHEMA_VERSION"
ENABLE_POSTGRES_WRITES_ENV = "VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES"
ENABLE_CLICKHOUSE_WRITES_ENV = "VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES"
ENABLE_OBJECT_STORAGE_WRITES_ENV = "VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES"
ENABLE_POLYGLOT_READS_ENV = "VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS"
POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_BOOTSTRAP_AUDIT_RETENTION_DAYS"
POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_OUTBOX_DELIVERED_RETENTION_DAYS"
POSTGRES_OUTBOX_FAILED_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_OUTBOX_FAILED_RETENTION_DAYS"
POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_RUNTIME_CYCLES_RETENTION_DAYS"
OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_RAW_EVENTS_RETENTION_DAYS"
OBJECT_STORE_MANIFESTS_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_MANIFESTS_RETENTION_DAYS"
OBJECT_STORE_PARQUET_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_PARQUET_RETENTION_DAYS"
OBJECT_STORE_ARCHIVES_RETENTION_DAYS_ENV = "VINTED_RADAR_PLATFORM_ARCHIVES_RETENTION_DAYS"
OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS_ENV = "VINTED_RADAR_PLATFORM_RAW_EVENTS_RETENTION_CLASS"
OBJECT_STORE_MANIFESTS_RETENTION_CLASS_ENV = "VINTED_RADAR_PLATFORM_MANIFESTS_RETENTION_CLASS"
OBJECT_STORE_PARQUET_RETENTION_CLASS_ENV = "VINTED_RADAR_PLATFORM_PARQUET_RETENTION_CLASS"
OBJECT_STORE_ARCHIVES_RETENTION_CLASS_ENV = "VINTED_RADAR_PLATFORM_ARCHIVES_RETENTION_CLASS"

DEFAULT_POSTGRES_DSN = "postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"
DEFAULT_CLICKHOUSE_URL = "http://127.0.0.1:8123"
DEFAULT_CLICKHOUSE_DATABASE = "vinted_radar"
DEFAULT_CLICKHOUSE_USERNAME = "default"
DEFAULT_CLICKHOUSE_PASSWORD = ""
DEFAULT_OBJECT_STORE_ENDPOINT = "http://127.0.0.1:9000"
DEFAULT_OBJECT_STORE_BUCKET = "vinted-radar"
DEFAULT_OBJECT_STORE_REGION = "us-east-1"
DEFAULT_OBJECT_STORE_ACCESS_KEY = "minioadmin"
DEFAULT_OBJECT_STORE_SECRET_KEY = "minioadmin"
DEFAULT_OBJECT_STORE_PREFIX = "vinted-radar"
DEFAULT_RAW_EVENTS_PREFIX_SUFFIX = "events/raw"
DEFAULT_MANIFESTS_PREFIX_SUFFIX = "manifests"
DEFAULT_PARQUET_PREFIX_SUFFIX = "parquet"
DEFAULT_ARCHIVES_PREFIX_SUFFIX = "archives"
DEFAULT_POSTGRES_SCHEMA_VERSION = POSTGRES_MUTABLE_SCHEMA_VERSION
DEFAULT_CLICKHOUSE_SCHEMA_VERSION = CLICKHOUSE_SERVING_SCHEMA_VERSION
DEFAULT_EVENT_SCHEMA_VERSION = 1
DEFAULT_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS = 30
DEFAULT_POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS = 14
DEFAULT_POSTGRES_OUTBOX_FAILED_RETENTION_DAYS = 30
DEFAULT_POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS = 90
DEFAULT_OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS = 730
DEFAULT_OBJECT_STORE_MANIFESTS_RETENTION_DAYS = 3650
DEFAULT_OBJECT_STORE_PARQUET_RETENTION_DAYS = 3650
DEFAULT_OBJECT_STORE_ARCHIVES_RETENTION_DAYS = 3650
DEFAULT_OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS = "transient-evidence"
DEFAULT_OBJECT_STORE_MANIFESTS_RETENTION_CLASS = "audit-manifest"
DEFAULT_OBJECT_STORE_PARQUET_RETENTION_CLASS = "warehouse"
DEFAULT_OBJECT_STORE_ARCHIVES_RETENTION_CLASS = "archive"
_SECRET_MASK = "***"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    dsn: str
    schema_version: int

    def as_redacted_dict(self) -> dict[str, object]:
        return {
            "dsn": redact_url_credentials(self.dsn),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class ClickHouseConfig:
    url: str
    database: str
    username: str
    password: str
    schema_version: int

    def as_redacted_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "database": self.database,
            "username": self.username,
            "password": _mask_secret(self.password),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class ObjectStorageConfig:
    endpoint_url: str
    bucket: str
    region: str
    access_key_id: str
    secret_access_key: str

    @property
    def secure(self) -> bool:
        return urlsplit(self.endpoint_url).scheme == "https"

    def as_redacted_dict(self) -> dict[str, object]:
        return {
            "endpoint_url": self.endpoint_url,
            "bucket": self.bucket,
            "region": self.region,
            "access_key_id": _mask_secret(self.access_key_id),
            "secret_access_key": _mask_secret(self.secret_access_key),
            "secure": self.secure,
        }


@dataclass(frozen=True, slots=True)
class StoragePrefixConfig:
    root: str
    raw_events: str
    manifests: str
    parquet: str
    archives: str

    def as_dict(self) -> dict[str, str]:
        return {
            "root": self.root,
            "raw_events": self.raw_events,
            "manifests": self.manifests,
            "parquet": self.parquet,
            "archives": self.archives,
        }


@dataclass(frozen=True, slots=True)
class PostgresLifecycleConfig:
    bootstrap_audit_retention_days: int
    delivered_outbox_retention_days: int
    failed_outbox_retention_days: int
    runtime_cycles_retention_days: int

    def as_dict(self) -> dict[str, int]:
        return {
            "bootstrap_audit_retention_days": self.bootstrap_audit_retention_days,
            "delivered_outbox_retention_days": self.delivered_outbox_retention_days,
            "failed_outbox_retention_days": self.failed_outbox_retention_days,
            "runtime_cycles_retention_days": self.runtime_cycles_retention_days,
        }


@dataclass(frozen=True, slots=True)
class ObjectStoreRetentionPolicy:
    retention_class: str
    retention_days: int

    def as_dict(self) -> dict[str, object]:
        return {
            "retention_class": self.retention_class,
            "retention_days": self.retention_days,
        }


@dataclass(frozen=True, slots=True)
class ObjectStorageLifecycleConfig:
    raw_events: ObjectStoreRetentionPolicy
    manifests: ObjectStoreRetentionPolicy
    parquet: ObjectStoreRetentionPolicy
    archives: ObjectStoreRetentionPolicy

    def as_dict(self) -> dict[str, object]:
        return {
            "raw_events": self.raw_events.as_dict(),
            "manifests": self.manifests.as_dict(),
            "parquet": self.parquet.as_dict(),
            "archives": self.archives.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    postgres: PostgresLifecycleConfig
    object_storage: ObjectStorageLifecycleConfig

    def as_dict(self) -> dict[str, object]:
        return {
            "postgres": self.postgres.as_dict(),
            "object_storage": self.object_storage.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class SchemaVersionConfig:
    postgres: int
    clickhouse: int
    events: int
    manifests: int

    def as_dict(self) -> dict[str, int]:
        return {
            "postgres": self.postgres,
            "clickhouse": self.clickhouse,
            "events": self.events,
            "manifests": self.manifests,
        }


@dataclass(frozen=True, slots=True)
class CutoverFlags:
    enable_postgres_writes: bool
    enable_clickhouse_writes: bool
    enable_object_storage_writes: bool
    enable_polyglot_reads: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "enable_postgres_writes": self.enable_postgres_writes,
            "enable_clickhouse_writes": self.enable_clickhouse_writes,
            "enable_object_storage_writes": self.enable_object_storage_writes,
            "enable_polyglot_reads": self.enable_polyglot_reads,
        }


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    postgres: PostgresConfig
    clickhouse: ClickHouseConfig
    object_storage: ObjectStorageConfig
    storage: StoragePrefixConfig
    lifecycle: LifecycleConfig
    schema_versions: SchemaVersionConfig
    cutover: CutoverFlags

    def as_redacted_dict(self) -> dict[str, object]:
        return {
            "postgres": self.postgres.as_redacted_dict(),
            "clickhouse": self.clickhouse.as_redacted_dict(),
            "object_storage": self.object_storage.as_redacted_dict(),
            "storage": self.storage.as_dict(),
            "lifecycle": self.lifecycle.as_dict(),
            "schema_versions": self.schema_versions.as_dict(),
            "cutover": self.cutover.as_dict(),
        }


def load_platform_config(env: Mapping[str, str] | None = None) -> PlatformConfig:
    environment = os.environ if env is None else env

    root_prefix = _read_storage_prefix(
        environment,
        OBJECT_STORE_PREFIX_ENV,
        default=DEFAULT_OBJECT_STORE_PREFIX,
    )
    raw_events_prefix = _read_storage_prefix(
        environment,
        RAW_EVENTS_PREFIX_ENV,
        default=f"{root_prefix}/{DEFAULT_RAW_EVENTS_PREFIX_SUFFIX}",
    )
    manifests_prefix = _read_storage_prefix(
        environment,
        MANIFESTS_PREFIX_ENV,
        default=f"{root_prefix}/{DEFAULT_MANIFESTS_PREFIX_SUFFIX}",
    )
    parquet_prefix = _read_storage_prefix(
        environment,
        PARQUET_PREFIX_ENV,
        default=f"{root_prefix}/{DEFAULT_PARQUET_PREFIX_SUFFIX}",
    )
    archives_prefix = _read_storage_prefix(
        environment,
        ARCHIVES_PREFIX_ENV,
        default=f"{root_prefix}/{DEFAULT_ARCHIVES_PREFIX_SUFFIX}",
    )

    postgres = PostgresConfig(
        dsn=_read_postgres_dsn(environment, POSTGRES_DSN_ENV, default=DEFAULT_POSTGRES_DSN),
        schema_version=_read_positive_int(
            environment,
            POSTGRES_SCHEMA_VERSION_ENV,
            default=DEFAULT_POSTGRES_SCHEMA_VERSION,
        ),
    )
    clickhouse = ClickHouseConfig(
        url=_read_http_url(environment, CLICKHOUSE_URL_ENV, default=DEFAULT_CLICKHOUSE_URL),
        database=_read_non_empty(environment, CLICKHOUSE_DATABASE_ENV, default=DEFAULT_CLICKHOUSE_DATABASE),
        username=_read_non_empty(environment, CLICKHOUSE_USERNAME_ENV, default=DEFAULT_CLICKHOUSE_USERNAME),
        password=_read_string(environment, CLICKHOUSE_PASSWORD_ENV, default=DEFAULT_CLICKHOUSE_PASSWORD),
        schema_version=_read_positive_int(
            environment,
            CLICKHOUSE_SCHEMA_VERSION_ENV,
            default=DEFAULT_CLICKHOUSE_SCHEMA_VERSION,
        ),
    )
    object_storage = ObjectStorageConfig(
        endpoint_url=_read_http_url(
            environment,
            OBJECT_STORE_ENDPOINT_ENV,
            default=DEFAULT_OBJECT_STORE_ENDPOINT,
        ),
        bucket=_read_bucket_name(environment, OBJECT_STORE_BUCKET_ENV, default=DEFAULT_OBJECT_STORE_BUCKET),
        region=_read_non_empty(environment, OBJECT_STORE_REGION_ENV, default=DEFAULT_OBJECT_STORE_REGION),
        access_key_id=_read_non_empty(
            environment,
            OBJECT_STORE_ACCESS_KEY_ENV,
            default=DEFAULT_OBJECT_STORE_ACCESS_KEY,
        ),
        secret_access_key=_read_non_empty(
            environment,
            OBJECT_STORE_SECRET_KEY_ENV,
            default=DEFAULT_OBJECT_STORE_SECRET_KEY,
        ),
    )
    lifecycle = LifecycleConfig(
        postgres=PostgresLifecycleConfig(
            bootstrap_audit_retention_days=_read_positive_int(
                environment,
                POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS_ENV,
                default=DEFAULT_POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS,
            ),
            delivered_outbox_retention_days=_read_positive_int(
                environment,
                POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS_ENV,
                default=DEFAULT_POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS,
            ),
            failed_outbox_retention_days=_read_positive_int(
                environment,
                POSTGRES_OUTBOX_FAILED_RETENTION_DAYS_ENV,
                default=DEFAULT_POSTGRES_OUTBOX_FAILED_RETENTION_DAYS,
            ),
            runtime_cycles_retention_days=_read_positive_int(
                environment,
                POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS_ENV,
                default=DEFAULT_POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS,
            ),
        ),
        object_storage=ObjectStorageLifecycleConfig(
            raw_events=ObjectStoreRetentionPolicy(
                retention_class=_read_non_empty(
                    environment,
                    OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS_ENV,
                    default=DEFAULT_OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS,
                ),
                retention_days=_read_positive_int(
                    environment,
                    OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS_ENV,
                    default=DEFAULT_OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS,
                ),
            ),
            manifests=ObjectStoreRetentionPolicy(
                retention_class=_read_non_empty(
                    environment,
                    OBJECT_STORE_MANIFESTS_RETENTION_CLASS_ENV,
                    default=DEFAULT_OBJECT_STORE_MANIFESTS_RETENTION_CLASS,
                ),
                retention_days=_read_positive_int(
                    environment,
                    OBJECT_STORE_MANIFESTS_RETENTION_DAYS_ENV,
                    default=DEFAULT_OBJECT_STORE_MANIFESTS_RETENTION_DAYS,
                ),
            ),
            parquet=ObjectStoreRetentionPolicy(
                retention_class=_read_non_empty(
                    environment,
                    OBJECT_STORE_PARQUET_RETENTION_CLASS_ENV,
                    default=DEFAULT_OBJECT_STORE_PARQUET_RETENTION_CLASS,
                ),
                retention_days=_read_positive_int(
                    environment,
                    OBJECT_STORE_PARQUET_RETENTION_DAYS_ENV,
                    default=DEFAULT_OBJECT_STORE_PARQUET_RETENTION_DAYS,
                ),
            ),
            archives=ObjectStoreRetentionPolicy(
                retention_class=_read_non_empty(
                    environment,
                    OBJECT_STORE_ARCHIVES_RETENTION_CLASS_ENV,
                    default=DEFAULT_OBJECT_STORE_ARCHIVES_RETENTION_CLASS,
                ),
                retention_days=_read_positive_int(
                    environment,
                    OBJECT_STORE_ARCHIVES_RETENTION_DAYS_ENV,
                    default=DEFAULT_OBJECT_STORE_ARCHIVES_RETENTION_DAYS,
                ),
            ),
        ),
    )
    schema_versions = SchemaVersionConfig(
        postgres=postgres.schema_version,
        clickhouse=clickhouse.schema_version,
        events=_read_positive_int(
            environment,
            EVENT_SCHEMA_VERSION_ENV,
            default=DEFAULT_EVENT_SCHEMA_VERSION,
        ),
        manifests=_read_positive_int(
            environment,
            MANIFEST_SCHEMA_VERSION_ENV,
            default=DEFAULT_MANIFEST_SCHEMA_VERSION,
        ),
    )
    cutover = CutoverFlags(
        enable_postgres_writes=_read_bool(environment, ENABLE_POSTGRES_WRITES_ENV, default=False),
        enable_clickhouse_writes=_read_bool(environment, ENABLE_CLICKHOUSE_WRITES_ENV, default=False),
        enable_object_storage_writes=_read_bool(
            environment,
            ENABLE_OBJECT_STORAGE_WRITES_ENV,
            default=False,
        ),
        enable_polyglot_reads=_read_bool(environment, ENABLE_POLYGLOT_READS_ENV, default=False),
    )

    return PlatformConfig(
        postgres=postgres,
        clickhouse=clickhouse,
        object_storage=object_storage,
        storage=StoragePrefixConfig(
            root=root_prefix,
            raw_events=raw_events_prefix,
            manifests=manifests_prefix,
            parquet=parquet_prefix,
            archives=archives_prefix,
        ),
        lifecycle=lifecycle,
        schema_versions=schema_versions,
        cutover=cutover,
    )


def redact_url_credentials(value: str) -> str:
    parts = urlsplit(value)
    if parts.username is None and parts.password is None:
        return value
    host = parts.hostname or "unknown"
    port = f":{parts.port}" if parts.port is not None else ""
    return urlunsplit((parts.scheme, f"{_SECRET_MASK}@{host}{port}", parts.path, parts.query, parts.fragment))


def _read_postgres_dsn(environment: Mapping[str, str], name: str, *, default: str) -> str:
    value = _read_string(environment, name, default=default)
    parts = urlsplit(value)
    if parts.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"{name} must use postgres:// or postgresql://")
    if not parts.hostname:
        raise ValueError(f"{name} must include a hostname")
    database_name = parts.path.lstrip("/")
    if not database_name:
        raise ValueError(f"{name} must include a database name in the path")
    return value


def _read_http_url(environment: Mapping[str, str], name: str, *, default: str) -> str:
    value = _read_string(environment, name, default=default)
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        raise ValueError(f"{name} must use http:// or https://")
    if not parts.hostname:
        raise ValueError(f"{name} must include a hostname")
    return value


def _read_bucket_name(environment: Mapping[str, str], name: str, *, default: str) -> str:
    value = _read_non_empty(environment, name, default=default)
    if not _BUCKET_RE.match(value):
        raise ValueError(f"{name} must be a valid S3 bucket name")
    return value


def _read_storage_prefix(environment: Mapping[str, str], name: str, *, default: str) -> str:
    value = _read_non_empty(environment, name, default=default)
    return normalize_storage_prefix(value, env_name=name)


def normalize_storage_prefix(value: str, *, env_name: str = "storage prefix") -> str:
    candidate = str(value).replace("\\", "/").strip().strip("/")
    segments = [segment.strip() for segment in candidate.split("/") if segment.strip()]
    if not segments:
        raise ValueError(f"{env_name} cannot be empty")
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError(f"{env_name} cannot contain '.' or '..' segments")
    return "/".join(segments)


def _read_positive_int(environment: Mapping[str, str], name: str, *, default: int) -> int:
    raw_value = _read_string(environment, name, default=str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def _read_bool(environment: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw_value = _read_string(environment, name, default="true" if default else "false")
    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be one of: 1, 0, true, false, yes, no, on, off")


def _read_non_empty(environment: Mapping[str, str], name: str, *, default: str) -> str:
    value = _read_string(environment, name, default=default).strip()
    if not value:
        raise ValueError(f"{name} cannot be empty")
    return value


def _read_string(environment: Mapping[str, str], name: str, *, default: str) -> str:
    if name not in environment:
        return default
    return str(environment[name])


def _mask_secret(value: str) -> str:
    return "" if not value else _SECRET_MASK


__all__ = [
    "ARCHIVES_PREFIX_ENV",
    "CLICKHOUSE_DATABASE_ENV",
    "CLICKHOUSE_PASSWORD_ENV",
    "CLICKHOUSE_SCHEMA_VERSION_ENV",
    "CLICKHOUSE_URL_ENV",
    "CLICKHOUSE_USERNAME_ENV",
    "CutoverFlags",
    "ENABLE_CLICKHOUSE_WRITES_ENV",
    "ENABLE_OBJECT_STORAGE_WRITES_ENV",
    "ENABLE_POLYGLOT_READS_ENV",
    "ENABLE_POSTGRES_WRITES_ENV",
    "EVENT_SCHEMA_VERSION_ENV",
    "LifecycleConfig",
    "MANIFESTS_PREFIX_ENV",
    "MANIFEST_SCHEMA_VERSION_ENV",
    "OBJECT_STORE_ACCESS_KEY_ENV",
    "OBJECT_STORE_ARCHIVES_RETENTION_CLASS_ENV",
    "OBJECT_STORE_ARCHIVES_RETENTION_DAYS_ENV",
    "OBJECT_STORE_BUCKET_ENV",
    "OBJECT_STORE_ENDPOINT_ENV",
    "OBJECT_STORE_MANIFESTS_RETENTION_CLASS_ENV",
    "OBJECT_STORE_MANIFESTS_RETENTION_DAYS_ENV",
    "OBJECT_STORE_PARQUET_RETENTION_CLASS_ENV",
    "OBJECT_STORE_PARQUET_RETENTION_DAYS_ENV",
    "OBJECT_STORE_PREFIX_ENV",
    "OBJECT_STORE_RAW_EVENTS_RETENTION_CLASS_ENV",
    "OBJECT_STORE_RAW_EVENTS_RETENTION_DAYS_ENV",
    "OBJECT_STORE_REGION_ENV",
    "OBJECT_STORE_SECRET_KEY_ENV",
    "ObjectStorageConfig",
    "ObjectStorageLifecycleConfig",
    "ObjectStoreRetentionPolicy",
    "PARQUET_PREFIX_ENV",
    "POSTGRES_BOOTSTRAP_AUDIT_RETENTION_DAYS_ENV",
    "POSTGRES_DSN_ENV",
    "POSTGRES_OUTBOX_DELIVERED_RETENTION_DAYS_ENV",
    "POSTGRES_OUTBOX_FAILED_RETENTION_DAYS_ENV",
    "POSTGRES_RUNTIME_CYCLES_RETENTION_DAYS_ENV",
    "POSTGRES_SCHEMA_VERSION_ENV",
    "PlatformConfig",
    "PostgresLifecycleConfig",
    "RAW_EVENTS_PREFIX_ENV",
    "SchemaVersionConfig",
    "StoragePrefixConfig",
    "load_platform_config",
    "normalize_storage_prefix",
    "redact_url_credentials",
]
