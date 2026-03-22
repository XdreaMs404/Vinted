---
estimated_steps: 4
estimated_files: 6
skills_used:
  - debug-like-expert
  - best-practices
  - test
  - review
---

# T01: Persist the runtime-controller snapshot and repository contract

**Slice:** S02 — Runtime Truth + Pause/Resume Surface
**Milestone:** M002

## Description

Load `debug-like-expert`, `test`, and `review` before coding. This task creates the durable runtime boundary for the whole slice. S02 must stop treating `runtime_cycles` as both history and current truth: keep cycle rows immutable, add a dedicated `runtime_controller_state` snapshot for what the loop is doing now, and bring DB health/recovery along so copied databases keep the new runtime truth.

## Steps

1. Extend `vinted_radar/db.py` with a dedicated `runtime_controller_state` table and any brownfield-safe migration/backfill needed so existing databases gain the new runtime boundary without rewriting `runtime_cycles` history.
2. Add repository methods in `vinted_radar/repository.py` to read/write the controller snapshot, record pause/resume intent, compute elapsed pause and next-resume values from `now`, and extend `runtime_status()` with controller truth while preserving existing cycle-history keys.
3. Update `vinted_radar/db_health.py` and `vinted_radar/db_recovery.py` so the new runtime table is treated as critical and survives health probes plus partial recovery.
4. Add repository and recovery regressions in `tests/test_runtime_repository.py` and `tests/test_db_recovery.py` that prove SQLite alone can answer current runtime truth and that recovered databases keep the controller snapshot.

## Must-Haves

- [ ] `runtime_cycles` remains immutable per-cycle history while `runtime_controller_state` becomes the source of truth for current scheduled/paused/running/failed state.
- [ ] `runtime_status()` returns controller-backed fields for status, phase, `updated_at`, `paused_at`, `next_resume_at`, elapsed pause, last error, and recent failures without breaking the existing compatibility keys.
- [ ] DB health and recovery tooling treat `runtime_controller_state` as a critical table and prove it survives recovery.

## Verification

- `python -m pytest tests/test_runtime_repository.py tests/test_db_recovery.py`
- `python -m pytest tests/test_runtime_repository.py -k runtime_status`

## Observability Impact

- Signals added/changed: persisted controller status/phase, heartbeat/update timestamp, pause/resume timing fields, and controller last-error state.
- How a future agent inspects this: run `python -m pytest tests/test_runtime_repository.py`, inspect `python -m vinted_radar.cli runtime-status --db ... --format json`, or query the SQLite `runtime_controller_state` and `runtime_cycles` tables.
- Failure state exposed: stale controller heartbeat, lost pause metadata, or dropped recovery data fail as explicit contract assertions instead of surfacing later as vague UI wording bugs.

## Inputs

- `.gsd/milestones/M002/slices/S02/S02-RESEARCH.md` — verified runtime-gap findings and the recommended separate-controller posture.
- `vinted_radar/db.py` — current schema and migration seam where the new runtime table must be introduced safely.
- `vinted_radar/repository.py` — existing `runtime_cycles` persistence and `runtime_status()` contract that S02 must extend.
- `vinted_radar/db_health.py` — current critical-table list and health probes that must start tracking the new runtime truth.
- `vinted_radar/db_recovery.py` — partial-recovery flow that must preserve the new table.
- `tests/test_db_recovery.py` — existing recovery assertions that need to expand to the new runtime table.

## Expected Output

- `vinted_radar/db.py` — `runtime_controller_state` schema and any needed brownfield-safe migration/backfill logic.
- `vinted_radar/repository.py` — controller snapshot persistence helpers and the extended repository-owned runtime contract.
- `vinted_radar/db_health.py` — critical-table probing that includes `runtime_controller_state`.
- `vinted_radar/db_recovery.py` — recovery ordering and copy logic that preserve the controller snapshot.
- `tests/test_runtime_repository.py` — new repository contract tests for scheduled/paused/next-resume/elapsed-pause runtime truth.
- `tests/test_db_recovery.py` — updated recovery regression proving the controller table survives copy/recovery.
