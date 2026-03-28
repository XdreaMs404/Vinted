CREATE TABLE IF NOT EXISTS platform_bootstrap_audit (
    event_id BIGSERIAL PRIMARY KEY,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_bootstrap_audit_component_time
    ON platform_bootstrap_audit (component, recorded_at DESC);
