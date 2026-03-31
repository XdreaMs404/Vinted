---
id: T01
parent: S14
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/services/full_backfill.py", "vinted_radar/cli.py", "tests/test_full_backfill.py", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Backfill PostgreSQL mutable truth directly from SQLite state/history instead of replaying every legacy dataset through serving-fact schemas.", "Replay only live-compatible historical discovery/probe batches through the existing ClickHouse outbox worker and keep observation/runtime history as Parquet audit evidence.", "Persist full-backfill progress in a local JSON checkpoint so interrupted migrations can resume idempotently without duplicating lake objects or ClickHouse facts."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified with `python3 -m pytest tests/test_full_backfill.py -q`, which passed all four focused tests. The suite proved PostgreSQL mutable-truth backfill, ClickHouse replay for discovery/probe history, Parquet manifest emission, dry-run no-write behavior, resume checkpoint skipping, and CLI option forwarding."
completed_at: 2026-03-31T12:09:21.650Z
blocker_discovered: false
---

# T01: Added a resumable full backfill command that migrates SQLite history into PostgreSQL mutable truth, ClickHouse facts, and Parquet audit manifests.

> Added a resumable full backfill command that migrates SQLite history into PostgreSQL mutable truth, ClickHouse facts, and Parquet audit manifests.

## What Happened
---
id: T01
parent: S14
milestone: M002
key_files:
  - vinted_radar/services/full_backfill.py
  - vinted_radar/cli.py
  - tests/test_full_backfill.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Backfill PostgreSQL mutable truth directly from SQLite state/history instead of replaying every legacy dataset through serving-fact schemas.
  - Replay only live-compatible historical discovery/probe batches through the existing ClickHouse outbox worker and keep observation/runtime history as Parquet audit evidence.
  - Persist full-backfill progress in a local JSON checkpoint so interrupted migrations can resume idempotently without duplicating lake objects or ClickHouse facts.
duration: ""
verification_result: passed
completed_at: 2026-03-31T12:09:21.650Z
blocker_discovered: false
---

# T01: Added a resumable full backfill command that migrates SQLite history into PostgreSQL mutable truth, ClickHouse facts, and Parquet audit manifests.

**Added a resumable full backfill command that migrates SQLite history into PostgreSQL mutable truth, ClickHouse facts, and Parquet audit manifests.**

## What Happened

Implemented a new `vinted_radar.services.full_backfill` orchestration layer for the historical cutover. The service reuses the existing SQLite-to-PostgreSQL mutable-truth projector for catalog-complete listing/runtime state, emits deterministic historical Parquet batches with a persisted JSON resume checkpoint, publishes live-compatible discovery/probe batches into the existing ClickHouse outbox worker, and exports legacy observation/runtime history as lake audit manifests. Wired the new flow into `vinted_radar.cli` as the `full-backfill` command with dry-run, checkpoint, reset, runtime-control, and batch-size options, then added focused tests covering the executed pipeline, dry-run safety, resume semantics, and CLI forwarding. Recorded the target split in `.gsd/KNOWLEDGE.md` so downstream cutover tasks know which historical datasets map to PostgreSQL, ClickHouse, and the lake.

## Verification

Verified with `python3 -m pytest tests/test_full_backfill.py -q`, which passed all four focused tests. The suite proved PostgreSQL mutable-truth backfill, ClickHouse replay for discovery/probe history, Parquet manifest emission, dry-run no-write behavior, resume checkpoint skipping, and CLI option forwarding.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_full_backfill.py -q` | 0 | ✅ pass | 786ms |


## Deviations

Used `python3` instead of `python` for verification because the local shell does not expose a `python` executable. Also added a `.gsd/KNOWLEDGE.md` entry to preserve the discovered target split for downstream work.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/services/full_backfill.py`
- `vinted_radar/cli.py`
- `tests/test_full_backfill.py`
- `.gsd/KNOWLEDGE.md`


## Deviations
Used `python3` instead of `python` for verification because the local shell does not expose a `python` executable. Also added a `.gsd/KNOWLEDGE.md` entry to preserve the discovered target split for downstream work.

## Known Issues
None.
