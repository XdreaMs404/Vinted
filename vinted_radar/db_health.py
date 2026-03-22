from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

CRITICAL_TABLES = (
    "discovery_runs",
    "catalogs",
    "catalog_scans",
    "listings",
    "listing_discoveries",
    "listing_observations",
    "item_page_probes",
    "runtime_cycles",
)
_CHECK_MESSAGE_LIMIT = 20


def inspect_sqlite_database(
    db_path: str | Path,
    *,
    include_integrity_check: bool = False,
    probe_tables: bool = True,
    tables: Iterable[str] = CRITICAL_TABLES,
) -> dict[str, object]:
    path = Path(db_path)
    report: dict[str, object] = {
        "db_path": str(path),
        "exists": path.exists(),
        "size_bytes": None,
        "open_error": None,
        "schema_table_count": None,
        "schema_error": None,
        "checks": {},
        "tables": [],
        "healthy": False,
    }
    if not path.exists():
        return report

    report["size_bytes"] = path.stat().st_size
    try:
        connection = sqlite3.connect(str(path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
    except sqlite3.Error as exc:
        report["open_error"] = _format_error(exc)
        return report

    try:
        try:
            row = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()
            report["schema_table_count"] = None if row is None else int(row[0])
        except sqlite3.Error as exc:
            report["schema_error"] = _format_error(exc)

        checks = dict(report["checks"])
        checks["quick_check"] = _run_pragma_check(connection, "quick_check")
        if include_integrity_check:
            checks["integrity_check"] = _run_pragma_check(connection, "integrity_check")
        report["checks"] = checks

        if probe_tables:
            report["tables"] = [_probe_table(connection, table_name) for table_name in tables]
    finally:
        connection.close()

    report["healthy"] = _is_healthy(report, probe_tables=probe_tables)
    return report


def _run_pragma_check(connection: sqlite3.Connection, pragma_name: str) -> dict[str, object]:
    try:
        cursor = connection.execute(f"PRAGMA {pragma_name}")
        messages = [str(row[0]) for row in cursor.fetchmany(_CHECK_MESSAGE_LIMIT)]
    except sqlite3.Error as exc:
        return {
            "ok": False,
            "messages": [],
            "error": _format_error(exc),
        }
    return {
        "ok": messages == ["ok"],
        "messages": messages,
        "error": None,
    }


def _probe_table(connection: sqlite3.Connection, table_name: str) -> dict[str, object]:
    quoted = _quote_identifier(table_name)
    try:
        exists_row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
    except sqlite3.Error as exc:
        error = _format_error(exc)
        return {
            "table": table_name,
            "exists": False,
            "count_ok": False,
            "row_count": None,
            "count_error": error,
            "sample_ok": False,
            "sample_rows": 0,
            "sample_error": error,
        }
    if exists_row is None:
        return {
            "table": table_name,
            "exists": False,
            "count_ok": False,
            "row_count": None,
            "count_error": "table missing",
            "sample_ok": False,
            "sample_rows": 0,
            "sample_error": "table missing",
        }

    row_count: int | None = None
    count_error: str | None = None
    try:
        count_row = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()
        row_count = None if count_row is None else int(count_row[0])
    except sqlite3.Error as exc:
        count_error = _format_error(exc)

    sample_rows = 0
    sample_error: str | None = None
    try:
        rows = connection.execute(f"SELECT 1 FROM {quoted} LIMIT 1").fetchall()
        sample_rows = len(rows)
    except sqlite3.Error as exc:
        sample_error = _format_error(exc)

    return {
        "table": table_name,
        "exists": True,
        "count_ok": count_error is None,
        "row_count": row_count,
        "count_error": count_error,
        "sample_ok": sample_error is None,
        "sample_rows": sample_rows,
        "sample_error": sample_error,
    }


def _is_healthy(report: dict[str, object], *, probe_tables: bool) -> bool:
    if not report.get("exists"):
        return False
    if report.get("open_error") or report.get("schema_error"):
        return False
    checks = report.get("checks") or {}
    if not checks:
        return False
    if any(not bool(check.get("ok")) for check in checks.values()):
        return False
    if not probe_tables:
        return True
    tables = report.get("tables") or []
    if not tables:
        return False
    return all(
        bool(table.get("exists")) and bool(table.get("count_ok")) and bool(table.get("sample_ok"))
        for table in tables
    )


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _format_error(exc: sqlite3.Error) -> str:
    return f"{type(exc).__name__}: {exc}"
