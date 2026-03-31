CREATE TABLE IF NOT EXISTS fact_listing_seen_events (
    event_id String,
    manifest_id Nullable(String),
    source_event_id Nullable(String),
    source_event_type LowCardinality(String) DEFAULT 'vinted.listing.observed',
    schema_version UInt16 DEFAULT 1,
    occurred_at DateTime64(3, 'UTC'),
    observed_at DateTime64(3, 'UTC'),
    observed_date Date MATERIALIZED toDate(observed_at),
    observed_hour DateTime('UTC') MATERIALIZED toStartOfHour(observed_at),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3),
    run_id Nullable(String),
    producer LowCardinality(String) DEFAULT 'platform.clickhouse_ingest',
    partition_key Nullable(String),
    listing_id UInt64,
    canonical_url String,
    source_url String,
    title Nullable(String),
    brand Nullable(String),
    size_label Nullable(String),
    condition_label Nullable(String),
    price_amount_cents Nullable(Int32),
    price_currency Nullable(String),
    total_price_amount_cents Nullable(Int32),
    total_price_currency Nullable(String),
    image_url Nullable(String),
    favourite_count Nullable(Int32),
    view_count Nullable(Int32),
    user_id Nullable(UInt64),
    user_login Nullable(String),
    user_profile_url Nullable(String),
    created_at_ts Nullable(Int64),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    source_catalog_id Nullable(UInt64),
    source_root_catalog_id Nullable(UInt64),
    source_page_number Nullable(UInt16),
    card_position Nullable(UInt16),
    root_title Nullable(String),
    category_path Nullable(String),
    has_estimated_publication UInt8 DEFAULT if(created_at_ts IS NULL, 0, 1),
    price_band_code LowCardinality(String) DEFAULT multiIf(
        price_amount_cents IS NULL, 'unknown',
        price_amount_cents < 2000, 'under_20_eur',
        price_amount_cents < 4000, '20_to_39_eur',
        '40_plus_eur'
    ),
    price_band_label LowCardinality(String) DEFAULT multiIf(
        price_amount_cents IS NULL, 'Prix indisponible',
        price_amount_cents < 2000, '< 20 €',
        price_amount_cents < 4000, '20–39 €',
        '40 € et plus'
    ),
    price_band_sort_order UInt8 DEFAULT multiIf(
        price_amount_cents IS NULL, 4,
        price_amount_cents < 2000, 1,
        price_amount_cents < 4000, 2,
        3
    ),
    raw_card_json String DEFAULT '{}',
    metadata_json String DEFAULT '{}'
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (observed_at, listing_id, event_id)
TTL observed_at + INTERVAL 730 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS fact_listing_probe_events (
    event_id String,
    manifest_id Nullable(String),
    source_event_id Nullable(String),
    source_event_type LowCardinality(String) DEFAULT 'vinted.listing.probe',
    schema_version UInt16 DEFAULT 1,
    occurred_at DateTime64(3, 'UTC'),
    probed_at DateTime64(3, 'UTC'),
    probed_date Date MATERIALIZED toDate(probed_at),
    probed_hour DateTime('UTC') MATERIALIZED toStartOfHour(probed_at),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3),
    producer LowCardinality(String) DEFAULT 'platform.clickhouse_ingest',
    listing_id UInt64,
    requested_url String,
    final_url Nullable(String),
    response_status Nullable(UInt16),
    probe_outcome LowCardinality(String),
    reason Nullable(String),
    error_message Nullable(String),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    brand Nullable(String),
    condition_label Nullable(String),
    price_amount_cents Nullable(Int32),
    price_currency Nullable(String),
    total_price_amount_cents Nullable(Int32),
    total_price_currency Nullable(String),
    favourite_count Nullable(Int32),
    view_count Nullable(Int32),
    price_band_code LowCardinality(String) DEFAULT multiIf(
        price_amount_cents IS NULL, 'unknown',
        price_amount_cents < 2000, 'under_20_eur',
        price_amount_cents < 4000, '20_to_39_eur',
        '40_plus_eur'
    ),
    price_band_label LowCardinality(String) DEFAULT multiIf(
        price_amount_cents IS NULL, 'Prix indisponible',
        price_amount_cents < 2000, '< 20 €',
        price_amount_cents < 4000, '20–39 €',
        '40 € et plus'
    ),
    detail_json String DEFAULT '{}',
    metadata_json String DEFAULT '{}'
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(probed_at)
ORDER BY (probed_at, listing_id, event_id)
TTL probed_at + INTERVAL 730 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS fact_listing_change_events (
    event_id String,
    manifest_id Nullable(String),
    source_event_id Nullable(String),
    source_event_type LowCardinality(String) DEFAULT 'vinted.listing.change',
    schema_version UInt16 DEFAULT 1,
    occurred_at DateTime64(3, 'UTC'),
    change_date Date MATERIALIZED toDate(occurred_at),
    change_hour DateTime('UTC') MATERIALIZED toStartOfHour(occurred_at),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3),
    producer LowCardinality(String) DEFAULT 'platform.clickhouse_ingest',
    listing_id UInt64,
    change_kind LowCardinality(String),
    previous_state_code Nullable(LowCardinality(String)),
    current_state_code Nullable(LowCardinality(String)),
    previous_basis_kind Nullable(LowCardinality(String)),
    current_basis_kind Nullable(LowCardinality(String)),
    previous_confidence_label Nullable(LowCardinality(String)),
    current_confidence_label Nullable(LowCardinality(String)),
    previous_confidence_score Nullable(Float32),
    current_confidence_score Nullable(Float32),
    previous_price_amount_cents Nullable(Int32),
    current_price_amount_cents Nullable(Int32),
    previous_total_price_amount_cents Nullable(Int32),
    current_total_price_amount_cents Nullable(Int32),
    previous_favourite_count Nullable(Int32),
    current_favourite_count Nullable(Int32),
    previous_view_count Nullable(Int32),
    current_view_count Nullable(Int32),
    follow_up_miss_count Nullable(UInt16),
    probe_outcome Nullable(LowCardinality(String)),
    response_status Nullable(UInt16),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    brand Nullable(String),
    condition_label Nullable(String),
    price_band_code LowCardinality(String) DEFAULT multiIf(
        current_price_amount_cents IS NULL, 'unknown',
        current_price_amount_cents < 2000, 'under_20_eur',
        current_price_amount_cents < 4000, '20_to_39_eur',
        '40_plus_eur'
    ),
    change_summary Nullable(String),
    change_json String DEFAULT '{}',
    metadata_json String DEFAULT '{}'
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (occurred_at, listing_id, change_kind, event_id)
TTL occurred_at + INTERVAL 730 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS rollup_listing_seen_hourly (
    bucket_start DateTime('UTC'),
    listing_id UInt64,
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    brand Nullable(String),
    condition_label Nullable(String),
    price_band_code LowCardinality(String),
    seen_events_state AggregateFunction(sum, UInt64),
    unique_listing_state AggregateFunction(uniqExact, UInt64),
    sighting_count_state AggregateFunction(sum, UInt64),
    price_sum_state AggregateFunction(sum, Int64),
    price_count_state AggregateFunction(sum, UInt64),
    favourite_sum_state AggregateFunction(sum, Int64),
    favourite_count_state AggregateFunction(sum, UInt64),
    view_sum_state AggregateFunction(sum, Int64),
    view_count_state AggregateFunction(sum, UInt64),
    first_seen_state AggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(bucket_start)
ORDER BY (bucket_start, listing_id, primary_root_catalog_id, primary_catalog_id, brand)
TTL bucket_start + INTERVAL 3650 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS rollup_listing_seen_daily (
    bucket_date Date,
    listing_id UInt64,
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    brand Nullable(String),
    condition_label Nullable(String),
    price_band_code LowCardinality(String),
    seen_events_state AggregateFunction(sum, UInt64),
    unique_listing_state AggregateFunction(uniqExact, UInt64),
    sighting_count_state AggregateFunction(sum, UInt64),
    price_sum_state AggregateFunction(sum, Int64),
    price_count_state AggregateFunction(sum, UInt64),
    favourite_sum_state AggregateFunction(sum, Int64),
    favourite_count_state AggregateFunction(sum, UInt64),
    view_sum_state AggregateFunction(sum, Int64),
    view_count_state AggregateFunction(sum, UInt64),
    first_seen_state AggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(bucket_date)
ORDER BY (bucket_date, listing_id, primary_root_catalog_id, primary_catalog_id, brand)
TTL bucket_date + INTERVAL 3650 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS rollup_category_daily (
    bucket_date Date,
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    condition_label Nullable(String),
    price_band_code LowCardinality(String),
    seen_events_state AggregateFunction(sum, UInt64),
    unique_listing_state AggregateFunction(uniqExact, UInt64),
    price_sum_state AggregateFunction(sum, Int64),
    price_count_state AggregateFunction(sum, UInt64),
    favourite_sum_state AggregateFunction(sum, Int64),
    favourite_count_state AggregateFunction(sum, UInt64),
    view_sum_state AggregateFunction(sum, Int64),
    view_count_state AggregateFunction(sum, UInt64),
    first_seen_state AggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(bucket_date)
ORDER BY (bucket_date, primary_root_catalog_id, primary_catalog_id, price_band_code, condition_label)
TTL bucket_date + INTERVAL 3650 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS rollup_brand_daily (
    bucket_date Date,
    brand Nullable(String),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    condition_label Nullable(String),
    price_band_code LowCardinality(String),
    seen_events_state AggregateFunction(sum, UInt64),
    unique_listing_state AggregateFunction(uniqExact, UInt64),
    price_sum_state AggregateFunction(sum, Int64),
    price_count_state AggregateFunction(sum, UInt64),
    favourite_sum_state AggregateFunction(sum, Int64),
    favourite_count_state AggregateFunction(sum, UInt64),
    view_sum_state AggregateFunction(sum, Int64),
    view_count_state AggregateFunction(sum, UInt64),
    first_seen_state AggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(bucket_date)
ORDER BY (bucket_date, brand, primary_root_catalog_id, primary_catalog_id, price_band_code)
TTL bucket_date + INTERVAL 3650 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS serving_listing_latest_seen (
    listing_id UInt64,
    version_token UInt64,
    observed_at DateTime64(3, 'UTC'),
    event_id String,
    manifest_id Nullable(String),
    run_id Nullable(String),
    canonical_url String,
    source_url String,
    title Nullable(String),
    brand Nullable(String),
    size_label Nullable(String),
    condition_label Nullable(String),
    price_amount_cents Nullable(Int32),
    price_currency Nullable(String),
    total_price_amount_cents Nullable(Int32),
    total_price_currency Nullable(String),
    image_url Nullable(String),
    favourite_count Nullable(Int32),
    view_count Nullable(Int32),
    user_id Nullable(UInt64),
    user_login Nullable(String),
    user_profile_url Nullable(String),
    created_at_ts Nullable(Int64),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    price_band_code LowCardinality(String),
    has_estimated_publication UInt8,
    metadata_json String
)
ENGINE = ReplacingMergeTree(version_token)
PARTITION BY intDiv(listing_id, 100000)
ORDER BY (listing_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS serving_listing_latest_probe (
    listing_id UInt64,
    version_token UInt64,
    probed_at DateTime64(3, 'UTC'),
    event_id String,
    manifest_id Nullable(String),
    probe_outcome LowCardinality(String),
    response_status Nullable(UInt16),
    requested_url String,
    final_url Nullable(String),
    reason Nullable(String),
    error_message Nullable(String),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    brand Nullable(String),
    condition_label Nullable(String),
    price_amount_cents Nullable(Int32),
    price_band_code LowCardinality(String),
    detail_json String,
    metadata_json String
)
ENGINE = ReplacingMergeTree(version_token)
PARTITION BY intDiv(listing_id, 100000)
ORDER BY (listing_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS serving_listing_latest_change (
    listing_id UInt64,
    version_token UInt64,
    occurred_at DateTime64(3, 'UTC'),
    event_id String,
    manifest_id Nullable(String),
    change_kind LowCardinality(String),
    previous_state_code Nullable(LowCardinality(String)),
    current_state_code Nullable(LowCardinality(String)),
    previous_basis_kind Nullable(LowCardinality(String)),
    current_basis_kind Nullable(LowCardinality(String)),
    previous_confidence_label Nullable(LowCardinality(String)),
    current_confidence_label Nullable(LowCardinality(String)),
    previous_confidence_score Nullable(Float32),
    current_confidence_score Nullable(Float32),
    previous_price_amount_cents Nullable(Int32),
    current_price_amount_cents Nullable(Int32),
    previous_favourite_count Nullable(Int32),
    current_favourite_count Nullable(Int32),
    previous_view_count Nullable(Int32),
    current_view_count Nullable(Int32),
    follow_up_miss_count Nullable(UInt16),
    probe_outcome Nullable(LowCardinality(String)),
    response_status Nullable(UInt16),
    primary_catalog_id Nullable(UInt64),
    primary_root_catalog_id Nullable(UInt64),
    root_title Nullable(String),
    category_path Nullable(String),
    brand Nullable(String),
    condition_label Nullable(String),
    price_band_code LowCardinality(String),
    change_summary Nullable(String),
    change_json String,
    metadata_json String
)
ENGINE = ReplacingMergeTree(version_token)
PARTITION BY intDiv(listing_id, 100000)
ORDER BY (listing_id)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_seen_to_hourly
TO rollup_listing_seen_hourly
AS
SELECT
    toStartOfHour(observed_at) AS bucket_start,
    listing_id,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code,
    sumState(toUInt64(1)) AS seen_events_state,
    uniqExactState(listing_id) AS unique_listing_state,
    sumState(toUInt64(1)) AS sighting_count_state,
    sumState(if(price_amount_cents IS NULL, toInt64(0), toInt64(price_amount_cents))) AS price_sum_state,
    sumState(if(price_amount_cents IS NULL, toUInt64(0), toUInt64(1))) AS price_count_state,
    sumState(if(favourite_count IS NULL, toInt64(0), toInt64(favourite_count))) AS favourite_sum_state,
    sumState(if(favourite_count IS NULL, toUInt64(0), toUInt64(1))) AS favourite_count_state,
    sumState(if(view_count IS NULL, toInt64(0), toInt64(view_count))) AS view_sum_state,
    sumState(if(view_count IS NULL, toUInt64(0), toUInt64(1))) AS view_count_state,
    minState(observed_at) AS first_seen_state,
    maxState(observed_at) AS last_seen_state
FROM fact_listing_seen_events
GROUP BY
    bucket_start,
    listing_id,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_seen_to_daily
TO rollup_listing_seen_daily
AS
SELECT
    toDate(observed_at) AS bucket_date,
    listing_id,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code,
    sumState(toUInt64(1)) AS seen_events_state,
    uniqExactState(listing_id) AS unique_listing_state,
    sumState(toUInt64(1)) AS sighting_count_state,
    sumState(if(price_amount_cents IS NULL, toInt64(0), toInt64(price_amount_cents))) AS price_sum_state,
    sumState(if(price_amount_cents IS NULL, toUInt64(0), toUInt64(1))) AS price_count_state,
    sumState(if(favourite_count IS NULL, toInt64(0), toInt64(favourite_count))) AS favourite_sum_state,
    sumState(if(favourite_count IS NULL, toUInt64(0), toUInt64(1))) AS favourite_count_state,
    sumState(if(view_count IS NULL, toInt64(0), toInt64(view_count))) AS view_sum_state,
    sumState(if(view_count IS NULL, toUInt64(0), toUInt64(1))) AS view_count_state,
    minState(observed_at) AS first_seen_state,
    maxState(observed_at) AS last_seen_state
FROM fact_listing_seen_events
GROUP BY
    bucket_date,
    listing_id,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_seen_to_category_daily
TO rollup_category_daily
AS
SELECT
    toDate(observed_at) AS bucket_date,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    condition_label,
    price_band_code,
    sumState(toUInt64(1)) AS seen_events_state,
    uniqExactState(listing_id) AS unique_listing_state,
    sumState(if(price_amount_cents IS NULL, toInt64(0), toInt64(price_amount_cents))) AS price_sum_state,
    sumState(if(price_amount_cents IS NULL, toUInt64(0), toUInt64(1))) AS price_count_state,
    sumState(if(favourite_count IS NULL, toInt64(0), toInt64(favourite_count))) AS favourite_sum_state,
    sumState(if(favourite_count IS NULL, toUInt64(0), toUInt64(1))) AS favourite_count_state,
    sumState(if(view_count IS NULL, toInt64(0), toInt64(view_count))) AS view_sum_state,
    sumState(if(view_count IS NULL, toUInt64(0), toUInt64(1))) AS view_count_state,
    minState(observed_at) AS first_seen_state,
    maxState(observed_at) AS last_seen_state
FROM fact_listing_seen_events
GROUP BY
    bucket_date,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    condition_label,
    price_band_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_seen_to_brand_daily
TO rollup_brand_daily
AS
SELECT
    toDate(observed_at) AS bucket_date,
    brand,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    condition_label,
    price_band_code,
    sumState(toUInt64(1)) AS seen_events_state,
    uniqExactState(listing_id) AS unique_listing_state,
    sumState(if(price_amount_cents IS NULL, toInt64(0), toInt64(price_amount_cents))) AS price_sum_state,
    sumState(if(price_amount_cents IS NULL, toUInt64(0), toUInt64(1))) AS price_count_state,
    sumState(if(favourite_count IS NULL, toInt64(0), toInt64(favourite_count))) AS favourite_sum_state,
    sumState(if(favourite_count IS NULL, toUInt64(0), toUInt64(1))) AS favourite_count_state,
    sumState(if(view_count IS NULL, toInt64(0), toInt64(view_count))) AS view_sum_state,
    sumState(if(view_count IS NULL, toUInt64(0), toUInt64(1))) AS view_count_state,
    minState(observed_at) AS first_seen_state,
    maxState(observed_at) AS last_seen_state
FROM fact_listing_seen_events
GROUP BY
    bucket_date,
    brand,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    condition_label,
    price_band_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_seen_to_latest_seen
TO serving_listing_latest_seen
AS
SELECT
    listing_id,
    toUnixTimestamp64Milli(observed_at) AS version_token,
    observed_at,
    event_id,
    manifest_id,
    run_id,
    canonical_url,
    source_url,
    title,
    brand,
    size_label,
    condition_label,
    price_amount_cents,
    price_currency,
    total_price_amount_cents,
    total_price_currency,
    image_url,
    favourite_count,
    view_count,
    user_id,
    user_login,
    user_profile_url,
    created_at_ts,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    price_band_code,
    has_estimated_publication,
    metadata_json
FROM fact_listing_seen_events;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_probe_to_latest_probe
TO serving_listing_latest_probe
AS
SELECT
    listing_id,
    toUnixTimestamp64Milli(probed_at) AS version_token,
    probed_at,
    event_id,
    manifest_id,
    probe_outcome,
    response_status,
    requested_url,
    final_url,
    reason,
    error_message,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_amount_cents,
    price_band_code,
    detail_json,
    metadata_json
FROM fact_listing_probe_events;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fact_listing_change_to_latest_change
TO serving_listing_latest_change
AS
SELECT
    listing_id,
    toUnixTimestamp64Milli(occurred_at) AS version_token,
    occurred_at,
    event_id,
    manifest_id,
    change_kind,
    previous_state_code,
    current_state_code,
    previous_basis_kind,
    current_basis_kind,
    previous_confidence_label,
    current_confidence_label,
    previous_confidence_score,
    current_confidence_score,
    previous_price_amount_cents,
    current_price_amount_cents,
    previous_favourite_count,
    current_favourite_count,
    previous_view_count,
    current_view_count,
    follow_up_miss_count,
    probe_outcome,
    response_status,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code,
    change_summary,
    change_json,
    metadata_json
FROM fact_listing_change_events;
