---
id: T02
parent: S13
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/platform/clickhouse_ingest.py", "vinted_radar/cli.py", "vinted_radar/platform/__init__.py", "tests/test_clickhouse_ingest.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S13/tasks/T02-SUMMARY.md"]
key_decisions: ["D048: use deterministic row-level fact ids plus source-event lookups so ClickHouse ingest inserts only missing rows on retries and partial replays."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the touched modules compile with `python3 -m py_compile`, and verified the required task suite passes with `python3 -m pytest tests/test_clickhouse_ingest.py -q` (6 tests passed)."
completed_at: 2026-03-31T07:04:16.603Z
blocker_discovered: false
---

# T02: Added replay-safe ClickHouse batch ingestion with checkpoint status and operator CLI commands.

> Added replay-safe ClickHouse batch ingestion with checkpoint status and operator CLI commands.

## What Happened
---
id: T02
parent: S13
milestone: M002
key_files:
  - vinted_radar/platform/clickhouse_ingest.py
  - vinted_radar/cli.py
  - vinted_radar/platform/__init__.py
  - tests/test_clickhouse_ingest.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S13/tasks/T02-SUMMARY.md
key_decisions:
  - D048: use deterministic row-level fact ids plus source-event lookups so ClickHouse ingest inserts only missing rows on retries and partial replays.
duration: ""
verification_result: passed
completed_at: 2026-03-31T07:04:16.603Z
blocker_discovered: false
---

# T02: Added replay-safe ClickHouse batch ingestion with checkpoint status and operator CLI commands.

**Added replay-safe ClickHouse batch ingestion with checkpoint status and operator CLI commands.**

## What Happened

Implemented `vinted_radar.platform.clickhouse_ingest.ClickHouseIngestService` to claim ClickHouse outbox rows, load parquet-batch manifests from the lake, map discovery listing-seen batches into `fact_listing_seen_events`, map state-refresh probe batches into `fact_listing_probe_events`, and persist sink lag/error state in PostgreSQL outbox checkpoints. The worker generates deterministic row-level fact ids from source batch identity plus row identity, queries ClickHouse for existing row ids by `source_event_id`, and inserts only missing rows so retries recover partial replays without duplicating facts. I also added `clickhouse-ingest` and `clickhouse-ingest-status` CLI commands plus focused tests for happy path, replay safety, failure-state persistence, and CLI output.

## Verification

Verified the touched modules compile with `python3 -m py_compile`, and verified the required task suite passes with `python3 -m pytest tests/test_clickhouse_ingest.py -q` (6 tests passed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/platform/clickhouse_ingest.py vinted_radar/platform/__init__.py vinted_radar/cli.py tests/test_clickhouse_ingest.py` | 0 | ✅ pass | 58ms |
| 2 | `python3 -m pytest tests/test_clickhouse_ingest.py -q` | 0 | ✅ pass | 540ms |


## Deviations

Used `python3` instead of `python` because this shell does not expose a `python` alias. No slice-plan invalidation.

## Known Issues

Current probe batches do not yet emit denormalized category/brand/price context, and current listing-seen batches still omit some nullable listing-card fields, so the new ClickHouse fact ingester leaves those schema columns null until upstream emitters enrich the batch rows.

## Files Created/Modified

- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/cli.py`
- `vinted_radar/platform/__init__.py`
- `tests/test_clickhouse_ingest.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S13/tasks/T02-SUMMARY.md`


## Deviations
Used `python3` instead of `python` because this shell does not expose a `python` alias. No slice-plan invalidation.

## Known Issues
Current probe batches do not yet emit denormalized category/brand/price context, and current listing-seen batches still omit some nullable listing-card fields, so the new ClickHouse fact ingester leaves those schema columns null until upstream emitters enrich the batch rows.
