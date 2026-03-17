from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

REQUIRED_TABLES = frozenset(
    {
        "catalog_nodes",
        "discovery_runs",
        "listing_identities",
        "listing_observations",
        "raw_evidence_fragments",
        "scan_coverage",
    }
)

_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS catalog_nodes (
        catalog_id INTEGER PRIMARY KEY,
        parent_catalog_id INTEGER,
        root_catalog_id INTEGER NOT NULL,
        slug TEXT,
        title TEXT,
        path TEXT,
        source_url TEXT,
        is_leaf INTEGER,
        observed_at TEXT NOT NULL,
        extractor_version TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS discovery_runs (
        run_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        requested_roots_json TEXT NOT NULL,
        max_pages_per_catalog INTEGER,
        item_details_mode TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        error_message TEXT,
        observed_at TEXT NOT NULL,
        extractor_version TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS listing_identities (
        listing_id TEXT PRIMARY KEY,
        source_url TEXT,
        seller_id TEXT,
        seller_login TEXT,
        first_observed_at TEXT NOT NULL,
        last_observed_at TEXT NOT NULL,
        first_extractor_version TEXT NOT NULL,
        last_extractor_version TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS listing_observations (
        observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        listing_id TEXT NOT NULL,
        catalog_id INTEGER,
        catalog_page INTEGER,
        observed_rank INTEGER,
        title TEXT,
        brand TEXT,
        size_label TEXT,
        price_amount REAL,
        currency_code TEXT,
        status_hint TEXT,
        seller_login TEXT,
        seller_country_code TEXT,
        favourite_count INTEGER,
        view_count INTEGER,
        image_url TEXT,
        source_url TEXT,
        observed_at TEXT NOT NULL,
        extractor_version TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_evidence_fragments (
        fragment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        listing_id TEXT,
        catalog_id INTEGER,
        fragment_kind TEXT NOT NULL,
        fragment_key TEXT,
        source_url TEXT,
        content_type TEXT NOT NULL,
        body TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        extractor_version TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scan_coverage (
        coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        catalog_id INTEGER,
        root_catalog_id INTEGER,
        page_number INTEGER,
        stage TEXT NOT NULL,
        pages_scanned INTEGER NOT NULL DEFAULT 0,
        listing_stubs_seen INTEGER NOT NULL DEFAULT 0,
        unique_listings INTEGER NOT NULL DEFAULT 0,
        duplicate_listings INTEGER NOT NULL DEFAULT 0,
        errors INTEGER NOT NULL DEFAULT 0,
        stop_reason TEXT,
        error_message TEXT,
        observed_at TEXT NOT NULL,
        extractor_version TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_listing_observations_listing_id
    ON listing_observations(listing_id, observed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_listing_observations_run_id
    ON listing_observations(run_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_evidence_fragments_run_id
    ON raw_evidence_fragments(run_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_scan_coverage_run_id
    ON scan_coverage(run_id, catalog_id, page_number)
    """,
)


def connect_sqlite(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def bootstrap_sqlite(connection: sqlite3.Connection) -> None:
    with connection:
        for statement in _SCHEMA:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 1")


def required_tables() -> frozenset[str]:
    return REQUIRED_TABLES


def list_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [str(row["name"]) for row in rows]


def table_columns(connection: sqlite3.Connection, table_name: str) -> Iterable[sqlite3.Row]:
    return connection.execute(f"PRAGMA table_info({table_name})").fetchall()
