---
estimated_steps: 7
estimated_files: 4
---

# T01: Extend persistence for observation history and migrations

**Slice:** S02 — Intelligent Revisits + Observation History
**Milestone:** M001

## Description

Add a durable normalized observation layer on top of S01 so repeated runs preserve listing evolution over time, while existing SQLite databases continue to open and upgrade cleanly.

## Steps

1. Add the schema changes needed for normalized per-observation persistence without removing the S01 diagnostics.
2. Implement forward-only migrations so old S01 databases gain the new tables/columns safely.
3. Record enough normalized fields per observation to reconstruct timeline rows even when later listing rows change.
4. Expose repository queries for listing history summaries, freshness buckets, and revisit candidates.
5. Keep first/last seen behavior truthful for both new and existing listings.
6. Add repository tests that cover repeated observations and migration safety.
7. Run the targeted repository tests before touching the CLI surface.

## Must-Haves

- [x] Existing S01 databases upgrade without manual intervention.
- [x] Repeated observations can be queried as a timeline with cadence metadata.
- [x] Freshness and revisit candidate summaries are derivable from persisted state.

## Verification

- `python -m pytest tests/test_history_repository.py`
- `python -m vinted_radar.cli coverage --db data/vinted-radar.db`

## Observability Impact

- Signals added/changed: `listing_observations`, per-listing history summary queries, freshness buckets, revisit candidate scoring.
- How a future agent inspects this: `freshness`, `revisit-plan`, and `history` CLI commands or direct SQLite queries.
- Failure state exposed: migration/schema mismatches fail immediately at DB open rather than surfacing later as silent missing history.

## Inputs

- `vinted_radar/repository.py` — S01 persistence and coverage query surface.
- `vinted_radar/services/discovery.py` — current run loop that already emits observation timestamps.

## Expected Output

- `vinted_radar/db.py` — upgraded schema + migrations.
- `vinted_radar/repository.py` — history/freshness/revisit queries.
- `tests/test_history_repository.py` — repository-level proof of repeated observation behavior.
