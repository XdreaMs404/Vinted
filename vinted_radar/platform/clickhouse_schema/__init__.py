from __future__ import annotations

from dataclasses import dataclass

CLICKHOUSE_SERVING_SCHEMA_VERSION = 2
_RAW_FACT_TTL_DAYS = 730
_ROLLUP_TTL_DAYS = 3650


@dataclass(frozen=True, slots=True)
class ClickHouseTableContract:
    name: str
    purpose: str
    engine: str
    grain: str
    partition_by: str
    order_by: tuple[str, ...]
    ttl_days: int | None = None


@dataclass(frozen=True, slots=True)
class ClickHouseMaterializedViewContract:
    name: str
    source_table: str
    target_table: str
    purpose: str


CLICKHOUSE_FACT_TABLE_CONTRACTS = (
    ClickHouseTableContract(
        name="fact_listing_seen_events",
        purpose="Append-only listing observation facts emitted from discovery batches with denormalized dimensions for hourly/daily serving rollups.",
        engine="ReplacingMergeTree(ingested_at)",
        grain="one observed listing event",
        partition_by="toYYYYMM(observed_at)",
        order_by=("observed_at", "listing_id", "event_id"),
        ttl_days=_RAW_FACT_TTL_DAYS,
    ),
    ClickHouseTableContract(
        name="fact_listing_probe_events",
        purpose="Append-only item-page probe facts carrying latest public availability outcomes, degraded-probe reasons, and denormalized listing dimensions.",
        engine="ReplacingMergeTree(ingested_at)",
        grain="one listing probe event",
        partition_by="toYYYYMM(probed_at)",
        order_by=("probed_at", "listing_id", "event_id"),
        ttl_days=_RAW_FACT_TTL_DAYS,
    ),
    ClickHouseTableContract(
        name="fact_listing_change_events",
        purpose="Derived append-only change facts for state transitions, price changes, engagement shifts, and follow-up miss transitions used by overview/explorer/detail reads.",
        engine="ReplacingMergeTree(ingested_at)",
        grain="one derived listing change event",
        partition_by="toYYYYMM(occurred_at)",
        order_by=("occurred_at", "listing_id", "change_kind", "event_id"),
        ttl_days=_RAW_FACT_TTL_DAYS,
    ),
)

CLICKHOUSE_ROLLUP_TABLE_CONTRACTS = (
    ClickHouseTableContract(
        name="rollup_listing_seen_hourly",
        purpose="Hourly observation aggregates per listing and key dimensions for explorer/detail history without rescanning raw events.",
        engine="AggregatingMergeTree",
        grain="one listing x hour bucket",
        partition_by="toYYYYMM(bucket_start)",
        order_by=("bucket_start", "listing_id", "primary_root_catalog_id", "primary_catalog_id", "brand"),
        ttl_days=_ROLLUP_TTL_DAYS,
    ),
    ClickHouseTableContract(
        name="rollup_listing_seen_daily",
        purpose="Daily observation aggregates per listing for detail timelines and AI-facing listing cadence features.",
        engine="AggregatingMergeTree",
        grain="one listing x day bucket",
        partition_by="toYYYYMM(bucket_date)",
        order_by=("bucket_date", "listing_id", "primary_root_catalog_id", "primary_catalog_id", "brand"),
        ttl_days=_ROLLUP_TTL_DAYS,
    ),
    ClickHouseTableContract(
        name="rollup_category_daily",
        purpose="Daily category-level serving metrics for overview and explorer comparison modules.",
        engine="AggregatingMergeTree",
        grain="one category x day bucket",
        partition_by="toYYYYMM(bucket_date)",
        order_by=("bucket_date", "primary_root_catalog_id", "primary_catalog_id", "price_band_code", "condition_label"),
        ttl_days=_ROLLUP_TTL_DAYS,
    ),
    ClickHouseTableContract(
        name="rollup_brand_daily",
        purpose="Daily brand-level serving metrics for overview and explorer comparison modules.",
        engine="AggregatingMergeTree",
        grain="one brand x day bucket",
        partition_by="toYYYYMM(bucket_date)",
        order_by=("bucket_date", "brand", "primary_root_catalog_id", "primary_catalog_id", "price_band_code"),
        ttl_days=_ROLLUP_TTL_DAYS,
    ),
)

CLICKHOUSE_SERVING_TABLE_CONTRACTS = (
    ClickHouseTableContract(
        name="serving_listing_latest_seen",
        purpose="Latest observed listing-card snapshot per listing for detail and explorer base rows.",
        engine="ReplacingMergeTree(version_token)",
        grain="one latest observation row per listing",
        partition_by="intDiv(listing_id, 100000)",
        order_by=("listing_id",),
        ttl_days=None,
    ),
    ClickHouseTableContract(
        name="serving_listing_latest_probe",
        purpose="Latest probe outcome per listing for current-state and degraded-acquisition reads.",
        engine="ReplacingMergeTree(version_token)",
        grain="one latest probe row per listing",
        partition_by="intDiv(listing_id, 100000)",
        order_by=("listing_id",),
        ttl_days=None,
    ),
    ClickHouseTableContract(
        name="serving_listing_latest_change",
        purpose="Latest derived change/state row per listing for current-state and transition reads.",
        engine="ReplacingMergeTree(version_token)",
        grain="one latest change row per listing",
        partition_by="intDiv(listing_id, 100000)",
        order_by=("listing_id",),
        ttl_days=None,
    ),
)

CLICKHOUSE_MATERIALIZED_VIEW_CONTRACTS = (
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_seen_to_hourly",
        source_table="fact_listing_seen_events",
        target_table="rollup_listing_seen_hourly",
        purpose="Aggregates raw listing observations into hourly listing buckets.",
    ),
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_seen_to_daily",
        source_table="fact_listing_seen_events",
        target_table="rollup_listing_seen_daily",
        purpose="Aggregates raw listing observations into daily listing buckets.",
    ),
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_seen_to_category_daily",
        source_table="fact_listing_seen_events",
        target_table="rollup_category_daily",
        purpose="Aggregates raw listing observations into daily category metrics.",
    ),
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_seen_to_brand_daily",
        source_table="fact_listing_seen_events",
        target_table="rollup_brand_daily",
        purpose="Aggregates raw listing observations into daily brand metrics.",
    ),
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_seen_to_latest_seen",
        source_table="fact_listing_seen_events",
        target_table="serving_listing_latest_seen",
        purpose="Maintains the latest observation snapshot per listing.",
    ),
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_probe_to_latest_probe",
        source_table="fact_listing_probe_events",
        target_table="serving_listing_latest_probe",
        purpose="Maintains the latest probe snapshot per listing.",
    ),
    ClickHouseMaterializedViewContract(
        name="mv_fact_listing_change_to_latest_change",
        source_table="fact_listing_change_events",
        target_table="serving_listing_latest_change",
        purpose="Maintains the latest derived change/state snapshot per listing.",
    ),
)

CLICKHOUSE_FACT_TABLES = tuple(contract.name for contract in CLICKHOUSE_FACT_TABLE_CONTRACTS)
CLICKHOUSE_ROLLUP_TABLES = tuple(contract.name for contract in CLICKHOUSE_ROLLUP_TABLE_CONTRACTS)
CLICKHOUSE_SERVING_TABLES = tuple(contract.name for contract in CLICKHOUSE_SERVING_TABLE_CONTRACTS)
CLICKHOUSE_ALL_TABLES = (
    *CLICKHOUSE_FACT_TABLES,
    *CLICKHOUSE_ROLLUP_TABLES,
    *CLICKHOUSE_SERVING_TABLES,
)
CLICKHOUSE_MATERIALIZED_VIEWS = tuple(contract.name for contract in CLICKHOUSE_MATERIALIZED_VIEW_CONTRACTS)

__all__ = [
    "CLICKHOUSE_ALL_TABLES",
    "CLICKHOUSE_FACT_TABLE_CONTRACTS",
    "CLICKHOUSE_FACT_TABLES",
    "CLICKHOUSE_MATERIALIZED_VIEW_CONTRACTS",
    "CLICKHOUSE_MATERIALIZED_VIEWS",
    "CLICKHOUSE_ROLLUP_TABLE_CONTRACTS",
    "CLICKHOUSE_ROLLUP_TABLES",
    "CLICKHOUSE_SERVING_SCHEMA_VERSION",
    "CLICKHOUSE_SERVING_TABLE_CONTRACTS",
    "CLICKHOUSE_SERVING_TABLES",
    "ClickHouseMaterializedViewContract",
    "ClickHouseTableContract",
]
