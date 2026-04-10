from __future__ import annotations

from pathlib import Path
import sqlite3
import threading

DEFAULT_RUNTIME_LANE = "frontier"

_DATABASE_BOOTSTRAP_LOCKS: dict[str, threading.Lock] = {}
_DATABASE_BOOTSTRAP_LOCKS_GUARD = threading.Lock()
_BOOTSTRAPPED_DATABASES: set[str] = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS discovery_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    root_scope TEXT NOT NULL,
    page_limit INTEGER NOT NULL,
    max_leaf_categories INTEGER,
    request_delay_seconds REAL NOT NULL,
    total_seed_catalogs INTEGER NOT NULL DEFAULT 0,
    total_leaf_catalogs INTEGER NOT NULL DEFAULT 0,
    scanned_leaf_catalogs INTEGER NOT NULL DEFAULT 0,
    successful_scans INTEGER NOT NULL DEFAULT 0,
    failed_scans INTEGER NOT NULL DEFAULT 0,
    raw_listing_hits INTEGER NOT NULL DEFAULT 0,
    unique_listing_hits INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS catalogs (
    catalog_id INTEGER PRIMARY KEY,
    root_catalog_id INTEGER NOT NULL,
    root_title TEXT NOT NULL,
    parent_catalog_id INTEGER,
    title TEXT NOT NULL,
    code TEXT,
    url TEXT NOT NULL,
    path TEXT NOT NULL,
    depth INTEGER NOT NULL,
    is_leaf INTEGER NOT NULL CHECK (is_leaf IN (0, 1)),
    allow_browsing_subcategories INTEGER NOT NULL CHECK (allow_browsing_subcategories IN (0, 1)),
    order_index INTEGER,
    synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_scans (
    run_id TEXT NOT NULL,
    catalog_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    requested_url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    response_status INTEGER,
    success INTEGER NOT NULL CHECK (success IN (0, 1)),
    listing_count INTEGER NOT NULL DEFAULT 0,
    api_listing_count INTEGER,
    accepted_listing_count INTEGER,
    filtered_out_count INTEGER,
    accepted_ratio REAL,
    min_price_seen_cents INTEGER,
    max_price_seen_cents INTEGER,
    pagination_total_pages INTEGER,
    next_page_url TEXT,
    error_message TEXT,
    PRIMARY KEY (run_id, catalog_id, page_number),
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (catalog_id) REFERENCES catalogs(catalog_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS listings (
    listing_id INTEGER PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT,
    brand TEXT,
    size_label TEXT,
    condition_label TEXT,
    price_amount_cents INTEGER,
    price_currency TEXT,
    total_price_amount_cents INTEGER,
    total_price_currency TEXT,
    image_url TEXT,
    favourite_count INTEGER,
    view_count INTEGER,
    user_id INTEGER,
    user_login TEXT,
    user_profile_url TEXT,
    created_at_ts INTEGER,
    primary_catalog_id INTEGER,
    primary_root_catalog_id INTEGER,
    first_discovered_at TEXT NOT NULL,
    last_discovered_at TEXT NOT NULL,
    last_seen_run_id TEXT NOT NULL,
    last_card_payload_json TEXT NOT NULL,
    FOREIGN KEY (primary_catalog_id) REFERENCES catalogs(catalog_id),
    FOREIGN KEY (last_seen_run_id) REFERENCES discovery_runs(run_id)
);

CREATE TABLE IF NOT EXISTS listing_discoveries (
    run_id TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    source_catalog_id INTEGER NOT NULL,
    source_page_number INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    card_position INTEGER NOT NULL,
    raw_card_payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, listing_id, source_catalog_id, source_page_number),
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (listing_id) REFERENCES listings(listing_id) ON DELETE CASCADE,
    FOREIGN KEY (source_catalog_id) REFERENCES catalogs(catalog_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS listing_observations (
    run_id TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_catalog_id INTEGER,
    source_page_number INTEGER,
    first_card_position INTEGER,
    sighting_count INTEGER NOT NULL DEFAULT 1,
    title TEXT,
    brand TEXT,
    size_label TEXT,
    condition_label TEXT,
    price_amount_cents INTEGER,
    price_currency TEXT,
    total_price_amount_cents INTEGER,
    total_price_currency TEXT,
    image_url TEXT,
    raw_card_payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, listing_id),
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (listing_id) REFERENCES listings(listing_id) ON DELETE CASCADE,
    FOREIGN KEY (source_catalog_id) REFERENCES catalogs(catalog_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS item_page_probes (
    probe_id TEXT PRIMARY KEY,
    listing_id INTEGER NOT NULL,
    probed_at TEXT NOT NULL,
    requested_url TEXT NOT NULL,
    final_url TEXT,
    response_status INTEGER,
    probe_outcome TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY (listing_id) REFERENCES listings(listing_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runtime_cycles (
    cycle_id TEXT PRIMARY KEY,
    lane_name TEXT NOT NULL DEFAULT 'frontier',
    benchmark_label TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    interval_seconds REAL,
    state_probe_limit INTEGER NOT NULL DEFAULT 0,
    discovery_run_id TEXT,
    state_probed_count INTEGER NOT NULL DEFAULT 0,
    tracked_listings INTEGER NOT NULL DEFAULT 0,
    first_pass_only INTEGER NOT NULL DEFAULT 0,
    fresh_followup INTEGER NOT NULL DEFAULT 0,
    aging_followup INTEGER NOT NULL DEFAULT 0,
    stale_followup INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    state_refresh_summary_json TEXT NOT NULL DEFAULT '{}',
    config_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (discovery_run_id) REFERENCES discovery_runs(run_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS runtime_controller_state (
    controller_id INTEGER PRIMARY KEY CHECK (controller_id = 1),
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    mode TEXT,
    active_cycle_id TEXT,
    latest_cycle_id TEXT,
    interval_seconds REAL,
    updated_at TEXT,
    paused_at TEXT,
    next_resume_at TEXT,
    last_error TEXT,
    last_error_at TEXT,
    requested_action TEXT NOT NULL DEFAULT 'none',
    requested_at TEXT,
    latest_benchmark_label TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (active_cycle_id) REFERENCES runtime_cycles(cycle_id) ON DELETE SET NULL,
    FOREIGN KEY (latest_cycle_id) REFERENCES runtime_cycles(cycle_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS runtime_lane_controller_state (
    lane_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    mode TEXT,
    active_cycle_id TEXT,
    latest_cycle_id TEXT,
    interval_seconds REAL,
    updated_at TEXT,
    paused_at TEXT,
    next_resume_at TEXT,
    last_error TEXT,
    last_error_at TEXT,
    requested_action TEXT NOT NULL DEFAULT 'none',
    requested_at TEXT,
    latest_benchmark_label TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (active_cycle_id) REFERENCES runtime_cycles(cycle_id) ON DELETE SET NULL,
    FOREIGN KEY (latest_cycle_id) REFERENCES runtime_cycles(cycle_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_catalogs_root_leaf ON catalogs(root_title, is_leaf);
CREATE INDEX IF NOT EXISTS idx_catalog_scans_run_success ON catalog_scans(run_id, success);
CREATE INDEX IF NOT EXISTS idx_catalog_scans_catalog_success_time ON catalog_scans(catalog_id, success, fetched_at DESC, run_id DESC);
CREATE INDEX IF NOT EXISTS idx_listing_discoveries_run_catalog ON listing_discoveries(run_id, source_catalog_id);
CREATE INDEX IF NOT EXISTS idx_listing_observations_listing_time ON listing_observations(listing_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_listings_last_discovered_at ON listings(last_discovered_at DESC, listing_id DESC);
CREATE INDEX IF NOT EXISTS idx_listings_primary_catalog_last_seen ON listings(primary_catalog_id, last_discovered_at DESC, listing_id DESC);
CREATE INDEX IF NOT EXISTS idx_listings_brand ON listings(brand, listing_id);
CREATE INDEX IF NOT EXISTS idx_listings_condition ON listings(condition_label, listing_id);
CREATE INDEX IF NOT EXISTS idx_item_page_probes_listing_time ON item_page_probes(listing_id, probed_at);
CREATE INDEX IF NOT EXISTS idx_runtime_cycles_started_at ON runtime_cycles(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runtime_controller_updated_at ON runtime_controller_state(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_runtime_lane_controller_updated_at ON runtime_lane_controller_state(updated_at DESC);
"""


POST_MIGRATION_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_runtime_cycles_lane_started_at ON runtime_cycles(lane_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_created_at_ts ON listings(created_at_ts DESC, listing_id DESC);
CREATE INDEX IF NOT EXISTS idx_listings_favourite_count ON listings(favourite_count DESC, listing_id DESC);
CREATE INDEX IF NOT EXISTS idx_listings_view_count ON listings(view_count DESC, listing_id DESC);
"""


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    db_str = str(db_path)
    if db_str != ":memory:":
        Path(db_str).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_str, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    if db_str == ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.executescript(SCHEMA)
        _apply_migrations(connection)
        connection.executescript(POST_MIGRATION_SCHEMA)
        connection.commit()
        return connection

    with _database_bootstrap_lock(db_str):
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        if _database_requires_bootstrap(connection, db_str):
            connection.executescript(SCHEMA)
            _apply_migrations(connection)
            connection.executescript(POST_MIGRATION_SCHEMA)
            connection.commit()
            _BOOTSTRAPPED_DATABASES.add(db_str)
    return connection


def _database_bootstrap_lock(db_str: str) -> threading.Lock:
    with _DATABASE_BOOTSTRAP_LOCKS_GUARD:
        return _DATABASE_BOOTSTRAP_LOCKS.setdefault(db_str, threading.Lock())


def _database_requires_bootstrap(connection: sqlite3.Connection, db_str: str) -> bool:
    return db_str not in _BOOTSTRAPPED_DATABASES or not _table_exists(connection, "discovery_runs")


def _apply_migrations(connection: sqlite3.Connection) -> None:
    # --- Extended Metadata Migration ---
    for col in (
        "favourite_count INTEGER",
        "view_count INTEGER",
        "user_id INTEGER",
        "user_login TEXT",
        "user_profile_url TEXT",
        "created_at_ts INTEGER",
    ):
        try:
            connection.execute(f"ALTER TABLE listings ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    # -----------------------------------

    for table_name, column_spec in (
        ("runtime_cycles", "state_refresh_summary_json TEXT NOT NULL DEFAULT '{}'"),
        ("runtime_cycles", f"lane_name TEXT NOT NULL DEFAULT '{DEFAULT_RUNTIME_LANE}'"),
        ("runtime_cycles", "benchmark_label TEXT"),
        ("runtime_controller_state", "latest_benchmark_label TEXT"),
        ("catalog_scans", "api_listing_count INTEGER"),
        ("catalog_scans", "accepted_listing_count INTEGER"),
        ("catalog_scans", "filtered_out_count INTEGER"),
        ("catalog_scans", "accepted_ratio REAL"),
        ("catalog_scans", "min_price_seen_cents INTEGER"),
        ("catalog_scans", "max_price_seen_cents INTEGER"),
    ):
        try:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_spec}")
        except sqlite3.OperationalError:
            pass

    if _table_exists(connection, "catalog_scans"):
        connection.execute(
            """
            UPDATE catalog_scans
            SET api_listing_count = listing_count
            WHERE api_listing_count IS NULL
            """
        )
        connection.execute(
            """
            UPDATE catalog_scans
            SET filtered_out_count = api_listing_count - accepted_listing_count
            WHERE filtered_out_count IS NULL
              AND api_listing_count IS NOT NULL
              AND accepted_listing_count IS NOT NULL
            """
        )
        connection.execute(
            """
            UPDATE catalog_scans
            SET accepted_ratio = CASE
                WHEN api_listing_count IS NULL THEN NULL
                WHEN accepted_listing_count IS NULL THEN NULL
                WHEN api_listing_count = 0 THEN NULL
                ELSE CAST(accepted_listing_count AS REAL) / CAST(api_listing_count AS REAL)
            END
            WHERE accepted_ratio IS NULL
              AND accepted_listing_count IS NOT NULL
            """
        )

    if _table_exists(connection, "runtime_cycles"):
        connection.execute(
            """
            UPDATE runtime_cycles
            SET lane_name = ?
            WHERE lane_name IS NULL OR TRIM(lane_name) = ''
            """,
            (DEFAULT_RUNTIME_LANE,),
        )

    if _table_exists(connection, "listing_discoveries") and _table_exists(connection, "listings"):
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            # Mark as migrated so we never attempt massive blocking startup queries again
            connection.execute("PRAGMA user_version = 1")

    _backfill_runtime_controller_state(connection)
    _backfill_runtime_lane_controller_state(connection)



def _backfill_runtime_controller_state(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "runtime_controller_state") or not _table_exists(connection, "runtime_cycles"):
        return
    existing_row = connection.execute(
        "SELECT controller_id FROM runtime_controller_state WHERE controller_id = 1"
    ).fetchone()
    if existing_row is not None:
        return

    latest_cycle = connection.execute(
        "SELECT * FROM runtime_cycles ORDER BY started_at DESC, cycle_id DESC LIMIT 1"
    ).fetchone()
    if latest_cycle is None:
        return

    updated_at = latest_cycle["finished_at"] or latest_cycle["started_at"]
    cycle_status = str(latest_cycle["status"])
    controller_status = _controller_status_from_cycle_status(cycle_status)
    last_error = latest_cycle["last_error"] if controller_status == "failed" else None
    last_error_at = updated_at if last_error else None
    active_cycle_id = latest_cycle["cycle_id"] if controller_status == "running" else None

    connection.execute(
        """
        INSERT INTO runtime_controller_state (
            controller_id,
            status,
            phase,
            mode,
            active_cycle_id,
            latest_cycle_id,
            interval_seconds,
            updated_at,
            paused_at,
            next_resume_at,
            last_error,
            last_error_at,
            requested_action,
            requested_at,
            latest_benchmark_label,
            config_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'none', NULL, ?, ?)
        """,
        (
            1,
            controller_status,
            latest_cycle["phase"],
            latest_cycle["mode"],
            active_cycle_id,
            latest_cycle["cycle_id"],
            latest_cycle["interval_seconds"],
            updated_at,
            None,
            None,
            last_error,
            last_error_at,
            latest_cycle["benchmark_label"],
            latest_cycle["config_json"] or "{}",
        ),
    )



def _backfill_runtime_lane_controller_state(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "runtime_lane_controller_state"):
        return

    existing_rows = connection.execute(
        "SELECT lane_name FROM runtime_lane_controller_state LIMIT 1"
    ).fetchone()
    if existing_rows is not None:
        return

    controller_row = None
    if _table_exists(connection, "runtime_controller_state"):
        controller_row = connection.execute(
            "SELECT * FROM runtime_controller_state WHERE controller_id = 1"
        ).fetchone()

    latest_cycle = None
    if _table_exists(connection, "runtime_cycles"):
        latest_cycle = connection.execute(
            "SELECT * FROM runtime_cycles ORDER BY started_at DESC, cycle_id DESC LIMIT 1"
        ).fetchone()

    if controller_row is None and latest_cycle is None:
        return

    lane_name = DEFAULT_RUNTIME_LANE
    latest_benchmark_label = None
    if latest_cycle is not None:
        lane_name = str(latest_cycle["lane_name"] or DEFAULT_RUNTIME_LANE)
        latest_benchmark_label = latest_cycle["benchmark_label"]

    connection.execute(
        """
        INSERT INTO runtime_lane_controller_state (
            lane_name,
            status,
            phase,
            mode,
            active_cycle_id,
            latest_cycle_id,
            interval_seconds,
            updated_at,
            paused_at,
            next_resume_at,
            last_error,
            last_error_at,
            requested_action,
            requested_at,
            latest_benchmark_label,
            config_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lane_name,
            (None if controller_row is None else controller_row["status"]) or _controller_status_from_cycle_status(str(latest_cycle["status"] if latest_cycle is not None else "idle")),
            (None if controller_row is None else controller_row["phase"]) or (None if latest_cycle is None else latest_cycle["phase"]) or "idle",
            (None if controller_row is None else controller_row["mode"]) or (None if latest_cycle is None else latest_cycle["mode"]),
            None if controller_row is None else controller_row["active_cycle_id"],
            (None if controller_row is None else controller_row["latest_cycle_id"]) or (None if latest_cycle is None else latest_cycle["cycle_id"]),
            (None if controller_row is None else controller_row["interval_seconds"]) or (None if latest_cycle is None else latest_cycle["interval_seconds"]),
            (None if controller_row is None else controller_row["updated_at"]) or (None if latest_cycle is None else (latest_cycle["finished_at"] or latest_cycle["started_at"])),
            None if controller_row is None else controller_row["paused_at"],
            None if controller_row is None else controller_row["next_resume_at"],
            None if controller_row is None else controller_row["last_error"],
            None if controller_row is None else controller_row["last_error_at"],
            (None if controller_row is None else controller_row["requested_action"]) or "none",
            None if controller_row is None else controller_row["requested_at"],
            (None if controller_row is None else controller_row["latest_benchmark_label"]) or latest_benchmark_label,
            (None if controller_row is None else controller_row["config_json"]) or (None if latest_cycle is None else latest_cycle["config_json"]) or "{}",
        ),
    )



def _controller_status_from_cycle_status(cycle_status: str) -> str:
    if cycle_status == "running":
        return "running"
    if cycle_status == "failed":
        return "failed"
    return "idle"



def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
