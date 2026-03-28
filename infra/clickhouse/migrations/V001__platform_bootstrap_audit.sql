CREATE TABLE IF NOT EXISTS platform_bootstrap_audit (
    component LowCardinality(String),
    status LowCardinality(String),
    detail String,
    recorded_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (component, recorded_at)
SETTINGS index_granularity = 8192;
