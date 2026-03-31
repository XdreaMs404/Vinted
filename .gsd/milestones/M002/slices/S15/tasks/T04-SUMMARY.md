---
id: T04
parent: S15
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/platform/clickhouse_ingest.py", "vinted_radar/services/full_backfill.py", "tests/test_clickhouse_ingest.py", "tests/test_full_backfill.py", ".gsd/milestones/M002/slices/S15/tasks/T04-SUMMARY.md"]
key_decisions: ["Carry pagination and chunk metadata in replayed discovery manifests so follow-up miss transitions only emit on the final replay chunk of a terminal catalog page.", "Verify replay-state reconstruction with ClickHouse test doubles that answer historical seen/probe/change queries instead of source-event-only fakes."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` because this workstation exposes `python3` instead of a `python` symlink. The suite passed with 10 tests green, covering replay-safe primary fact dedupe, derived change-fact inserts, terminal-chunk-aware backfill manifests, and replay history lookups used by change derivation."
completed_at: 2026-03-31T15:40:41.805Z
blocker_discovered: false
---

# T04: Made ClickHouse replay derive truthful change facts with terminal-chunk-aware backfill manifests.

> Made ClickHouse replay derive truthful change facts with terminal-chunk-aware backfill manifests.

## What Happened
---
id: T04
parent: S15
milestone: M002
key_files:
  - vinted_radar/platform/clickhouse_ingest.py
  - vinted_radar/services/full_backfill.py
  - tests/test_clickhouse_ingest.py
  - tests/test_full_backfill.py
  - .gsd/milestones/M002/slices/S15/tasks/T04-SUMMARY.md
key_decisions:
  - Carry pagination and chunk metadata in replayed discovery manifests so follow-up miss transitions only emit on the final replay chunk of a terminal catalog page.
  - Verify replay-state reconstruction with ClickHouse test doubles that answer historical seen/probe/change queries instead of source-event-only fakes.
duration: ""
verification_result: passed
completed_at: 2026-03-31T15:40:41.805Z
blocker_discovered: false
---

# T04: Made ClickHouse replay derive truthful change facts with terminal-chunk-aware backfill manifests.

**Made ClickHouse replay derive truthful change facts with terminal-chunk-aware backfill manifests.**

## What Happened

Completed the missing change-fact replay path by wiring truthful discovery replay metadata through full backfill and tightening previous-snapshot reconstruction in ClickHouse ingest. `vinted_radar/services/full_backfill.py` now groups discovery replay rows by run/catalog/page before chunk emission so manifests carry `page_chunk_index`, `page_chunk_count`, `pagination_current_page`, `pagination_total_pages`, and `next_page_url`, which makes terminal-page follow-up miss derivation truthful during replay. `vinted_radar/platform/clickhouse_ingest.py` was also fixed to coalesce string dimensions correctly from prior change rows/seen rows during replay-state reconstruction. The tests were updated to use stateful ClickHouse fakes, distinguish primary fact inserts from derived change inserts, and assert replayed probe batches derive the expected state-transition and engagement-shift facts from prior ClickHouse history.

## Verification

Ran `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` because this workstation exposes `python3` instead of a `python` symlink. The suite passed with 10 tests green, covering replay-safe primary fact dedupe, derived change-fact inserts, terminal-chunk-aware backfill manifests, and replay history lookups used by change derivation.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` | 0 | ✅ pass | 470ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/services/full_backfill.py`
- `tests/test_clickhouse_ingest.py`
- `tests/test_full_backfill.py`
- `.gsd/milestones/M002/slices/S15/tasks/T04-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
