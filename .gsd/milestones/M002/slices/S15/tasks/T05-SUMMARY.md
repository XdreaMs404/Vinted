---
id: T05
parent: S15
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/query/feature_marts.py", "vinted_radar/query/overview_clickhouse.py", "vinted_radar/cli.py", "vinted_radar/platform/health.py", "infra/clickhouse/migrations/V002__serving_warehouse.sql", "tests/test_feature_marts.py", "tests/clickhouse_product_test_support.py"]
key_decisions: ["Expose AI-ready mart rows as stable ClickHouse views plus a grouped evidence-pack export surface instead of forcing downstream consumers to rescan raw fact/change tables ad hoc."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `python3 -m pytest tests/test_feature_marts.py -q` and the new mart/evidence-pack/CLI test file passed (3 passed). Also ran `python3 -m py_compile vinted_radar/query/feature_marts.py vinted_radar/query/overview_clickhouse.py vinted_radar/cli.py vinted_radar/platform/health.py tests/test_feature_marts.py tests/clickhouse_product_test_support.py` to confirm the touched Python modules compile cleanly."
completed_at: 2026-03-31T15:58:53.374Z
blocker_discovered: false
---

# T05: Added ClickHouse-backed feature marts and evidence-pack exports with explicit manifest/window traceability.

> Added ClickHouse-backed feature marts and evidence-pack exports with explicit manifest/window traceability.

## What Happened
---
id: T05
parent: S15
milestone: M002
key_files:
  - vinted_radar/query/feature_marts.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/cli.py
  - vinted_radar/platform/health.py
  - infra/clickhouse/migrations/V002__serving_warehouse.sql
  - tests/test_feature_marts.py
  - tests/clickhouse_product_test_support.py
key_decisions:
  - Expose AI-ready mart rows as stable ClickHouse views plus a grouped evidence-pack export surface instead of forcing downstream consumers to rescan raw fact/change tables ad hoc.
duration: ""
verification_result: passed
completed_at: 2026-03-31T15:58:53.375Z
blocker_discovered: false
---

# T05: Added ClickHouse-backed feature marts and evidence-pack exports with explicit manifest/window traceability.

**Added ClickHouse-backed feature marts and evidence-pack exports with explicit manifest/window traceability.**

## What Happened

Implemented the deferred warehouse mart surface now that truthful change facts exist. Added `vinted_radar/query/feature_marts.py` for listing-day, segment-day, price-change, state-transition, and grouped evidence-pack exports backed by ClickHouse rollups and change facts with manifest/window traceability. Exposed the new marts through `ClickHouseProductQueryAdapter`, added a `feature-marts` CLI command plus table-mode rendering, defined stable ClickHouse mart views in `infra/clickhouse/migrations/V002__serving_warehouse.sql`, and added focused tests with an extended scripted ClickHouse client.

## Verification

Ran `python3 -m pytest tests/test_feature_marts.py -q` and the new mart/evidence-pack/CLI test file passed (3 passed). Also ran `python3 -m py_compile vinted_radar/query/feature_marts.py vinted_radar/query/overview_clickhouse.py vinted_radar/cli.py vinted_radar/platform/health.py tests/test_feature_marts.py tests/clickhouse_product_test_support.py` to confirm the touched Python modules compile cleanly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_feature_marts.py -q` | 0 | ✅ pass | 539ms |
| 2 | `python3 -m py_compile vinted_radar/query/feature_marts.py vinted_radar/query/overview_clickhouse.py vinted_radar/cli.py vinted_radar/platform/health.py tests/test_feature_marts.py tests/clickhouse_product_test_support.py` | 0 | ✅ pass | 68ms |


## Deviations

Used `python3` instead of `python` for verification because this workstation does not expose a `python` launcher. Otherwise none.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/query/feature_marts.py`
- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/cli.py`
- `vinted_radar/platform/health.py`
- `infra/clickhouse/migrations/V002__serving_warehouse.sql`
- `tests/test_feature_marts.py`
- `tests/clickhouse_product_test_support.py`


## Deviations
Used `python3` instead of `python` for verification because this workstation does not expose a `python` launcher. Otherwise none.

## Known Issues
None.
