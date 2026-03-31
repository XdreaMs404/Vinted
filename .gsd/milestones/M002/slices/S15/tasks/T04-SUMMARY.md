---
id: T04
parent: S15
milestone: M002
provides:
  - Partial replay-safe change-fact derivation scaffolding in ClickHouse ingest plus explicit resume notes
key_files:
  - vinted_radar/platform/clickhouse_ingest.py
key_decisions:
  - Derive prior state for change facts from pre-event ClickHouse fact history instead of current latest-serving rows so replay can recreate change rows even when raw fact rows already exist.
patterns_established:
  - Model change facts as deterministic per-source-event rows keyed by listing_id + change_kind rather than query-time diffs.
observability_surfaces:
  - clickhouse ingest checkpoint metadata now carries change_row_count/change_inserted_row_count/change_existing_row_count/change_target_table
duration: partial session
verification_result: failed
completed_at: 2026-03-31T13:05:00+02:00
blocker_discovered: false
---

# T04: Truthful change-fact derivation + replay path

**Started replay-safe ClickHouse change-fact derivation, but stopped before the task reached the verification bar.**

## Slice Plan Excerpt
Source: `.gsd/milestones/M002/slices/S15/S15-PLAN.md`
**Goal:** Close the platform migration with lifecycle discipline, reconciliation/audit surfaces, and AI-ready feature/evidence marts so the new stack stays bounded, trustworthy, and ready for grounded intelligence work without another storage redesign.
**Demo:** After this: After this: TTL, compaction, reconciliation, and AI-ready feature/evidence marts keep the new platform bounded, auditable, and ready for grounded intelligence work.

## What Happened

I partially rewired `vinted_radar/platform/clickhouse_ingest.py` so ingest can derive change facts from ClickHouse history instead of only loading seen/probe fact rows. The new scaffolding builds prior state from pre-event raw fact history, computes current snapshots for listing-seen, probe, and follow-up-miss transitions, and emits deterministic `fact_listing_change_events` rows with checkpoint metadata that reports change-row counts separately from primary fact inserts.

I stopped before completing the full task because the unit hit the hard timeout while verification was still red. The implementation is only partially landed:

- `vinted_radar/platform/clickhouse_ingest.py` now contains the new change-fact derivation path and extra checkpoint metadata.
- I did **not** finish the historical replay-side manifest/chunk metadata work in `vinted_radar/services/full_backfill.py` that is needed to make terminal catalog-scan miss transitions safe for chunked discovery replay batches.
- I did **not** finish updating the affected test expectations/fakes for the new change table behavior.

## Verification

Ran the task-plan command and it still fails:

- `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q`
- Latest result: **2 failed, 8 passed**

Remaining red checks at stop time:

1. `tests/test_clickhouse_ingest.py::test_clickhouse_ingest_only_inserts_missing_rows_on_replay`
   - The assertion still assumes the last ClickHouse insert call is the primary fact-table insert.
   - With change-fact derivation enabled, the final insert call is now the `fact_listing_change_events` insert, so the test expectation needs to distinguish primary-row replay behavior from appended change-row behavior.
2. `tests/test_full_backfill.py::test_full_backfill_pipeline_projects_postgres_writes_manifests_and_ingests_clickhouse`
   - The test still expects only `fact_listing_seen_events` and `fact_listing_probe_events` to be populated.
   - The new ingest path now also writes `fact_listing_change_events`, so the assertion needs to be updated once the replay metadata work is finished and the final behavior is locked.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` | 1 | ❌ fail | 510ms |

## Diagnostics

- Inspect `vinted_radar/platform/clickhouse_ingest.py` around `_ingest_record`, `_derive_listing_seen_change_rows`, `_derive_probe_change_rows`, and `_is_terminal_catalog_batch`.
- Re-run `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` first; it should still reproduce the two failures listed above.
- The ingest checkpoint metadata now includes `change_row_count`, `change_inserted_row_count`, `change_existing_row_count`, and `change_target_table` for the latest processed outbox event.

## Deviations

Stopped at the hard timeout before the task reached the required verification bar. Only the ingest-side wiring was partially implemented; the replay-side chunk/terminal metadata work in `vinted_radar/services/full_backfill.py` and the matching test updates were not completed.

## Known Issues

- The task is **not complete**.
- `vinted_radar/services/full_backfill.py` still needs the planner-intended replay metadata work so chunked discovery replay batches can truthfully decide when a catalog scan is terminal before emitting follow-up miss transitions.
- The task-plan verification command is still failing with the two tests listed above.

## Resume Notes

Next worker should continue from this exact point:

1. Finish `vinted_radar/services/full_backfill.py` discovery-batch metadata so chunked replay batches carry enough page/chunk completion information for `_is_terminal_catalog_batch()` to be truthful.
2. Update `tests/test_clickhouse_ingest.py` replay assertions to account for separate primary-row and change-row inserts.
3. Update `tests/test_full_backfill.py` to expect `fact_listing_change_events` once the replay behavior is finalized.
4. Re-run `python3 -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q` and only mark T04 complete if it passes.

## Files Created/Modified

- `vinted_radar/platform/clickhouse_ingest.py` — partial change-fact derivation scaffolding, replay-safe prior-state lookup helpers, and richer checkpoint metadata.
