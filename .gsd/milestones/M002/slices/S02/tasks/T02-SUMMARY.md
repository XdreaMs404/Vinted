---
id: T02
parent: S02
milestone: M002
provides:
  - Cooperative continuous-runtime scheduling with persisted `scheduled` / `paused` / `running` controller truth and CLI pause/resume controls on the same SQLite contract
key_files:
  - vinted_radar/services/runtime.py
  - vinted_radar/cli.py
  - tests/test_runtime_service.py
  - tests/test_runtime_cli.py
key_decisions:
  - D025: current controller truth lives in `runtime_controller_state`, not in the last cycle row
patterns_established:
  - Continuous mode must heartbeat through the DB while waiting so pause/resume can be observed before the full interval elapses
observability_surfaces:
  - `python -m vinted_radar.cli runtime-status --format json`
  - `python -m vinted_radar.cli runtime-pause`
  - `python -m vinted_radar.cli runtime-resume`
  - `tests/test_runtime_service.py`
  - `tests/test_runtime_cli.py`
duration: 40m
verification_result: passed
completed_at: 2026-03-23T09:10:00+01:00
blocker_discovered: false
---

# T02: Make continuous runtime and CLI controls honor the persisted controller truth

**Replaced the blind interval sleep with a cooperative controller-backed loop and added pause/resume/status CLI controls on top of the same DB contract.**

## What Happened

I reworked `vinted_radar/services/runtime.py` so continuous mode no longer sleeps out the whole interval without looking at SQLite.

The runtime service now:
- keeps a controller heartbeat alive while it is waiting between cycles
- persists `scheduled` windows explicitly instead of leaving the last cycle row to imply what should happen next
- preserves `paused` state in the controller snapshot and keeps its heartbeat fresh while paused
- detects pause requests between cycles immediately and pause requests made during a running cycle as soon as that cycle finishes
- lets resume move the controller back into a scheduled window with a real `next_resume_at`
- returns to `idle` on graceful loop shutdown instead of leaving scheduled state behind after a bounded smoke run

To make this testable, I added an injectable `now_fn` and used fake-clock tests so the scheduler contract is verified deterministically instead of depending on wall-clock sleeps.

In `vinted_radar/cli.py`, I added:
- `runtime-pause`
- `runtime-resume`
- richer `runtime-status` output with current controller status/phase, heartbeat age, paused duration, next resume timing, pending operator action, and controller error context
- `--now` on `runtime-status` so timing output can be verified deterministically in tests and inspected reproducibly later

In `tests/test_runtime_service.py`, I expanded coverage so the service now proves:
- batch completion leaves an `idle` controller with the latest cycle attached
- a failed continuous cycle remains visible in history while the loop still continues
- a pause requested after cycle completion really pushes the loop into paused state and a resume request lets the next cycle proceed

In `tests/test_runtime_cli.py`, I added coverage for:
- controller-backed JSON status
- `runtime-pause` / `runtime-resume` mutating persisted controller truth
- human-readable controller timing output in table mode

## Verification

I ran the targeted service and CLI regressions from the task plan:
- `python -m pytest tests/test_runtime_service.py tests/test_runtime_cli.py`

All tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_runtime_service.py tests/test_runtime_cli.py` | 0 | ✅ pass | 0.87s |

## Diagnostics

The fastest ways to inspect what T02 shipped are now:
- `python -m vinted_radar.cli runtime-status --db ... --format json`
- `python -m vinted_radar.cli runtime-status --db ... --now <iso>` for deterministic timing readback
- `python -m vinted_radar.cli runtime-pause --db ...`
- `python -m vinted_radar.cli runtime-resume --db ...`
- `tests/test_runtime_service.py` for the cooperative scheduler contract
- `tests/test_runtime_cli.py` for operator-surface behavior

## Deviations

None.

## Known Issues

- The controller truth now exists and is used by the scheduler and CLI, but the dashboard still exposes only `/api/runtime` plus overview wording that reads too close to the last cycle row. T03 still needs the dedicated `/runtime` page and home-surface runtime copy changes.
- Graceful stop is explicit only when the loop exits through normal bounded completion or `KeyboardInterrupt`. A hard process death still relies on heartbeat staleness for honesty, which is expected for this slice.

## Files Created/Modified

- `vinted_radar/services/runtime.py` — added cooperative scheduling, DB-backed waiting heartbeats, pause/resume handling, and deterministic time injection for tests.
- `vinted_radar/cli.py` — added `runtime-pause`, `runtime-resume`, richer `runtime-status`, and `--now` support.
- `tests/test_runtime_service.py` — added deterministic scheduler coverage for idle/scheduled/paused/resumed behavior and continued retry after failure.
- `tests/test_runtime_cli.py` — added CLI coverage for pause/resume and controller timing output.
- `.gsd/milestones/M002/slices/S02/S02-PLAN.md` — marked T02 complete.
