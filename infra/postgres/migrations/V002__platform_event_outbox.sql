CREATE TABLE IF NOT EXISTS platform_events (
    event_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    producer TEXT NOT NULL,
    partition_key TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_checksum TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_events_type_time
    ON platform_events (event_type, occurred_at DESC, event_id DESC);

CREATE INDEX IF NOT EXISTS idx_platform_events_partition_time
    ON platform_events (partition_key, occurred_at DESC, event_id DESC);

CREATE TABLE IF NOT EXISTS platform_evidence_manifests (
    manifest_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES platform_events(event_id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL,
    manifest_type TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    bucket TEXT NOT NULL,
    entries_json JSONB NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum_algorithm TEXT NOT NULL DEFAULT 'sha256',
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_evidence_manifests_event_time
    ON platform_evidence_manifests (event_id, generated_at DESC, manifest_id DESC);

CREATE TABLE IF NOT EXISTS platform_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES platform_events(event_id) ON DELETE CASCADE,
    sink TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'delivered', 'failed')),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    claimed_by TEXT,
    locked_until TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    last_error TEXT,
    manifest_id TEXT REFERENCES platform_evidence_manifests(manifest_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, sink)
);

CREATE INDEX IF NOT EXISTS idx_platform_outbox_claim
    ON platform_outbox (sink, status, available_at ASC, outbox_id ASC);

CREATE INDEX IF NOT EXISTS idx_platform_outbox_lock_window
    ON platform_outbox (sink, locked_until ASC, outbox_id ASC);
