CREATE TABLE IF NOT EXISTS platform_mutable_manifests (
    manifest_id TEXT PRIMARY KEY REFERENCES platform_evidence_manifests(manifest_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL UNIQUE REFERENCES platform_events(event_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    manifest_type TEXT NOT NULL,
    projection_status TEXT NOT NULL DEFAULT 'pending' CHECK (projection_status IN ('pending', 'projected', 'failed', 'skipped')),
    projected_at TIMESTAMPTZ,
    last_error TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_mutable_manifests_status_time
    ON platform_mutable_manifests (projection_status, occurred_at ASC, manifest_id ASC);

CREATE INDEX IF NOT EXISTS idx_platform_mutable_manifests_aggregate_time
    ON platform_mutable_manifests (aggregate_type, aggregate_id, occurred_at DESC, manifest_id DESC);

CREATE TABLE IF NOT EXISTS platform_discovery_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    root_scope TEXT NOT NULL,
    page_limit INTEGER NOT NULL CHECK (page_limit >= 1),
    max_leaf_categories INTEGER CHECK (max_leaf_categories IS NULL OR max_leaf_categories >= 1),
    request_delay_seconds DOUBLE PRECISION NOT NULL CHECK (request_delay_seconds >= 0),
    total_seed_catalogs INTEGER NOT NULL DEFAULT 0 CHECK (total_seed_catalogs >= 0),
    total_leaf_catalogs INTEGER NOT NULL DEFAULT 0 CHECK (total_leaf_catalogs >= 0),
    scanned_leaf_catalogs INTEGER NOT NULL DEFAULT 0 CHECK (scanned_leaf_catalogs >= 0),
    successful_scans INTEGER NOT NULL DEFAULT 0 CHECK (successful_scans >= 0),
    failed_scans INTEGER NOT NULL DEFAULT 0 CHECK (failed_scans >= 0),
    raw_listing_hits INTEGER NOT NULL DEFAULT 0 CHECK (raw_listing_hits >= 0),
    unique_listing_hits INTEGER NOT NULL DEFAULT 0 CHECK (unique_listing_hits >= 0),
    last_error TEXT,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_discovery_runs_status_time
    ON platform_discovery_runs (status, started_at DESC, run_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_discovery_runs_finished_time
    ON platform_discovery_runs (finished_at DESC, run_id DESC);

CREATE TABLE IF NOT EXISTS platform_runtime_cycles (
    cycle_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    mode TEXT NOT NULL CHECK (mode IN ('batch', 'continuous')),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'interrupted')),
    phase TEXT NOT NULL,
    interval_seconds DOUBLE PRECISION,
    state_probe_limit INTEGER NOT NULL DEFAULT 0 CHECK (state_probe_limit >= 0),
    discovery_run_id TEXT REFERENCES platform_discovery_runs(run_id) ON DELETE SET NULL,
    state_probed_count INTEGER NOT NULL DEFAULT 0 CHECK (state_probed_count >= 0),
    tracked_listings INTEGER NOT NULL DEFAULT 0 CHECK (tracked_listings >= 0),
    first_pass_only INTEGER NOT NULL DEFAULT 0 CHECK (first_pass_only >= 0),
    fresh_followup INTEGER NOT NULL DEFAULT 0 CHECK (fresh_followup >= 0),
    aging_followup INTEGER NOT NULL DEFAULT 0 CHECK (aging_followup >= 0),
    stale_followup INTEGER NOT NULL DEFAULT 0 CHECK (stale_followup >= 0),
    last_error TEXT,
    state_refresh_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_runtime_cycles_started_at
    ON platform_runtime_cycles (started_at DESC, cycle_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_runtime_cycles_status_time
    ON platform_runtime_cycles (status, started_at DESC, cycle_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_runtime_cycles_discovery_run
    ON platform_runtime_cycles (discovery_run_id, started_at DESC, cycle_id DESC);

CREATE TABLE IF NOT EXISTS platform_runtime_controller_state (
    controller_id INTEGER PRIMARY KEY CHECK (controller_id = 1),
    status TEXT NOT NULL CHECK (status IN ('idle', 'running', 'scheduled', 'paused', 'failed')),
    phase TEXT NOT NULL,
    mode TEXT CHECK (mode IS NULL OR mode IN ('batch', 'continuous')),
    active_cycle_id TEXT REFERENCES platform_runtime_cycles(cycle_id) ON DELETE SET NULL,
    latest_cycle_id TEXT REFERENCES platform_runtime_cycles(cycle_id) ON DELETE SET NULL,
    interval_seconds DOUBLE PRECISION,
    updated_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    next_resume_at TIMESTAMPTZ,
    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    requested_action TEXT NOT NULL DEFAULT 'none' CHECK (requested_action IN ('none', 'pause', 'resume')),
    requested_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_runtime_controller_status_time
    ON platform_runtime_controller_state (status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_platform_runtime_controller_requested_action
    ON platform_runtime_controller_state (requested_action, updated_at DESC);

CREATE TABLE IF NOT EXISTS platform_catalogs (
    catalog_id BIGINT PRIMARY KEY,
    root_catalog_id BIGINT NOT NULL,
    root_title TEXT NOT NULL,
    parent_catalog_id BIGINT REFERENCES platform_catalogs(catalog_id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    code TEXT,
    url TEXT NOT NULL,
    path TEXT NOT NULL,
    depth INTEGER NOT NULL CHECK (depth >= 0),
    is_leaf BOOLEAN NOT NULL,
    allow_browsing_subcategories BOOLEAN NOT NULL,
    order_index INTEGER,
    synced_at TIMESTAMPTZ NOT NULL,
    last_run_id TEXT REFERENCES platform_discovery_runs(run_id) ON DELETE SET NULL,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_catalogs_root_leaf
    ON platform_catalogs (root_title, is_leaf, order_index NULLS LAST, catalog_id ASC);

CREATE INDEX IF NOT EXISTS idx_platform_catalogs_parent_order
    ON platform_catalogs (parent_catalog_id, order_index NULLS LAST, catalog_id ASC);

CREATE INDEX IF NOT EXISTS idx_platform_catalogs_synced_time
    ON platform_catalogs (synced_at DESC, catalog_id DESC);

CREATE TABLE IF NOT EXISTS platform_listing_identity (
    listing_id BIGINT PRIMARY KEY,
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
    user_id BIGINT,
    user_login TEXT,
    user_profile_url TEXT,
    created_at_ts BIGINT,
    primary_catalog_id BIGINT REFERENCES platform_catalogs(catalog_id) ON DELETE SET NULL,
    primary_root_catalog_id BIGINT REFERENCES platform_catalogs(catalog_id) ON DELETE SET NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    first_seen_run_id TEXT REFERENCES platform_discovery_runs(run_id) ON DELETE SET NULL,
    last_seen_run_id TEXT REFERENCES platform_discovery_runs(run_id) ON DELETE SET NULL,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_listing_identity_last_seen
    ON platform_listing_identity (last_seen_at DESC, listing_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_identity_catalog_last_seen
    ON platform_listing_identity (primary_catalog_id, last_seen_at DESC, listing_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_identity_brand
    ON platform_listing_identity (brand, listing_id ASC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_identity_condition
    ON platform_listing_identity (condition_label, listing_id ASC);

CREATE TABLE IF NOT EXISTS platform_listing_current_state (
    listing_id BIGINT PRIMARY KEY REFERENCES platform_listing_identity(listing_id) ON DELETE CASCADE,
    state_code TEXT NOT NULL CHECK (state_code IN ('active', 'sold_observed', 'sold_probable', 'unavailable_non_conclusive', 'deleted', 'unknown')),
    state_label TEXT NOT NULL,
    basis_kind TEXT NOT NULL CHECK (basis_kind IN ('observed', 'inferred', 'unknown')),
    confidence_label TEXT NOT NULL CHECK (confidence_label IN ('high', 'medium', 'low')),
    confidence_score DOUBLE PRECISION NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    sold_like BOOLEAN NOT NULL DEFAULT FALSE,
    seen_in_latest_primary_scan BOOLEAN NOT NULL DEFAULT FALSE,
    latest_primary_scan_run_id TEXT REFERENCES platform_discovery_runs(run_id) ON DELETE SET NULL,
    latest_primary_scan_at TIMESTAMPTZ,
    follow_up_miss_count INTEGER NOT NULL DEFAULT 0 CHECK (follow_up_miss_count >= 0),
    latest_follow_up_miss_at TIMESTAMPTZ,
    latest_probe_at TIMESTAMPTZ,
    latest_probe_response_status INTEGER,
    latest_probe_outcome TEXT,
    latest_probe_error_message TEXT,
    last_seen_age_hours DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (last_seen_age_hours >= 0),
    state_explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_listing_current_state_state_confidence
    ON platform_listing_current_state (state_code, confidence_score DESC, listing_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_current_state_basis_state
    ON platform_listing_current_state (basis_kind, state_code, listing_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_current_state_probe_outcome
    ON platform_listing_current_state (latest_probe_outcome, latest_probe_at DESC, listing_id DESC);

CREATE TABLE IF NOT EXISTS platform_listing_presence_summary (
    listing_id BIGINT PRIMARY KEY REFERENCES platform_listing_identity(listing_id) ON DELETE CASCADE,
    observation_count INTEGER NOT NULL DEFAULT 0 CHECK (observation_count >= 0),
    total_sightings INTEGER NOT NULL DEFAULT 0 CHECK (total_sightings >= 0),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    average_revisit_hours DOUBLE PRECISION,
    last_observed_run_id TEXT REFERENCES platform_discovery_runs(run_id) ON DELETE SET NULL,
    freshness_bucket TEXT NOT NULL CHECK (freshness_bucket IN ('first-pass-only', 'fresh-followup', 'aging-followup', 'stale-followup')),
    signal_completeness INTEGER NOT NULL DEFAULT 0 CHECK (signal_completeness >= 0),
    partial_signal BOOLEAN NOT NULL DEFAULT FALSE,
    thin_signal BOOLEAN NOT NULL DEFAULT FALSE,
    has_estimated_publication BOOLEAN NOT NULL DEFAULT FALSE,
    price_band_code TEXT NOT NULL CHECK (price_band_code IN ('under_20_eur', '20_to_39_eur', '40_plus_eur', 'unknown')),
    price_band_label TEXT NOT NULL,
    price_band_sort_order INTEGER NOT NULL DEFAULT 4 CHECK (price_band_sort_order >= 1),
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_listing_presence_summary_bucket_time
    ON platform_listing_presence_summary (freshness_bucket, last_seen_at DESC, listing_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_presence_summary_price_band
    ON platform_listing_presence_summary (price_band_code, freshness_bucket, last_seen_at DESC, listing_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_listing_presence_summary_run
    ON platform_listing_presence_summary (last_observed_run_id, last_seen_at DESC, listing_id DESC);

CREATE TABLE IF NOT EXISTS platform_outbox_checkpoints (
    consumer_name TEXT NOT NULL,
    sink TEXT NOT NULL,
    last_outbox_id BIGINT,
    last_event_id TEXT REFERENCES platform_events(event_id) ON DELETE SET NULL,
    last_manifest_id TEXT REFERENCES platform_mutable_manifests(manifest_id) ON DELETE SET NULL,
    last_claimed_at TIMESTAMPTZ,
    last_delivered_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'idle' CHECK (status IN ('idle', 'running', 'lagging', 'failed')),
    lag_seconds DOUBLE PRECISION,
    last_error TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (consumer_name, sink)
);

CREATE INDEX IF NOT EXISTS idx_platform_outbox_checkpoints_status_time
    ON platform_outbox_checkpoints (status, updated_at DESC, consumer_name ASC, sink ASC);

CREATE INDEX IF NOT EXISTS idx_platform_outbox_checkpoints_sink_time
    ON platform_outbox_checkpoints (sink, updated_at DESC, consumer_name ASC);

CREATE INDEX IF NOT EXISTS idx_platform_outbox_checkpoints_outbox_id
    ON platform_outbox_checkpoints (last_outbox_id DESC, consumer_name ASC, sink ASC);
