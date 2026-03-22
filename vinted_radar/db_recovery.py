from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from vinted_radar.db import connect_database
from vinted_radar.db_health import CRITICAL_TABLES, inspect_sqlite_database

RECOVERY_TABLE_ORDER = tuple(CRITICAL_TABLES)


def recover_partial_database(
    source_db: str | Path,
    destination_db: str | Path,
    *,
    include_integrity_check: bool = False,
    force: bool = False,
    batch_size: int = 1000,
    candidate_tables: Iterable[str] = RECOVERY_TABLE_ORDER,
) -> dict[str, object]:
    source_path = Path(source_db)
    destination_path = Path(destination_db)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _build_sidecar_path(destination_path, marker="recovering")

    if destination_path.exists() and not force:
        raise FileExistsError(f"Destination already exists: {destination_path}")
    if temp_path.exists():
        temp_path.unlink()

    source_health = inspect_sqlite_database(source_path, include_integrity_check=include_integrity_check, probe_tables=True)
    if not source_health.get("exists"):
        raise FileNotFoundError(f"Source database not found: {source_path}")
    if source_health.get("open_error"):
        raise sqlite3.DatabaseError(str(source_health["open_error"]))

    table_health = {str(table["table"]): table for table in list(source_health.get("tables") or [])}
    requested_tables = [table_name for table_name in candidate_tables if table_name in RECOVERY_TABLE_ORDER]
    recovered_tables: list[dict[str, object]] = []
    skipped_tables: list[dict[str, object]] = []

    source_connection = sqlite3.connect(str(source_path), timeout=30.0)
    source_connection.row_factory = sqlite3.Row
    destination_connection = connect_database(temp_path)
    destination_connection.execute("PRAGMA foreign_keys = OFF")

    try:
        for table_name in requested_tables:
            health = table_health.get(table_name)
            if health is None:
                skipped_tables.append({"table": table_name, "reason": "missing from health report"})
                continue
            if not bool(health.get("exists")):
                skipped_tables.append({"table": table_name, "reason": "table missing in source"})
                continue
            if not bool(health.get("count_ok")) or not bool(health.get("sample_ok")):
                skipped_tables.append(
                    {
                        "table": table_name,
                        "reason": health.get("count_error") or health.get("sample_error") or "table failed health probe",
                    }
                )
                continue
            try:
                imported_rows = _copy_table(
                    source_connection,
                    destination_connection,
                    table_name,
                    batch_size=batch_size,
                )
            except sqlite3.Error as exc:
                destination_connection.execute(f'DELETE FROM {_quote_identifier(table_name)}')
                destination_connection.commit()
                skipped_tables.append({"table": table_name, "reason": f"copy failed: {type(exc).__name__}: {exc}"})
                continue
            recovered_tables.append({"table": table_name, "imported_rows": imported_rows})
    finally:
        destination_connection.execute("PRAGMA foreign_keys = ON")
        destination_connection.close()
        source_connection.close()

    destination_health = inspect_sqlite_database(temp_path, include_integrity_check=False, probe_tables=True)
    report = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_db": str(source_path),
        "destination_db": str(destination_path),
        "temporary_db": str(temp_path),
        "source_health": source_health,
        "destination_health": destination_health,
        "recovered_tables": recovered_tables,
        "skipped_tables": skipped_tables,
        "recovery_mode": "partial-copy-of-healthy-tables",
        "notes": [
            "Skipped tables remained empty in the recovered database so operator tooling can open the file without structural corruption.",
            "Foreign-key completeness is not guaranteed when structurally healthy child tables depend on skipped parent tables.",
        ],
    }

    if not destination_health.get("healthy"):
        rejected_path = _build_sidecar_path(destination_path, marker=f"rejected-{_timestamp()}")
        temp_path.replace(rejected_path)
        report["temporary_db"] = str(rejected_path)
        report["promoted"] = False
        report["rejected_db"] = str(rejected_path)
        return report

    if destination_path.exists():
        destination_path.unlink()
    temp_path.replace(destination_path)
    report["temporary_db"] = None
    report["promoted"] = True
    return report



def write_recovery_report(report: dict[str, object], report_path: str | Path) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path



def _copy_table(
    source_connection: sqlite3.Connection,
    destination_connection: sqlite3.Connection,
    table_name: str,
    *,
    batch_size: int,
) -> int:
    quoted_table = _quote_identifier(table_name)
    columns = _table_columns(source_connection, table_name)
    if not columns:
        return 0
    quoted_columns = ", ".join(_quote_identifier(column_name) for column_name in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})"
    select_sql = f"SELECT {quoted_columns} FROM {quoted_table}"

    imported_rows = 0
    cursor = source_connection.execute(select_sql)
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        destination_connection.executemany(insert_sql, [tuple(row) for row in rows])
        destination_connection.commit()
        imported_rows += len(rows)
    return imported_rows



def _table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f'PRAGMA table_info({_quote_identifier(table_name)})').fetchall()
    return [str(row[1]) for row in rows]



def _build_sidecar_path(path: Path, *, marker: str) -> Path:
    suffix = path.suffix or ".db"
    stem = path.name[:-len(suffix)] if path.suffix else path.name
    return path.with_name(f"{stem}.{marker}{suffix}")



def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'



def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
