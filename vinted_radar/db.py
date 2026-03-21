from __future__ import annotations

from pathlib import Path
import sqlite3

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
    config_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (discovery_run_id) REFERENCES discovery_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_catalogs_root_leaf ON catalogs(root_title, is_leaf);
CREATE INDEX IF NOT EXISTS idx_catalog_scans_run_success ON catalog_scans(run_id, success);
CREATE INDEX IF NOT EXISTS idx_listing_discoveries_run_catalog ON listing_discoveries(run_id, source_catalog_id);
CREATE INDEX IF NOT EXISTS idx_listing_observations_listing_time ON listing_observations(listing_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_item_page_probes_listing_time ON item_page_probes(listing_id, probed_at);
CREATE INDEX IF NOT EXISTS idx_runtime_cycles_started_at ON runtime_cycles(started_at DESC);
"""


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    db_str = str(db_path)
    if db_str != ":memory:":
        Path(db_str).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_str, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.executescript(SCHEMA)
    _apply_migrations(connection)
    connection.commit()
    return connection


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

    if not _table_exists(connection, "listing_discoveries") or not _table_exists(connection, "listings"):
        return

    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version >= 1:
        return

    connection.execute(
        """
        INSERT OR IGNORE INTO listing_observations (
            run_id, listing_id, observed_at, canonical_url, source_url,
            source_catalog_id, source_page_number, first_card_position, sighting_count,
            title, brand, size_label, condition_label,
            price_amount_cents, price_currency,
            total_price_amount_cents, total_price_currency,
            image_url, raw_card_payload_json
        )
        SELECT
            discoveries.run_id,
            discoveries.listing_id,
            discoveries.observed_at,
            listings.canonical_url,
            discoveries.source_url,
            discoveries.source_catalog_id,
            discoveries.source_page_number,
            discoveries.card_position,
            1,
            listings.title,
            listings.brand,
            listings.size_label,
            listings.condition_label,
            listings.price_amount_cents,
            listings.price_currency,
            listings.total_price_amount_cents,
            listings.total_price_currency,
            listings.image_url,
            discoveries.raw_card_payload_json
        FROM listing_discoveries AS discoveries
        JOIN listings ON listings.listing_id = discoveries.listing_id
        """
    )
    connection.execute(
        """
        UPDATE listing_observations
        SET sighting_count = (
            SELECT COUNT(*)
            FROM listing_discoveries AS discoveries
            WHERE discoveries.run_id = listing_observations.run_id
              AND discoveries.listing_id = listing_observations.listing_id
        )
        WHERE EXISTS (
            SELECT 1
            FROM listing_discoveries AS discoveries
            WHERE discoveries.run_id = listing_observations.run_id
              AND discoveries.listing_id = listing_observations.listing_id
        )
        """
    )
    connection.execute(
        """
        UPDATE listing_observations
        SET
            canonical_url = COALESCE(NULLIF(canonical_url, ''), (SELECT canonical_url FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            title = COALESCE(title, (SELECT title FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            brand = COALESCE(brand, (SELECT brand FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            size_label = COALESCE(size_label, (SELECT size_label FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            condition_label = COALESCE(condition_label, (SELECT condition_label FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            price_amount_cents = COALESCE(price_amount_cents, (SELECT price_amount_cents FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            price_currency = COALESCE(price_currency, (SELECT price_currency FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            total_price_amount_cents = COALESCE(total_price_amount_cents, (SELECT total_price_amount_cents FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            total_price_currency = COALESCE(total_price_currency, (SELECT total_price_currency FROM listings WHERE listings.listing_id = listing_observations.listing_id)),
            image_url = COALESCE(image_url, (SELECT image_url FROM listings WHERE listings.listing_id = listing_observations.listing_id))
        """
    )
    
    connection.execute("PRAGMA user_version = 1")


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
