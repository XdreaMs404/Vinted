---
id: T04
parent: S13
milestone: M002
provides:
  - Durable recovery state for the unfinished analytical parity and route-proof work.
key_files:
  - .gsd/milestones/M002/slices/S13/tasks/T04-SUMMARY.md
key_decisions:
  - Do not mark T04 complete without landing the missing ClickHouse adapter, parity tests, and route-proof artifacts.
patterns_established:
  - When auto-mode recovery fires before implementation is durable, write the task summary immediately with exact resume steps and known-good findings.
observability_surfaces:
  - none
duration: partial
verification_result: not-run
completed_at: 2026-03-31T08:23:20+02:00
blocker_discovered: false
---

# T04: Analytical parity + route proof

**Recovery artifact only: T04 is not complete yet; this summary preserves the exact local state needed to resume safely.**

## Slice Plan Excerpt
Source: `.gsd/milestones/M002/slices/S13/S13-PLAN.md`
**Goal:** Introduce the long-term serving warehouse in ClickHouse so overview, explorer, detail, and future AI-facing analytics read from raw facts and materialized rollups instead of SQLite full-history scans.
**Demo:** After this: After this: overview, explorer, and listing-detail analytics read from ClickHouse raw facts and materialized rollups rather than SQLite full-history scans.

## What Happened

I verified the current slice state after the failed auto-mode attempt and confirmed that the durable artifact problem was real for this unit: `T04-SUMMARY.md` was missing when recovery started. I then checked the local codebase to identify whether T04 could be completed immediately or whether a recovery artifact was required first.

What is observably true right now:

- `vinted_radar/query/detail_clickhouse.py` exists and contains the first ClickHouse helper queries.
- `vinted_radar/query/explorer_clickhouse.py` exists and contains pure-Python explorer/comparison helpers.
- `vinted_radar/query/overview_clickhouse.py` does **not** exist.
- `vinted_radar/query/__init__.py` does **not** exist, so there is no ClickHouse product-query adapter yet.
- `vinted_radar/dashboard.py` is still wired directly to `RadarRepository` for overview, explorer, and detail routes.
- `tests/test_clickhouse_queries.py` does **not** exist.
- `tests/test_clickhouse_parity.py` does **not** exist.
- The platform cutover flag already exists as `config.cutover.enable_polyglot_reads` in `vinted_radar/platform/config.py`.
- The SQLite repository already defines the exact compatibility contract the adapter must preserve (`overview_snapshot`, `explorer_filter_options`, `explorer_snapshot`, `listing_explorer_page`, `listing_state_inputs`, `listing_price_context_peer_prices`, `listing_history`, `runtime_status`, `coverage_summary`, `freshness_summary`).

Because the missing adapter and parity tests are still substantial unfinished work, full truthful completion was not possible during this recovery turn. I wrote this summary immediately so the unit can resume without losing the investigation already performed.

## Exact Resume Steps

Resume in this order:

1. Create `vinted_radar/query/overview_clickhouse.py`.
   - Build Python helpers that take ClickHouse-derived listing-state rows and emit the same overview snapshot shape as `RadarRepository.overview_snapshot(...)`.
   - Reproduce the existing derived fields/labels used by SQLite:
     - `freshness_bucket`
     - `partial_signal` / `thin_signal`
     - `price_band_code` / `price_band_label` / `price_band_sort_order`
     - `state_label` / `state_sort_order`
     - `sold_like`
   - Reuse `evaluate_listing_state(...)` for state classification instead of duplicating the state machine logic.

2. Create `vinted_radar/query/__init__.py`.
   - Add `ClickHouseProductQueryAdapter` that wraps a live `RadarRepository` plus a ClickHouse client/database name.
   - The adapter should expose repository-shaped methods used by the dashboard/scoring path:
     - `overview_snapshot(...)`
     - `explorer_filter_options(...)`
     - `explorer_snapshot(...)`
     - `listing_explorer_page(...)`
     - `listing_state_inputs(...)`
     - `listing_price_context_peer_prices(...)`
     - `listing_history(...)`
     - passthroughs for `runtime_status(...)`, `coverage_summary(...)`, `freshness_summary(...)`, and `db_path`
   - The adapter can derive latest-scan and follow-up-miss metadata from the live SQLite repository because ClickHouse stores listing facts/probes but not the full scan-control tables.

3. Update `vinted_radar/dashboard.py`.
   - Add a small context-managed repository factory for overview / explorer / detail routes only.
   - If `load_platform_config().cutover.enable_polyglot_reads` is false, keep using `RadarRepository` directly.
   - If true, open and use the ClickHouse adapter instead.
   - Leave `/runtime`, `/api/runtime`, and `/health` on the direct repository path.

4. Add `tests/test_clickhouse_queries.py`.
   - Build a fake ClickHouse client keyed off the existing SQL markers in `detail_clickhouse.py`.
   - Seed from the same dashboard fixture data as `tests/test_dashboard.py`.
   - Prove parity for:
     - dashboard payload
     - explorer payload
     - listing detail payload / price context

5. Add `tests/test_clickhouse_parity.py` and `scripts/verify_clickhouse_routes.py`.
   - Parity tests should compare representative SQLite-backed outputs against ClickHouse-adapter outputs.
   - Route proof should exercise dashboard / explorer / detail paths with polyglot reads enabled and report correctness plus basic latency evidence.

6. Re-run verification.
   - At minimum:
     - `python -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q`
     - `python -m pytest tests/test_clickhouse_parity.py -q`

7. Only after all verification passes:
   - replace this recovery summary with a real completion summary
   - call `gsd_complete_task`

## Verification

No implementation verification was run for T04 in this recovery turn because the required ClickHouse adapter, overview helper, and parity tests are still missing.

## Verification Evidence

No final verification command was run in this recovery turn.

## Diagnostics

Current missing pieces are easy to inspect directly:

- missing file: `vinted_radar/query/overview_clickhouse.py`
- missing file: `vinted_radar/query/__init__.py`
- missing file: `tests/test_clickhouse_queries.py`
- missing file: `tests/test_clickhouse_parity.py`
- dashboard still SQLite-only in: `vinted_radar/dashboard.py`
- existing landed ClickHouse helpers:
  - `vinted_radar/query/detail_clickhouse.py`
  - `vinted_radar/query/explorer_clickhouse.py`

## Deviations

This recovery turn wrote the durable task artifact before implementation could continue. No slice-plan invalidation was discovered.

## Known Issues

- T04 is incomplete.
- T03’s missing adapter/dashboard wiring still blocks truthful T04 completion.
- No parity or route-proof verification has been executed yet.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S13/tasks/T04-SUMMARY.md` — added a durable recovery summary with exact observed state and a concrete resume checklist.
