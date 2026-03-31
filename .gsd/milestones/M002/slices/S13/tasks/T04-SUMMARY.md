---
id: T04
parent: S13
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/dashboard.py", "scripts/verify_clickhouse_routes.py", "tests/test_clickhouse_parity.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S13/tasks/T04-SUMMARY.md"]
key_decisions: ["D052: normalize probe presentation at the dashboard serialization and route-proof layer instead of forcing every backend to emit the repository’s flat row shape."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran python3 -m py_compile on the touched files, ran the task-level parity suite with python3 -m pytest tests/test_clickhouse_parity.py -q, and then ran the full slice verification sweep across tests/test_clickhouse_schema.py, tests/test_clickhouse_ingest.py, tests/test_clickhouse_queries.py, tests/test_dashboard.py, and tests/test_clickhouse_parity.py. All checks passed, including the end-to-end route-proof coverage inside the new parity suite."
completed_at: 2026-03-31T11:40:34.442Z
blocker_discovered: false
---

# T04: Added ClickHouse parity tests and a reusable route verifier, and fixed dashboard probe rendering so overview, explorer, and detail stay cutover-consistent.

> Added ClickHouse parity tests and a reusable route verifier, and fixed dashboard probe rendering so overview, explorer, and detail stay cutover-consistent.

## What Happened
---
id: T04
parent: S13
milestone: M002
key_files:
  - vinted_radar/dashboard.py
  - scripts/verify_clickhouse_routes.py
  - tests/test_clickhouse_parity.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S13/tasks/T04-SUMMARY.md
key_decisions:
  - D052: normalize probe presentation at the dashboard serialization and route-proof layer instead of forcing every backend to emit the repository’s flat row shape.
duration: ""
verification_result: passed
completed_at: 2026-03-31T11:40:34.443Z
blocker_discovered: false
---

# T04: Added ClickHouse parity tests and a reusable route verifier, and fixed dashboard probe rendering so overview, explorer, and detail stay cutover-consistent.

**Added ClickHouse parity tests and a reusable route verifier, and fixed dashboard probe rendering so overview, explorer, and detail stay cutover-consistent.**

## What Happened

Added ClickHouse parity coverage for representative overview, explorer, and listing-detail payloads against the SQLite-era repository contract, plus a reusable route-proof verifier that starts temporary repository and ClickHouse-backed dashboard servers, checks dashboard/explorer/detail/health parity, and records route latency. Fixed dashboard explorer/overview serialization so nested latest_probe evidence from the ClickHouse adapter renders the same user-visible probe state as the flat repository row shape, then recorded that cutover rule in project knowledge.

## Verification

Ran python3 -m py_compile on the touched files, ran the task-level parity suite with python3 -m pytest tests/test_clickhouse_parity.py -q, and then ran the full slice verification sweep across tests/test_clickhouse_schema.py, tests/test_clickhouse_ingest.py, tests/test_clickhouse_queries.py, tests/test_dashboard.py, and tests/test_clickhouse_parity.py. All checks passed, including the end-to-end route-proof coverage inside the new parity suite.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/dashboard.py scripts/verify_clickhouse_routes.py tests/test_clickhouse_parity.py` | 0 | ✅ pass | 137ms |
| 2 | `python3 -m pytest tests/test_clickhouse_parity.py -q` | 0 | ✅ pass | 1632ms |
| 3 | `python3 -m pytest tests/test_clickhouse_schema.py tests/test_clickhouse_ingest.py tests/test_clickhouse_queries.py tests/test_dashboard.py tests/test_clickhouse_parity.py -q` | 0 | ✅ pass | 2954ms |


## Deviations

Used python3 instead of python because this shell does not expose a python alias. No slice-plan invalidation.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/dashboard.py`
- `scripts/verify_clickhouse_routes.py`
- `tests/test_clickhouse_parity.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S13/tasks/T04-SUMMARY.md`


## Deviations
Used python3 instead of python because this shell does not expose a python alias. No slice-plan invalidation.

## Known Issues
None.
