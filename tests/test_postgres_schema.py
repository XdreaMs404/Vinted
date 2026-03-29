from __future__ import annotations

import re

from vinted_radar.platform.migrations import postgres_migrations_dir, run_versioned_migrations
from vinted_radar.platform.postgres_schema import (
    POSTGRES_MUTABLE_INDEXES,
    POSTGRES_MUTABLE_SCHEMA_VERSION,
    POSTGRES_MUTABLE_TABLES,
)


class FakeQueryResult:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class RecordingPostgresConnection:
    def __init__(self) -> None:
        self.migration_table_exists = False
        self.applied_versions: dict[int, str] = {}
        self.executed_sql: list[str] = []
        self.created_tables: dict[str, str] = {}
        self.created_indexes: dict[str, str] = {}
        self.commits = 0
        self.rollbacks = 0

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
        table_match = re.match(r"CREATE TABLE IF NOT EXISTS ([A-Za-z0-9_]+) ", normalized)
        if table_match is not None:
            self.created_tables[table_match.group(1)] = normalized
            return FakeQueryResult()
        index_match = re.match(r"CREATE INDEX IF NOT EXISTS ([A-Za-z0-9_]+) ON ([A-Za-z0-9_]+) ", normalized)
        if index_match is not None:
            self.created_indexes[index_match.group(1)] = normalized
            return FakeQueryResult()
        return FakeQueryResult()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RecordingMigrationBackend:
    def __init__(self, connection: RecordingPostgresConnection) -> None:
        self.connection = connection

    def fetch_applied_versions(self, *, create_if_missing: bool):
        exists = self.connection.migration_table_exists
        if not exists:
            if not create_if_missing:
                return {}
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            self.connection.commit()
        rows = self.connection.execute(
            "SELECT version, checksum FROM platform_schema_migrations ORDER BY version"
        ).fetchall()
        return {int(row[0]): str(row[1]) for row in rows}

    def apply_migration(self, migration) -> None:
        try:
            for statement in [part.strip() for part in migration.sql.split(";") if part.strip()]:
                self.connection.execute(statement)
            self.connection.execute(
                "INSERT INTO platform_schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise


def test_postgres_mutable_schema_migration_applies_v003_tables_and_indexes() -> None:
    connection = RecordingPostgresConnection()
    result = run_versioned_migrations(
        backend=RecordingMigrationBackend(connection),
        directory=postgres_migrations_dir(),
        expected_version=POSTGRES_MUTABLE_SCHEMA_VERSION,
        apply=True,
    )

    assert result.healthy is True
    assert result.current_version == POSTGRES_MUTABLE_SCHEMA_VERSION
    assert result.applied_this_run == (1, 2, 3)
    for table_name in POSTGRES_MUTABLE_TABLES:
        assert table_name in connection.created_tables
    for index_name in POSTGRES_MUTABLE_INDEXES:
        assert index_name in connection.created_indexes


def test_postgres_mutable_schema_uses_natural_keys_and_projector_checkpoints() -> None:
    migration_sql = (postgres_migrations_dir() / "V003__platform_mutable_truth.sql").read_text(encoding="utf-8")

    assert "manifest_id TEXT PRIMARY KEY REFERENCES platform_evidence_manifests(manifest_id) ON DELETE CASCADE" in migration_sql
    assert "event_id TEXT NOT NULL UNIQUE REFERENCES platform_events(event_id) ON DELETE CASCADE" in migration_sql
    assert "controller_id INTEGER PRIMARY KEY CHECK (controller_id = 1)" in migration_sql
    assert "listing_id BIGINT PRIMARY KEY REFERENCES platform_listing_identity(listing_id) ON DELETE CASCADE" in migration_sql
    assert "PRIMARY KEY (consumer_name, sink)" in migration_sql
    assert "last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL" in migration_sql
    assert "idx_platform_listing_current_state_state_confidence" in migration_sql
    assert "idx_platform_listing_presence_summary_bucket_time" in migration_sql
    assert "idx_platform_outbox_checkpoints_outbox_id" in migration_sql
