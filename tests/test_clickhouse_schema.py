from __future__ import annotations

import re

from vinted_radar.platform.clickhouse_schema import (
    CLICKHOUSE_ALL_TABLES,
    CLICKHOUSE_FACT_TABLES,
    CLICKHOUSE_MATERIALIZED_VIEWS,
    CLICKHOUSE_ROLLUP_TABLES,
    CLICKHOUSE_SERVING_SCHEMA_VERSION,
    CLICKHOUSE_SERVING_TABLES,
)
from vinted_radar.platform.migrations import clickhouse_migrations_dir, run_versioned_migrations


class FakeQueryResult:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self._rows = rows or []

    @property
    def result_rows(self):
        return [list(row) for row in self._rows]


class RecordingClickHouseClient:
    def __init__(self) -> None:
        self.database_exists = False
        self.migration_table_exists = False
        self.applied_versions: dict[int, str] = {}
        self.command_log: list[str] = []
        self.created_tables: dict[str, str] = {}
        self.created_views: dict[str, str] = {}

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
        table_match = re.match(r"CREATE TABLE IF NOT EXISTS ([A-Za-z0-9_]+) ", normalized)
        if table_match is not None:
            self.created_tables[table_match.group(1)] = normalized
            return None
        view_match = re.match(r"CREATE MATERIALIZED VIEW IF NOT EXISTS ([A-Za-z0-9_]+) TO ([A-Za-z0-9_]+) ", normalized)
        if view_match is not None:
            self.created_views[view_match.group(1)] = normalized
            return None
        return None

    def query(self, sql: str) -> FakeQueryResult:
        normalized = " ".join(sql.split())
        self.command_log.append(normalized)
        if normalized.startswith("SELECT version, checksum FROM vinted_radar.platform_schema_migrations"):
            rows = [(version, checksum) for version, checksum in sorted(self.applied_versions.items())]
            return FakeQueryResult(rows)
        return FakeQueryResult()


class RecordingMigrationBackend:
    def __init__(self, client: RecordingClickHouseClient) -> None:
        self.client = client

    def fetch_applied_versions(self, *, create_if_missing: bool):
        if not self.client.database_exists:
            if not create_if_missing:
                return {}
            self.client.command("CREATE DATABASE IF NOT EXISTS vinted_radar")
        if not self.client.migration_table_exists:
            if not create_if_missing:
                return {}
            self.client.command(
                """
                CREATE TABLE IF NOT EXISTS vinted_radar.platform_schema_migrations (
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
            "SELECT version, checksum FROM vinted_radar.platform_schema_migrations ORDER BY version"
        ).result_rows
        return {int(row[0]): str(row[1]) for row in rows}

    def apply_migration(self, migration) -> None:
        for statement in [part.strip() for part in migration.sql.split(";") if part.strip()]:
            self.client.command(statement)
        self.client.command(
            f"INSERT INTO vinted_radar.platform_schema_migrations (version, name, checksum) VALUES ({migration.version}, '{migration.name}', '{migration.checksum}')"
        )


def test_clickhouse_serving_schema_migration_applies_v002_tables_and_materialized_views() -> None:
    client = RecordingClickHouseClient()
    result = run_versioned_migrations(
        backend=RecordingMigrationBackend(client),
        directory=clickhouse_migrations_dir(),
        expected_version=CLICKHOUSE_SERVING_SCHEMA_VERSION,
        apply=True,
    )

    assert result.healthy is True
    assert result.current_version == CLICKHOUSE_SERVING_SCHEMA_VERSION
    assert result.applied_this_run == (1, 2)
    for table_name in CLICKHOUSE_ALL_TABLES:
        assert table_name in client.created_tables
    for view_name in CLICKHOUSE_MATERIALIZED_VIEWS:
        assert view_name in client.created_views


def test_clickhouse_serving_schema_v002_defines_fact_ttl_rollups_and_latest_serving_primitives() -> None:
    migration_sql = (clickhouse_migrations_dir() / "V002__serving_warehouse.sql").read_text(encoding="utf-8")

    for table_name in CLICKHOUSE_FACT_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration_sql
    for table_name in CLICKHOUSE_ROLLUP_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration_sql
    for table_name in CLICKHOUSE_SERVING_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration_sql
    for view_name in CLICKHOUSE_MATERIALIZED_VIEWS:
        assert f"CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name}" in migration_sql

    assert "TTL toDateTime(observed_at) + INTERVAL 730 DAY" in migration_sql
    assert "TTL toDateTime(probed_at) + INTERVAL 730 DAY" in migration_sql
    assert "TTL toDateTime(occurred_at) + INTERVAL 730 DAY" in migration_sql
    assert "allow_nullable_key = 1" in migration_sql
    assert "sumState(toInt64(ifNull(price_amount_cents, 0))) AS price_sum_state" in migration_sql
    assert "sumState(toUInt64(price_amount_cents IS NOT NULL)) AS price_count_state" in migration_sql
    assert "LowCardinality(Nullable(String))" in migration_sql
    assert "TTL bucket_start + INTERVAL 3650 DAY" in migration_sql
    assert "TTL bucket_date + INTERVAL 3650 DAY" in migration_sql
    assert "ENGINE = AggregatingMergeTree" in migration_sql
    assert "ENGINE = ReplacingMergeTree(version_token)" in migration_sql
    assert "uniqExactState(listing_id) AS unique_listing_state" in migration_sql
    assert "toStartOfHour(observed_at) AS bucket_start" in migration_sql
    assert "toDate(observed_at) AS bucket_date" in migration_sql
    assert "TO rollup_category_daily" in migration_sql
    assert "TO rollup_brand_daily" in migration_sql
    assert "TO serving_listing_latest_seen" in migration_sql
    assert "TO serving_listing_latest_probe" in migration_sql
    assert "TO serving_listing_latest_change" in migration_sql
