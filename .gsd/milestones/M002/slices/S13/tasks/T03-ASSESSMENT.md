---
id: T03
parent: S13
milestone: M002
provides:
  - Partial ClickHouse query-layer groundwork plus precise resume notes for finishing the dashboard cutover.
key_files:
  - vinted_radar/query/detail_clickhouse.py
  - vinted_radar/query/explorer_clickhouse.py
key_decisions:
  - Keep the existing dashboard payload builders/state-machine path and insert a ClickHouse-backed adapter underneath them instead of rewriting the product payload contracts.
patterns_established:
  - Derive listing-state inputs from ClickHouse latest/fact tables, then reuse the existing Python state and scoring layers for contract parity.
observability_surfaces:
  - none
duration: partial
verification_result: not-run
completed_at: 2026-03-31T08:23:20+02:00
blocker_discovered: false
---

# T03: Product query adapters on ClickHouse

**Timed out mid-implementation after landing the first ClickHouse query helpers; task is not complete and must resume from this summary.**

## Slice Plan Excerpt
Source: `.gsd/milestones/M002/slices/S13/S13-PLAN.md`
**Goal:** Introduce the long-term serving warehouse in ClickHouse so overview, explorer, detail, and future AI-facing analytics read from raw facts and materialized rollups instead of SQLite full-history scans.
**Demo:** After this: After this: overview, explorer, and listing-detail analytics read from ClickHouse raw facts and materialized rollups rather than SQLite full-history scans.

## What Happened

I confirmed the current contracts in `vinted_radar/dashboard.py`, `vinted_radar/repository.py`, and `tests/test_dashboard.py`, then started the planned adapter seam instead of rewriting the payload builders. The intent is to keep `build_dashboard_payload(...)`, `build_explorer_payload(...)`, `build_listing_detail_payload(...)`, `state_machine.py`, and `scoring.py` intact while swapping in a ClickHouse-backed object with repository-shaped methods.

I completed two new query helper modules:

- `vinted_radar/query/detail_clickhouse.py`
  - Adds real ClickHouse SQL helpers for:
    - aggregated listing-state inputs from `fact_listing_seen_events` + `serving_listing_latest_seen` + `serving_listing_latest_probe`
    - per-listing history timeline rows from `fact_listing_seen_events`
    - price-context peer prices from `serving_listing_latest_seen`
  - The SQL includes explicit `/* clickhouse-query: ... */` markers so the planned fake ClickHouse client in tests can route responses without brittle SQL parsing.
- `vinted_radar/query/explorer_clickhouse.py`
  - Adds pure-Python helpers for:
    - explorer filter-option counts
    - explorer filtering / search matching
    - summary blocks
    - comparison modules
    - paginated sorted explorer pages
  - These helpers are designed to operate on ClickHouse-derived listing-state rows while preserving the existing payload shapes.

I also drafted, but did **not** successfully persist due timeout interruption, an `overview_clickhouse.py` helper file and the remaining adapter/dashboard wiring plan. No runtime routes or dashboard routes have been switched yet.

## Exact Resume Plan

Resume in this order only:

1. **Finish the overview helper file**
   - Recreate `vinted_radar/query/overview_clickhouse.py`.
   - It should build the repository-shaped overview snapshot from evaluated ClickHouse state rows plus SQLite `coverage_summary()` / `runtime_status()` passthrough data.

2. **Create the actual adapter module**
   - Add `vinted_radar/query/__init__.py` with a `ClickHouseProductQueryAdapter` (or equivalently named class).
   - The adapter should:
     - accept a live `RadarRepository` for runtime/coverage/control-plane reads
     - accept a ClickHouse client + database name
     - expose repository-like methods used by the dashboard/scoring path:
       - `overview_snapshot(...)`
       - `explorer_filter_options(...)`
       - `explorer_snapshot(...)`
       - `listing_explorer_page(...)`
       - `listing_state_inputs(...)`
       - `listing_price_context_peer_prices(...)`
       - `listing_history(...)`
       - passthroughs for `runtime_status(...)`, `coverage_summary(...)`, `freshness_summary(...)`, `db_path`
     - enrich ClickHouse rows with the same derived fields the SQLite repository currently adds:
       - `last_seen_age_hours`
       - `freshness_bucket`
       - `signal_completeness`
       - `partial_signal`
       - `thin_signal`
       - `price_band_code` / `price_band_label` / `price_band_sort_order`
       - `latest_primary_scan_run_id` / `latest_primary_scan_at`
       - `follow_up_miss_count`
       - `seen_in_latest_primary_scan`
       - `state_label` / `state_sort_order`
       - `sold_like`
     - reuse `evaluate_listing_state(...)` rather than re-implementing state logic.

3. **Wire dashboard route selection**
   - Edit `vinted_radar/dashboard.py` only enough to add a small context-managed factory that:
     - opens `RadarRepository(self.db_path)`
     - loads platform config
     - if `config.cutover.enable_polyglot_reads` is false, yields the plain repository
     - if true, yields the ClickHouse adapter created from that repository
   - Use that helper only for the overview / explorer / detail routes and JSON APIs.
   - Leave `/runtime`, `/api/runtime`, and `/health` on the current repository path unless needed for compatibility.

4. **Add tests before verification**
   - Create `tests/test_clickhouse_queries.py` with a fake ClickHouse client keyed off the `/* clickhouse-query: ... */` markers.
   - Seed it with rows equivalent to `_seed_dashboard_db(...)` from `tests/test_dashboard.py`.
   - Verify ClickHouse-backed payloads preserve the current contract for:
     - dashboard payload
     - explorer payload
     - detail payload / price context
   - Add one route-selection test to `tests/test_dashboard.py` proving `DashboardApplication` switches to the adapter when `enable_polyglot_reads=True`.

5. **Run the required verification command**
   - `python3 -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q`

6. **Only after verification passes**
   - replace this partial summary with a real completion summary
   - call `gsd_complete_task`

## Verification

Not run for the task as a whole. The unit timed out before the adapter, dashboard wiring, and tests were complete.

## Verification Evidence

No final verification command was run before timeout.

## Diagnostics

Recovery should start from the two landed helper modules:

- `vinted_radar/query/detail_clickhouse.py`
- `vinted_radar/query/explorer_clickhouse.py`

These are intentionally self-contained and not yet imported anywhere, so the repo should still behave exactly as before until the adapter/dashboard wiring is finished.

## Deviations

Stopped for timeout recovery before the adapter, dashboard wiring, and tests were finished. No slice-plan invalidation was discovered.

## Known Issues

- Task is incomplete.
- `vinted_radar/query/overview_clickhouse.py` still needs to be written.
- `vinted_radar/query/__init__.py` / adapter class still needs to be written.
- `vinted_radar/dashboard.py` is not yet wired to ClickHouse reads.
- `tests/test_clickhouse_queries.py` does not exist yet.
- No verification has been run.

## Files Created/Modified

- `vinted_radar/query/detail_clickhouse.py` — added ClickHouse SQL helpers for state-input rows, per-listing history timeline rows, and price-context peer-price reads.
- `vinted_radar/query/explorer_clickhouse.py` — added pure-Python explorer filtering, summaries, comparison modules, and paging helpers for ClickHouse-derived listing rows.
