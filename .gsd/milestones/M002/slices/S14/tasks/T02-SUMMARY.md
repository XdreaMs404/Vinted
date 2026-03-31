---
id: T02
parent: S14
milestone: M002
provides:
  - Partial reconciliation service and cutover-status helper scaffolding for the historical cutover slice.
key_files:
  - vinted_radar/services/reconciliation.py
  - vinted_radar/platform/health.py
  - vinted_radar/platform/postgres_repository.py
  - tests/platform_test_fakes.py
  - vinted_radar/platform/__init__.py
key_decisions:
  - Reconciliation should compare SQLite source baselines against PostgreSQL current-state tables, ClickHouse fact tables, and object-storage Parquet-backed manifests using one explicit report shape.
  - Cutover observability should expose an explicit mode label and warnings instead of leaving operators to infer deployment state from four raw booleans.
patterns_established:
  - Reconciliation snapshots are modeled as row-count plus optional time-window pairs so stores with different physical layouts can still be compared consistently.
observability_surfaces:
  - Partial cutover summary helper in platform health code; CLI/dashboard surfaces not wired yet.
duration: timed-out
verification_result: partial
completed_at: 2026-03-31T12:52:10+02:00
blocker_discovered: false
---

# T02: Reconciliation + cutover controls

**Started the reconciliation service and explicit cutover-state helper, but the task timed out before CLI wiring, dashboard/runtime exposure, and the planned test suite were finished.**

## Slice Plan Excerpt
Source: `.gsd/milestones/M002/slices/S14/S14-PLAN.md`
**Goal:** Migrate historical continuity, cut reads and writes over to the new platform end to end, and retire the SQLite-heavy live loop from the real product path without losing auditability or product truth.
**Demo:** After this: After this: historical SQLite evidence is backfilled into PostgreSQL, ClickHouse, and the Parquet lake, the product reads the new platform end to end, and the live collector no longer depends on heavyweight SQLite history tables.

## What Happened

I implemented the core reconciliation/report scaffolding in `vinted_radar/services/reconciliation.py`, including SQLite baseline collection, PostgreSQL table reconciliation hooks, ClickHouse fact-table reconciliation hooks, and object-storage manifest/parquet reconciliation against historical backfill datasets. I also added a reusable cutover-state summary helper in `vinted_radar/platform/health.py`, exported it through `vinted_radar/platform/__init__.py`, added a generic PostgreSQL table snapshot helper to `vinted_radar/platform/postgres_repository.py`, and extended `tests/platform_test_fakes.py` with S3 object listing support needed for manifest reconciliation tests.

The unit timed out before I could finish the remaining contract work:
- wire `run_reconciliation` into `vinted_radar/cli.py` as the user-facing reconciliation command
- expose the cutover summary in runtime and dashboard health diagnostics
- add `tests/test_reconciliation.py`
- run the required verification command `python -m pytest tests/test_reconciliation.py -q`

## Verification

Only a minimal syntax check ran on the files already touched. The required reconciliation test suite was not created or executed before timeout, so task verification is incomplete.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/services/reconciliation.py vinted_radar/platform/health.py vinted_radar/platform/postgres_repository.py vinted_radar/platform/__init__.py tests/platform_test_fakes.py vinted_radar/cli.py vinted_radar/dashboard.py` | 0 | ✅ pass | not recorded |

## Diagnostics

Resume from the partially implemented reconciliation path in `vinted_radar/services/reconciliation.py`. The next concrete steps are:
1. finish CLI imports and add a `platform-reconcile`-style command that calls `run_reconciliation`
2. add a small cutover snapshot loader/helper in CLI and dashboard so runtime-status and `/health` include the explicit mode/warnings
3. add `tests/test_reconciliation.py` covering the reconciliation report, runtime/dashboard cutover surfaces, and platform health rendering
4. run `python3 -m pytest tests/test_reconciliation.py -q`
5. only after that, write the final success summary and complete the task in GSD

## Deviations

Timeout forced an early wrap-up with a partial durable artifact instead of a completed task handoff.

## Known Issues

- `vinted_radar/cli.py` was only partially updated and does not yet expose the reconciliation command or cutover diagnostics.
- `vinted_radar/dashboard.py` was not updated yet.
- `tests/test_reconciliation.py` does not exist yet.
- The task remains incomplete and should not be marked done until the missing wiring and verification are finished.

## Files Created/Modified

- `vinted_radar/services/reconciliation.py` — added the new reconciliation report/service scaffolding.
- `vinted_radar/platform/health.py` — added explicit cutover-mode summarization and health render lines.
- `vinted_radar/platform/postgres_repository.py` — added a generic reconciliation table snapshot helper.
- `tests/platform_test_fakes.py` — added object listing support for fake S3-backed reconciliation tests.
- `vinted_radar/platform/__init__.py` — exported the new cutover-health helper types/functions.
