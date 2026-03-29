from __future__ import annotations

import pytest

from vinted_radar.platform.config import (
    CLICKHOUSE_PASSWORD_ENV,
    CLICKHOUSE_SCHEMA_VERSION_ENV,
    ENABLE_CLICKHOUSE_WRITES_ENV,
    ENABLE_OBJECT_STORAGE_WRITES_ENV,
    ENABLE_POLYGLOT_READS_ENV,
    ENABLE_POSTGRES_WRITES_ENV,
    EVENT_SCHEMA_VERSION_ENV,
    MANIFESTS_PREFIX_ENV,
    OBJECT_STORE_ACCESS_KEY_ENV,
    OBJECT_STORE_PREFIX_ENV,
    OBJECT_STORE_SECRET_KEY_ENV,
    PARQUET_PREFIX_ENV,
    POSTGRES_DSN_ENV,
    POSTGRES_SCHEMA_VERSION_ENV,
    RAW_EVENTS_PREFIX_ENV,
    load_platform_config,
)


def test_load_platform_config_uses_local_platform_defaults() -> None:
    config = load_platform_config(env={})

    assert config.postgres.dsn == "postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar"
    assert config.postgres.schema_version == 3
    assert config.clickhouse.url == "http://127.0.0.1:8123"
    assert config.clickhouse.database == "vinted_radar"
    assert config.object_storage.endpoint_url == "http://127.0.0.1:9000"
    assert config.object_storage.bucket == "vinted-radar"
    assert config.object_storage.secure is False
    assert config.storage.root == "vinted-radar"
    assert config.storage.raw_events == "vinted-radar/events/raw"
    assert config.storage.manifests == "vinted-radar/manifests"
    assert config.storage.parquet == "vinted-radar/parquet"
    assert config.schema_versions.as_dict() == {
        "postgres": 3,
        "clickhouse": 1,
        "events": 1,
        "manifests": 1,
    }
    assert config.cutover.as_dict() == {
        "enable_postgres_writes": False,
        "enable_clickhouse_writes": False,
        "enable_object_storage_writes": False,
        "enable_polyglot_reads": False,
    }


def test_load_platform_config_normalizes_prefixes_and_redacts_sensitive_fields() -> None:
    env = {
        POSTGRES_DSN_ENV: "postgresql://writer:secret@db.example:5432/radar",
        CLICKHOUSE_PASSWORD_ENV: "click-secret",
        OBJECT_STORE_ACCESS_KEY_ENV: "minio-user",
        OBJECT_STORE_SECRET_KEY_ENV: "minio-secret",
        OBJECT_STORE_PREFIX_ENV: "/tenant-a//",
        RAW_EVENTS_PREFIX_ENV: "/tenant-a/events/raw/",
        MANIFESTS_PREFIX_ENV: "tenant-a//manifests/",
        PARQUET_PREFIX_ENV: "tenant-a\\warehouse\\",
        POSTGRES_SCHEMA_VERSION_ENV: "4",
        CLICKHOUSE_SCHEMA_VERSION_ENV: "7",
        EVENT_SCHEMA_VERSION_ENV: "5",
        ENABLE_POSTGRES_WRITES_ENV: "true",
        ENABLE_CLICKHOUSE_WRITES_ENV: "1",
        ENABLE_OBJECT_STORAGE_WRITES_ENV: "yes",
        ENABLE_POLYGLOT_READS_ENV: "on",
    }

    config = load_platform_config(env=env)
    redacted = config.as_redacted_dict()

    assert config.storage.root == "tenant-a"
    assert config.storage.raw_events == "tenant-a/events/raw"
    assert config.storage.manifests == "tenant-a/manifests"
    assert config.storage.parquet == "tenant-a/warehouse"
    assert config.schema_versions.as_dict() == {
        "postgres": 4,
        "clickhouse": 7,
        "events": 5,
        "manifests": 1,
    }
    assert config.cutover.as_dict() == {
        "enable_postgres_writes": True,
        "enable_clickhouse_writes": True,
        "enable_object_storage_writes": True,
        "enable_polyglot_reads": True,
    }
    assert redacted["postgres"] == {
        "dsn": "postgresql://***@db.example:5432/radar",
        "schema_version": 4,
    }
    assert redacted["clickhouse"]["password"] == "***"
    assert redacted["object_storage"]["access_key_id"] == "***"
    assert redacted["object_storage"]["secret_access_key"] == "***"


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({POSTGRES_DSN_ENV: "sqlite:///tmp/vinted.db"}, POSTGRES_DSN_ENV),
        ({POSTGRES_SCHEMA_VERSION_ENV: "0"}, POSTGRES_SCHEMA_VERSION_ENV),
        ({RAW_EVENTS_PREFIX_ENV: "../escape"}, RAW_EVENTS_PREFIX_ENV),
    ],
)
def test_load_platform_config_rejects_invalid_values(env: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_platform_config(env=env)
