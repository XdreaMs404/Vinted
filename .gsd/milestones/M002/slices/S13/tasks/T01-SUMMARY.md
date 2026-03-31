---
id: T01
parent: S13
milestone: M002
provides: []
requires: []
affects: []
key_files: ["infra/clickhouse/migrations/V002__serving_warehouse.sql", "vinted_radar/platform/clickhouse_schema/__init__.py", "tests/test_clickhouse_schema.py", "vinted_radar/platform/config.py", "vinted_radar/platform/__init__.py", "tests/test_platform_config.py", "tests/test_data_platform_bootstrap.py", "tests/test_data_platform_smoke.py"]
key_decisions: ["D047: use 730-day raw fact TTL, 3650-day serving rollups, and latest-per-listing serving tables fed by materialized views."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the touched Python modules compile with python3 -m py_compile, and verified the required schema contract test passes with python3 -m pytest tests/test_clickhouse_schema.py -q. The schema test confirms migration application, raw-fact/rollup/latest-serving object creation, TTL policy, and materialized-view wiring."
completed_at: 2026-03-31T06:41:20.031Z
blocker_discovered: false
---

# T01: Added the ClickHouse warehouse V002 schema with raw facts, rollups, latest-serving primitives, and schema tests.

> Added the ClickHouse warehouse V002 schema with raw facts, rollups, latest-serving primitives, and schema tests.

## What Happened
---
id: T01
parent: S13
milestone: M002
key_files:
  - infra/clickhouse/migrations/V002__serving_warehouse.sql
  - vinted_radar/platform/clickhouse_schema/__init__.py
  - tests/test_clickhouse_schema.py
  - vinted_radar/platform/config.py
  - vinted_radar/platform/__init__.py
  - tests/test_platform_config.py
  - tests/test_data_platform_bootstrap.py
  - tests/test_data_platform_smoke.py
key_decisions:
  - D047: use 730-day raw fact TTL, 3650-day serving rollups, and latest-per-listing serving tables fed by materialized views.
duration: ""
verification_result: passed
completed_at: 2026-03-31T06:41:20.031Z
blocker_discovered: false
---

# T01: Added the ClickHouse warehouse V002 schema with raw facts, rollups, latest-serving primitives, and schema tests.

**Added the ClickHouse warehouse V002 schema with raw facts, rollups, latest-serving primitives, and schema tests.**

## What Happened

Added the ClickHouse warehouse baseline for S13 by introducing a new schema contract module, a V002 ClickHouse migration, and contract tests. The migration adds append-only listing-seen, listing-probe, and derived listing-change fact tables with monthly partitions and 730-day TTL; AggregatingMergeTree listing-hourly/listing-daily/category-daily/brand-daily rollups with 3650-day retention; and ReplacingMergeTree latest-seen/latest-probe/latest-change serving tables populated by materialized views. I also updated platform config and platform bootstrap/smoke expectations so ClickHouse schema version 2 is treated as the live baseline across the codebase.

## Verification

Verified the touched Python modules compile with python3 -m py_compile, and verified the required schema contract test passes with python3 -m pytest tests/test_clickhouse_schema.py -q. The schema test confirms migration application, raw-fact/rollup/latest-serving object creation, TTL policy, and materialized-view wiring.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/platform/config.py vinted_radar/platform/__init__.py vinted_radar/platform/clickhouse_schema/__init__.py tests/test_clickhouse_schema.py tests/test_data_platform_bootstrap.py tests/test_platform_config.py` | 0 | ✅ pass | 56ms |
| 2 | `python3 -m pytest tests/test_clickhouse_schema.py -q` | 0 | ✅ pass | 347ms |


## Deviations

Updated platform config/export/bootstrap expectations so ClickHouse schema v2 is the active baseline rather than leaving V002 only partially wired. No slice-plan invalidation.

## Known Issues

None.

## Files Created/Modified

- `infra/clickhouse/migrations/V002__serving_warehouse.sql`
- `vinted_radar/platform/clickhouse_schema/__init__.py`
- `tests/test_clickhouse_schema.py`
- `vinted_radar/platform/config.py`
- `vinted_radar/platform/__init__.py`
- `tests/test_platform_config.py`
- `tests/test_data_platform_bootstrap.py`
- `tests/test_data_platform_smoke.py`


## Deviations
Updated platform config/export/bootstrap expectations so ClickHouse schema v2 is the active baseline rather than leaving V002 only partially wired. No slice-plan invalidation.

## Known Issues
None.
