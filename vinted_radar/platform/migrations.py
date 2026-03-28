from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Protocol

_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE_RE = re.compile(r"^V(?P<version>\d+)__(?P<name>[a-z0-9_]+)\.sql$")


@dataclass(frozen=True, slots=True)
class SqlMigration:
    version: int
    name: str
    path: Path
    sql: str
    checksum: str

    @property
    def file_name(self) -> str:
        return self.path.name


@dataclass(frozen=True, slots=True)
class MigrationRunResult:
    expected_version: int
    available_version: int
    current_version: int
    applied_versions: tuple[int, ...]
    pending_versions: tuple[int, ...]
    applied_this_run: tuple[int, ...]
    unexpected_versions: tuple[int, ...]
    mismatched_checksums: tuple[int, ...]
    healthy: bool


class MigrationBackend(Protocol):
    def fetch_applied_versions(self, *, create_if_missing: bool) -> Mapping[int, str]: ...

    def apply_migration(self, migration: SqlMigration) -> None: ...


def project_root(root: Path | None = None) -> Path:
    return _DEFAULT_PROJECT_ROOT if root is None else Path(root)


def postgres_migrations_dir(root: Path | None = None) -> Path:
    return project_root(root) / "infra" / "postgres" / "migrations"


def clickhouse_migrations_dir(root: Path | None = None) -> Path:
    return project_root(root) / "infra" / "clickhouse" / "migrations"


def load_sql_migrations(directory: str | Path) -> tuple[SqlMigration, ...]:
    migration_dir = Path(directory)
    if not migration_dir.exists():
        raise FileNotFoundError(f"Migration directory does not exist: {migration_dir}")
    if not migration_dir.is_dir():
        raise ValueError(f"Migration path is not a directory: {migration_dir}")

    discovered: list[SqlMigration] = []
    for path in sorted(migration_dir.glob("*.sql")):
        match = _MIGRATION_FILE_RE.fullmatch(path.name)
        if match is None:
            raise ValueError(
                f"Invalid migration filename '{path.name}' in {migration_dir}. Expected V###__name.sql."
            )
        sql = path.read_text(encoding="utf-8").strip()
        if not sql:
            raise ValueError(f"Migration file is empty: {path}")
        discovered.append(
            SqlMigration(
                version=int(match.group("version")),
                name=match.group("name"),
                path=path,
                sql=sql,
                checksum=sha256(sql.encode("utf-8")).hexdigest(),
            )
        )

    if not discovered:
        raise ValueError(f"No SQL migrations found in {migration_dir}")

    versions = [migration.version for migration in discovered]
    if len(set(versions)) != len(versions):
        raise ValueError(f"Duplicate migration versions found in {migration_dir}")

    expected_version = 1
    for migration in discovered:
        if migration.version != expected_version:
            raise ValueError(
                f"Expected migration version V{expected_version:03d} in {migration_dir}, found V{migration.version:03d}"
            )
        expected_version += 1

    return tuple(discovered)


def run_versioned_migrations(
    *,
    backend: MigrationBackend,
    directory: str | Path,
    expected_version: int,
    apply: bool,
) -> MigrationRunResult:
    if expected_version < 1:
        raise ValueError(f"expected_version must be >= 1, got {expected_version}")

    migrations = load_sql_migrations(directory)
    available_version = migrations[-1].version
    if available_version < expected_version:
        raise ValueError(
            f"Expected schema version {expected_version}, but only {available_version} migration(s) exist in {directory}"
        )

    applied_versions = {
        int(version): str(checksum)
        for version, checksum in dict(backend.fetch_applied_versions(create_if_missing=apply)).items()
    }
    migration_by_version = {migration.version: migration for migration in migrations}
    mismatched_checksums = tuple(
        sorted(
            version
            for version, checksum in applied_versions.items()
            if version in migration_by_version and migration_by_version[version].checksum != checksum
        )
    )
    if apply and mismatched_checksums:
        versions = ", ".join(f"V{version:03d}" for version in mismatched_checksums)
        raise ValueError(f"Stored migration checksums do not match local SQL for {versions}")

    pending_migrations = tuple(
        migration
        for migration in migrations
        if migration.version <= expected_version and migration.version not in applied_versions
    )
    applied_this_run: list[int] = []
    if apply:
        for migration in pending_migrations:
            backend.apply_migration(migration)
            applied_this_run.append(migration.version)
        applied_versions = {
            int(version): str(checksum)
            for version, checksum in dict(backend.fetch_applied_versions(create_if_missing=False)).items()
        }
        mismatched_checksums = tuple(
            sorted(
                version
                for version, checksum in applied_versions.items()
                if version in migration_by_version and migration_by_version[version].checksum != checksum
            )
        )

    pending_versions = tuple(
        migration.version
        for migration in migrations
        if migration.version <= expected_version and migration.version not in applied_versions
    )
    applied_version_tuple = tuple(sorted(applied_versions))
    current_version = max(applied_version_tuple, default=0)
    unexpected_versions = tuple(sorted(version for version in applied_versions if version > expected_version))
    healthy = (
        available_version >= expected_version
        and current_version == expected_version
        and not pending_versions
        and not unexpected_versions
        and not mismatched_checksums
    )
    return MigrationRunResult(
        expected_version=expected_version,
        available_version=available_version,
        current_version=current_version,
        applied_versions=applied_version_tuple,
        pending_versions=pending_versions,
        applied_this_run=tuple(applied_this_run),
        unexpected_versions=unexpected_versions,
        mismatched_checksums=mismatched_checksums,
        healthy=healthy,
    )


def iter_sql_statements(sql: str) -> tuple[str, ...]:
    return tuple(statement.strip() for statement in sql.split(";") if statement.strip())


__all__ = [
    "MigrationBackend",
    "MigrationRunResult",
    "SqlMigration",
    "clickhouse_migrations_dir",
    "iter_sql_statements",
    "load_sql_migrations",
    "postgres_migrations_dir",
    "project_root",
    "run_versioned_migrations",
]
