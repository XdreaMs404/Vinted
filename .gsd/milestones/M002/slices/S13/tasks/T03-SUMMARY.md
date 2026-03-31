---
id: T03
parent: S13
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/dashboard.py", "vinted_radar/query/overview_clickhouse.py", "vinted_radar/query/detail_clickhouse.py", "vinted_radar/query/explorer_clickhouse.py", "tests/clickhouse_product_test_support.py", "tests/test_clickhouse_queries.py", "tests/test_dashboard.py", ".gsd/milestones/M002/slices/S13/tasks/T03-SUMMARY.md"]
key_decisions: ["D051: switch dashboard product reads through a repository-shaped ClickHouse adapter so route payload builders stay stable during cutover."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the touched Python modules compile with python3 -m py_compile, then ran python3 -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q. The new tests cover the ClickHouse adapter overview/explorer/detail contracts, same-now cache reuse, and dashboard route delivery over the ClickHouse-backed product adapter."
completed_at: 2026-03-31T11:27:22.081Z
blocker_discovered: false
---

# T03: Added a repository-shaped ClickHouse query adapter so overview, explorer, and listing detail can read analytical state from ClickHouse while preserving the existing dashboard route contracts.

> Added a repository-shaped ClickHouse query adapter so overview, explorer, and listing detail can read analytical state from ClickHouse while preserving the existing dashboard route contracts.

## What Happened
---
id: T03
parent: S13
milestone: M002
key_files:
  - vinted_radar/dashboard.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/query/detail_clickhouse.py
  - vinted_radar/query/explorer_clickhouse.py
  - tests/clickhouse_product_test_support.py
  - tests/test_clickhouse_queries.py
  - tests/test_dashboard.py
  - .gsd/milestones/M002/slices/S13/tasks/T03-SUMMARY.md
key_decisions:
  - D051: switch dashboard product reads through a repository-shaped ClickHouse adapter so route payload builders stay stable during cutover.
duration: ""
verification_result: passed
completed_at: 2026-03-31T11:27:22.081Z
blocker_discovered: false
---

# T03: Added a repository-shaped ClickHouse query adapter so overview, explorer, and listing detail can read analytical state from ClickHouse while preserving the existing dashboard route contracts.

**Added a repository-shaped ClickHouse query adapter so overview, explorer, and listing detail can read analytical state from ClickHouse while preserving the existing dashboard route contracts.**

## What Happened

Added vinted_radar.query.overview_clickhouse.ClickHouseProductQueryAdapter, a repository-shaped backend that exposes overview_snapshot, explorer_snapshot, listing_explorer_page, listing_state_inputs, listing_history, and peer-price context lookups over ClickHouse facts and latest-serving tables. Extended vinted_radar.query.detail_clickhouse with repository-shaped state-input and history loaders, added an explorer snapshot helper in vinted_radar.query.explorer_clickhouse, and wired DashboardApplication so routes can serve the same overview/explorer/detail payloads from ClickHouse either by explicit injection or by polyglot-read configuration. Kept runtime and coverage delegation on the existing repository boundary and surfaced the active backend through request.primary_payload_source in the dashboard API for operator-visible diagnostics.

## Verification

Verified the touched Python modules compile with python3 -m py_compile, then ran python3 -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q. The new tests cover the ClickHouse adapter overview/explorer/detail contracts, same-now cache reuse, and dashboard route delivery over the ClickHouse-backed product adapter.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/dashboard.py vinted_radar/query/detail_clickhouse.py vinted_radar/query/explorer_clickhouse.py vinted_radar/query/overview_clickhouse.py tests/clickhouse_product_test_support.py tests/test_clickhouse_queries.py tests/test_dashboard.py` | 0 | ✅ pass | 90ms |
| 2 | `python3 -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q` | 0 | ✅ pass | 850ms |


## Deviations

Used python3 instead of python because this shell does not expose a python alias. No slice-plan invalidation.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/dashboard.py`
- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/query/detail_clickhouse.py`
- `vinted_radar/query/explorer_clickhouse.py`
- `tests/clickhouse_product_test_support.py`
- `tests/test_clickhouse_queries.py`
- `tests/test_dashboard.py`
- `.gsd/milestones/M002/slices/S13/tasks/T03-SUMMARY.md`


## Deviations
Used python3 instead of python because this shell does not expose a python alias. No slice-plan invalidation.

## Known Issues
None.
