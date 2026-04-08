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
TTL toDateTime(observed_at) + INTERVAL 730 DAY
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
TTL toDateTime(probed_at) + INTERVAL 730 DAY
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
    previous_state_code LowCardinality(Nullable(String)),
    current_state_code LowCardinality(Nullable(String)),
    previous_basis_kind LowCardinality(Nullable(String)),
    current_basis_kind LowCardinality(Nullable(String)),
    previous_confidence_label LowCardinality(Nullable(String)),
    current_confidence_label LowCardinality(Nullable(String)),
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
    probe_outcome LowCardinality(Nullable(String)),
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
TTL toDateTime(occurred_at) + INTERVAL 730 DAY
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
SETTINGS index_granularity = 8192, allow_nullable_key = 1;

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
SETTINGS index_granularity = 8192, allow_nullable_key = 1;

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
SETTINGS index_granularity = 8192, allow_nullable_key = 1;

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
SETTINGS index_granularity = 8192, allow_nullable_key = 1;

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
    previous_state_code LowCardinality(Nullable(String)),
    current_state_code LowCardinality(Nullable(String)),
    previous_basis_kind LowCardinality(Nullable(String)),
    current_basis_kind LowCardinality(Nullable(String)),
    previous_confidence_label LowCardinality(Nullable(String)),
    current_confidence_label LowCardinality(Nullable(String)),
    previous_confidence_score Nullable(Float32),
    current_confidence_score Nullable(Float32),
    previous_price_amount_cents Nullable(Int32),
    current_price_amount_cents Nullable(Int32),
    previous_favourite_count Nullable(Int32),
    current_favourite_count Nullable(Int32),
    previous_view_count Nullable(Int32),
    current_view_count Nullable(Int32),
    follow_up_miss_count Nullable(UInt16),
    probe_outcome LowCardinality(Nullable(String)),
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
    sumState(toInt64(ifNull(price_amount_cents, 0))) AS price_sum_state,
    sumState(toUInt64(price_amount_cents IS NOT NULL)) AS price_count_state,
    sumState(toInt64(ifNull(favourite_count, 0))) AS favourite_sum_state,
    sumState(toUInt64(favourite_count IS NOT NULL)) AS favourite_count_state,
    sumState(toInt64(ifNull(view_count, 0))) AS view_sum_state,
    sumState(toUInt64(view_count IS NOT NULL)) AS view_count_state,
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
    sumState(toInt64(ifNull(price_amount_cents, 0))) AS price_sum_state,
    sumState(toUInt64(price_amount_cents IS NOT NULL)) AS price_count_state,
    sumState(toInt64(ifNull(favourite_count, 0))) AS favourite_sum_state,
    sumState(toUInt64(favourite_count IS NOT NULL)) AS favourite_count_state,
    sumState(toInt64(ifNull(view_count, 0))) AS view_sum_state,
    sumState(toUInt64(view_count IS NOT NULL)) AS view_count_state,
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
    sumState(toInt64(ifNull(price_amount_cents, 0))) AS price_sum_state,
    sumState(toUInt64(price_amount_cents IS NOT NULL)) AS price_count_state,
    sumState(toInt64(ifNull(favourite_count, 0))) AS favourite_sum_state,
    sumState(toUInt64(favourite_count IS NOT NULL)) AS favourite_count_state,
    sumState(toInt64(ifNull(view_count, 0))) AS view_sum_state,
    sumState(toUInt64(view_count IS NOT NULL)) AS view_count_state,
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
    sumState(toInt64(ifNull(price_amount_cents, 0))) AS price_sum_state,
    sumState(toUInt64(price_amount_cents IS NOT NULL)) AS price_count_state,
    sumState(toInt64(ifNull(favourite_count, 0))) AS favourite_sum_state,
    sumState(toUInt64(favourite_count IS NOT NULL)) AS favourite_count_state,
    sumState(toInt64(ifNull(view_count, 0))) AS view_sum_state,
    sumState(toUInt64(view_count IS NOT NULL)) AS view_count_state,
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

CREATE VIEW IF NOT EXISTS mart_listing_day AS
WITH trace AS (
    SELECT
        toDate(observed_at) AS bucket_date,
        listing_id,
        arraySort(groupUniqArrayIf(manifest_id, manifest_id IS NOT NULL)) AS manifest_ids,
        arraySort(groupUniqArrayIf(source_event_id, source_event_id IS NOT NULL)) AS source_event_ids,
        arraySort(groupUniqArrayIf(run_id, run_id IS NOT NULL)) AS run_ids,
        min(observed_at) AS window_started_at,
        max(observed_at) AS window_ended_at
    FROM fact_listing_seen_events
    GROUP BY bucket_date, listing_id
)
SELECT
    daily.bucket_date,
    daily.listing_id,
    daily.primary_catalog_id,
    daily.primary_root_catalog_id,
    daily.root_title,
    daily.category_path,
    daily.brand,
    daily.condition_label,
    daily.price_band_code,
    multiIf(
        daily.price_band_code = 'under_20_eur', '< 20 €',
        daily.price_band_code = '20_to_39_eur', '20–39 €',
        daily.price_band_code = '40_plus_eur', '40 € et plus',
        'Prix indisponible'
    ) AS price_band_label,
    toUInt64(finalizeAggregation(daily.seen_events_state)) AS seen_events,
    toUInt64(finalizeAggregation(daily.unique_listing_state)) AS unique_listing_count,
    toUInt64(finalizeAggregation(daily.sighting_count_state)) AS sighting_count,
    if(
        finalizeAggregation(daily.price_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(daily.price_sum_state)) / finalizeAggregation(daily.price_count_state), 2)
    ) AS average_price_amount_cents,
    if(
        finalizeAggregation(daily.favourite_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(daily.favourite_sum_state)) / finalizeAggregation(daily.favourite_count_state), 2)
    ) AS average_favourite_count,
    if(
        finalizeAggregation(daily.view_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(daily.view_sum_state)) / finalizeAggregation(daily.view_count_state), 2)
    ) AS average_view_count,
    finalizeAggregation(daily.first_seen_state) AS first_seen_at,
    finalizeAggregation(daily.last_seen_state) AS last_seen_at,
    trace.window_started_at,
    trace.window_ended_at,
    trace.manifest_ids,
    trace.source_event_ids,
    trace.run_ids
FROM rollup_listing_seen_daily AS daily
LEFT JOIN trace USING (bucket_date, listing_id);

CREATE VIEW IF NOT EXISTS mart_segment_day AS
WITH category_trace AS (
    SELECT
        toDate(observed_at) AS bucket_date,
        primary_catalog_id,
        primary_root_catalog_id,
        root_title,
        category_path,
        condition_label,
        price_band_code,
        arraySort(groupUniqArrayIf(manifest_id, manifest_id IS NOT NULL)) AS manifest_ids,
        arraySort(groupUniqArrayIf(source_event_id, source_event_id IS NOT NULL)) AS source_event_ids,
        arraySort(groupUniqArrayIf(run_id, run_id IS NOT NULL)) AS run_ids,
        min(observed_at) AS window_started_at,
        max(observed_at) AS window_ended_at
    FROM fact_listing_seen_events
    GROUP BY bucket_date, primary_catalog_id, primary_root_catalog_id, root_title, category_path, condition_label, price_band_code
),
brand_trace AS (
    SELECT
        toDate(observed_at) AS bucket_date,
        brand,
        primary_catalog_id,
        primary_root_catalog_id,
        root_title,
        category_path,
        condition_label,
        price_band_code,
        arraySort(groupUniqArrayIf(manifest_id, manifest_id IS NOT NULL)) AS manifest_ids,
        arraySort(groupUniqArrayIf(source_event_id, source_event_id IS NOT NULL)) AS source_event_ids,
        arraySort(groupUniqArrayIf(run_id, run_id IS NOT NULL)) AS run_ids,
        min(observed_at) AS window_started_at,
        max(observed_at) AS window_ended_at
    FROM fact_listing_seen_events
    GROUP BY bucket_date, brand, primary_catalog_id, primary_root_catalog_id, root_title, category_path, condition_label, price_band_code
)
SELECT
    category.bucket_date,
    'category' AS segment_lens,
    if(category.primary_catalog_id IS NULL, ifNull(category.root_title, 'unknown-root'), toString(category.primary_catalog_id)) AS segment_value,
    ifNull(category.category_path, ifNull(category.root_title, 'Catégorie inconnue')) AS segment_label,
    category.primary_catalog_id,
    category.primary_root_catalog_id,
    category.root_title,
    category.category_path,
    CAST(NULL AS Nullable(String)) AS brand,
    category.condition_label,
    category.price_band_code,
    multiIf(
        category.price_band_code = 'under_20_eur', '< 20 €',
        category.price_band_code = '20_to_39_eur', '20–39 €',
        category.price_band_code = '40_plus_eur', '40 € et plus',
        'Prix indisponible'
    ) AS price_band_label,
    toUInt64(finalizeAggregation(category.seen_events_state)) AS seen_events,
    toUInt64(finalizeAggregation(category.unique_listing_state)) AS unique_listing_count,
    if(
        finalizeAggregation(category.price_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(category.price_sum_state)) / finalizeAggregation(category.price_count_state), 2)
    ) AS average_price_amount_cents,
    if(
        finalizeAggregation(category.favourite_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(category.favourite_sum_state)) / finalizeAggregation(category.favourite_count_state), 2)
    ) AS average_favourite_count,
    if(
        finalizeAggregation(category.view_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(category.view_sum_state)) / finalizeAggregation(category.view_count_state), 2)
    ) AS average_view_count,
    finalizeAggregation(category.first_seen_state) AS first_seen_at,
    finalizeAggregation(category.last_seen_state) AS last_seen_at,
    category_trace.window_started_at,
    category_trace.window_ended_at,
    category_trace.manifest_ids,
    category_trace.source_event_ids,
    category_trace.run_ids
FROM rollup_category_daily AS category
LEFT JOIN category_trace
    ON category_trace.bucket_date = category.bucket_date
   AND ifNull(category_trace.primary_catalog_id, toUInt64(0)) = ifNull(category.primary_catalog_id, toUInt64(0))
   AND ifNull(category_trace.primary_root_catalog_id, toUInt64(0)) = ifNull(category.primary_root_catalog_id, toUInt64(0))
   AND ifNull(category_trace.root_title, '') = ifNull(category.root_title, '')
   AND ifNull(category_trace.category_path, '') = ifNull(category.category_path, '')
   AND ifNull(category_trace.condition_label, '') = ifNull(category.condition_label, '')
   AND category_trace.price_band_code = category.price_band_code
UNION ALL
SELECT
    brand_daily.bucket_date,
    'brand' AS segment_lens,
    ifNull(brand_daily.brand, 'unknown-brand') AS segment_value,
    ifNull(brand_daily.brand, 'Marque inconnue') AS segment_label,
    brand_daily.primary_catalog_id,
    brand_daily.primary_root_catalog_id,
    brand_daily.root_title,
    brand_daily.category_path,
    brand_daily.brand,
    brand_daily.condition_label,
    brand_daily.price_band_code,
    multiIf(
        brand_daily.price_band_code = 'under_20_eur', '< 20 €',
        brand_daily.price_band_code = '20_to_39_eur', '20–39 €',
        brand_daily.price_band_code = '40_plus_eur', '40 € et plus',
        'Prix indisponible'
    ) AS price_band_label,
    toUInt64(finalizeAggregation(brand_daily.seen_events_state)) AS seen_events,
    toUInt64(finalizeAggregation(brand_daily.unique_listing_state)) AS unique_listing_count,
    if(
        finalizeAggregation(brand_daily.price_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(brand_daily.price_sum_state)) / finalizeAggregation(brand_daily.price_count_state), 2)
    ) AS average_price_amount_cents,
    if(
        finalizeAggregation(brand_daily.favourite_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(brand_daily.favourite_sum_state)) / finalizeAggregation(brand_daily.favourite_count_state), 2)
    ) AS average_favourite_count,
    if(
        finalizeAggregation(brand_daily.view_count_state) = 0,
        CAST(NULL AS Nullable(Float64)),
        round(toFloat64(finalizeAggregation(brand_daily.view_sum_state)) / finalizeAggregation(brand_daily.view_count_state), 2)
    ) AS average_view_count,
    finalizeAggregation(brand_daily.first_seen_state) AS first_seen_at,
    finalizeAggregation(brand_daily.last_seen_state) AS last_seen_at,
    brand_trace.window_started_at,
    brand_trace.window_ended_at,
    brand_trace.manifest_ids,
    brand_trace.source_event_ids,
    brand_trace.run_ids
FROM rollup_brand_daily AS brand_daily
LEFT JOIN brand_trace
    ON brand_trace.bucket_date = brand_daily.bucket_date
   AND ifNull(brand_trace.brand, '') = ifNull(brand_daily.brand, '')
   AND ifNull(brand_trace.primary_catalog_id, toUInt64(0)) = ifNull(brand_daily.primary_catalog_id, toUInt64(0))
   AND ifNull(brand_trace.primary_root_catalog_id, toUInt64(0)) = ifNull(brand_daily.primary_root_catalog_id, toUInt64(0))
   AND ifNull(brand_trace.root_title, '') = ifNull(brand_daily.root_title, '')
   AND ifNull(brand_trace.category_path, '') = ifNull(brand_daily.category_path, '')
   AND ifNull(brand_trace.condition_label, '') = ifNull(brand_daily.condition_label, '')
   AND brand_trace.price_band_code = brand_daily.price_band_code;

CREATE VIEW IF NOT EXISTS mart_price_change AS
SELECT
    occurred_at,
    change_date,
    listing_id,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code,
    previous_price_amount_cents,
    current_price_amount_cents,
    previous_total_price_amount_cents,
    current_total_price_amount_cents,
    previous_favourite_count,
    current_favourite_count,
    previous_view_count,
    current_view_count,
    follow_up_miss_count,
    manifest_id,
    source_event_id,
    source_event_type,
    change_summary,
    change_json,
    metadata_json
FROM fact_listing_change_events
WHERE change_kind = 'price_change';

CREATE VIEW IF NOT EXISTS mart_state_transition AS
SELECT
    occurred_at,
    change_date,
    listing_id,
    primary_catalog_id,
    primary_root_catalog_id,
    root_title,
    category_path,
    brand,
    condition_label,
    price_band_code,
    previous_state_code,
    current_state_code,
    previous_basis_kind,
    current_basis_kind,
    previous_confidence_label,
    current_confidence_label,
    previous_confidence_score,
    current_confidence_score,
    follow_up_miss_count,
    probe_outcome,
    response_status,
    manifest_id,
    source_event_id,
    source_event_type,
    change_summary,
    change_json,
    metadata_json
FROM fact_listing_change_events
WHERE change_kind = 'state_transition';
