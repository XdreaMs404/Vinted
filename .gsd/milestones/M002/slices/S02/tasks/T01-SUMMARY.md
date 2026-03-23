---
id: T01
parent: S02
milestone: M002
provides:
  - Repository-owned runtime controller snapshot persisted in SQLite and exposed through `runtime_status()` alongside cycle-history compatibility keys
key_files:
  - vinted_radar/repository.py
  - vinted_radar/db.py
  - vinted_radar/db_health.py
  - tests/test_runtime_repository.py
  - tests/test_db_recovery.py
key_decisions:
  - D025: represent current scheduler truth in `runtime_controller_state` while keeping `runtime_cycles` as immutable history
patterns_established:
  - Keep current controller truth in `runtime_controller_state` and read product/runtime surfaces through `runtime_status()` instead of inferring from the latest cycle row
observability_surfaces:
  - `RadarRepository.runtime_controller_state()`
  - `RadarRepository.runtime_status()`
  - `tests/test_runtime_repository.py`
  - `python -m pytest tests/test_runtime_repository.py tests/test_db_recovery.py`
duration: 35m
verification_result: passed
completed_at: 2026-03-23T08:55:00+01:00
blocker_discovered: false
---

# T01: Persist the runtime-controller snapshot and repository contract

**Added a persisted `runtime_controller_state` contract, controller-aware repository methods, and recovery coverage so SQLite can answer what the runtime is doing now.**

## What Happened

I finished the T01 runtime boundary around the new `runtime_controller_state` table that was already started in `vinted_radar/db.py`.

In `vinted_radar/repository.py`, I extended the runtime seam so the repository now owns both:
- immutable per-cycle history in `runtime_cycles`
- current controller truth in `runtime_controller_state`

The repository now:
- keeps the controller snapshot in sync when cycles start, change phase, and finish
- exposes `runtime_controller_state()` for direct inspection
- exposes controller-aware `runtime_status()` with top-level current status/phase/timing fields plus compatibility keys (`latest_cycle`, `recent_cycles`, `latest_failure`, `totals`)
- computes elapsed pause time, next-resume countdown, and heartbeat staleness from a caller-provided `now`
- persists operator requests through pause/resume request helpers
- redacts URL userinfo from persisted runtime config payloads before they can leak into CLI/API/UI surfaces

In `vinted_radar/db_health.py`, I promoted `runtime_controller_state` into the critical-table list.

In `tests/test_runtime_repository.py`, I added regressions that prove:
- cycle methods keep the controller snapshot aligned with the current runtime state
- runtime status exposes paused timing, heartbeat staleness, and recent failure history
- config payloads are sanitized before readback
- pause/resume requests round-trip through the controller contract

In `tests/test_db_recovery.py`, I extended recovery assertions so healthy partial copies preserve `runtime_controller_state` instead of dropping the controller truth.

## Verification

I ran the repository and recovery regressions targeted by the task plan:
- `python -m pytest tests/test_runtime_repository.py tests/test_db_recovery.py`

All tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_runtime_repository.py tests/test_db_recovery.py` | 0 | ✅ pass | 0.25s |

## Diagnostics

For future inspection:
- `RadarRepository.runtime_controller_state()` shows the current controller snapshot directly.
- `RadarRepository.runtime_status(now=...)` is now the authoritative repository payload for controller state + cycle history.
- `tests/test_runtime_repository.py` is the drift alarm for pause/resume timing, heartbeat staleness, request persistence, and config redaction.
- `python -m pytest tests/test_runtime_repository.py tests/test_db_recovery.py` is the quickest contract proof.

## Deviations

None.

## Known Issues

- The controller contract is persisted and queryable, but the continuous loop still sleeps blindly between cycles. T02 still needs to make the runtime service honor the new scheduled/paused contract in real time.
- `/runtime`, richer `/api/runtime`, and overview runtime wording still depend on T03.

## Files Created/Modified

- `vinted_radar/repository.py` — added controller snapshot persistence, controller-aware runtime status fields, pause/resume request helpers, heartbeat timing computation, and config redaction.
- `vinted_radar/db.py` — keeps the new `runtime_controller_state` table in schema/backfill.
- `vinted_radar/db_health.py` — treats `runtime_controller_state` as a critical table.
- `tests/test_runtime_repository.py` — new repository regressions for controller truth, pause/resume requests, timing, and redaction.
- `tests/test_db_recovery.py` — recovery assertions now require `runtime_controller_state` preservation.
- `.gsd/milestones/M002/slices/S02/S02-PLAN.md` — marked T01 complete.
