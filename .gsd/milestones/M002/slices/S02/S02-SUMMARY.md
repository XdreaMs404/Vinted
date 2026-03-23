---
id: S02
parent: M002
milestone: M002
provides:
  - A persisted `runtime_controller_state` contract for current scheduler truth, separate from immutable `runtime_cycles`
  - Cooperative pause/resume/scheduled runtime behavior exposed through CLI, `/runtime`, `/api/runtime`, `/health`, and the overview home
  - A French-first runtime page and controller-aware operator documentation grounded in the same SQLite payload
requires:
  - slice: S01
    provides: SQL-backed overview/freshness vocabulary and the brownfield `/`, `/explorer`, `/api/...` route split that S02 extends
affects:
  - S03
  - S06
  - S07
key_files:
  - vinted_radar/repository.py
  - vinted_radar/services/runtime.py
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - vinted_radar/db_health.py
  - vinted_radar/db_recovery.py
  - tests/test_runtime_repository.py
  - tests/test_runtime_service.py
  - tests/test_runtime_cli.py
  - tests/test_dashboard.py
  - tests/test_db_recovery.py
  - README.md
key_decisions:
  - D025
patterns_established:
  - Keep current scheduler truth in `runtime_controller_state` and keep `runtime_cycles` as immutable history.
  - Persist post-cycle `scheduled` / `paused` transitions before observer-facing callbacks so `/runtime`, `/api/runtime`, `/health`, and `/` do not drift through a fake idle window.
observability_surfaces:
  - `/runtime`
  - `/api/runtime`
  - `/health`
  - `python -m vinted_radar.cli runtime-status --format json`
  - `python -m vinted_radar.cli runtime-pause`
  - `python -m vinted_radar.cli runtime-resume`
  - `tests/test_runtime_repository.py`
  - `tests/test_runtime_service.py`
  - `tests/test_dashboard.py`
drill_down_paths:
  - `.gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S02/S02-UAT.md`
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
---

# S02: Runtime Truth + Pause/Resume Surface

**S02 replaced cycle-only runtime inference with a controller-backed runtime contract: the radar can now truthfully show running, scheduled, paused, failed, elapsed pause time, next resume timing, and recent errors through the CLI, `/runtime`, `/api/runtime`, `/health`, and the overview home on the same SQLite DB.**

## What Happened

S02 started by making current runtime truth representable.

`vinted_radar/db.py` already had the new `runtime_controller_state` table stubbed in, but the product still behaved as if the latest cycle row were the current runtime. I finished that split in `vinted_radar/repository.py` by turning `runtime_controller_state` into the source of truth for current scheduler state while leaving `runtime_cycles` as immutable history.

The repository now owns:
- current controller status / phase / heartbeat / pause / next-resume / last-error truth
- pause/resume request persistence
- heartbeat staleness calculation
- recent failure history alongside the existing compatibility keys
- config redaction so proxy-like credentials cannot leak into runtime surfaces

On top of that contract, `vinted_radar/services/runtime.py` no longer uses a blind full-interval sleep in continuous mode. The loop now:
- persists scheduled windows between cycles
- heartbeats through SQLite while waiting
- observes pause/resume requests cooperatively
- supports “pause after the current cycle finishes” when the operator requests pause mid-cycle
- returns to `scheduled` or `paused` truth explicitly instead of leaving a completed cycle row to imply current state

`vinted_radar/cli.py` then became the real operator surface for that controller contract:
- `runtime-status` now shows controller status/phase, heartbeat age, pause duration, next resume timing, and pending operator action
- `runtime-pause` and `runtime-resume` mutate the same persisted truth the runtime loop reads
- the dashboard/local-server output now advertises the dedicated `/runtime` page

Finally, `vinted_radar/dashboard.py` exposed the same truth through the product surface:
- dedicated French-first `/runtime`
- richer `/api/runtime`
- `/health` now includes current runtime status and controller data
- the overview home now says `Runtime actuel` from controller truth instead of implying that a healthy waiting loop is just “completed” because the last cycle row ended cleanly

The most important late finding came from live smoke: `/api/runtime` and `/health` could drift through a tiny fake-idle window because the continuous loop originally called the observer callback before persisting the next `scheduled` / `paused` transition. S02 fixes that ordering and treats it as part of the runtime contract, not as a UI bug.

## Verification

S02 verification passed at three levels:

1. **Contract / regression tests**
   - `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_db_recovery.py`
2. **Local operator smoke with the actual continuous CLI**
   - `python -m vinted_radar.cli continuous --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8781`
   - `python -m vinted_radar.cli runtime-pause --db data/vinted-radar-s02.db`
   - `python -m vinted_radar.cli runtime-resume --db data/vinted-radar-s02.db`
3. **Browser / HTTP verification**
   - browser verification passed on `http://127.0.0.1:8781/runtime` and `http://127.0.0.1:8781/`
   - real HTTP probes confirmed `/api/runtime` and `/health` agree on `running`, then `paused`, then `scheduled` when driven through the live controller

## Requirements Advanced

- R010 — S02 makes current runtime truth first-class product data instead of leaving the app to infer operator state from the last cycle row.
- R004 — the overview and dedicated runtime page now expose runtime freshness, heartbeat, pause timing, and next-resume truth explicitly.
- R011 — scheduled, paused, failed, stale-heartbeat, and recent-error states remain visible instead of being smoothed away by optimistic UI wording.

## Requirements Validated

- none — R010 was already validated at the broader M001 operability level; S02 deepens and hardens that runtime truth rather than changing the requirement’s status.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- One unplanned but necessary fix landed during live smoke: post-cycle controller transitions are now persisted before observer-facing callbacks so `/runtime`, `/api/runtime`, `/health`, and `/` do not drift through a fake idle window.

## Known Limitations

- This slice is locally and browser verified, but it does not prove the responsive VPS shell or remote phone/desktop consultation path; S03 and S07 still own that.
- Hard process death still relies on heartbeat staleness for honesty; S02 does not pretend a crash can be made graceful after the fact.
- Explorer copy/layout remains brownfield-English; S02 only updates the runtime and overview runtime wording.

## Follow-ups

- S03 should treat `/runtime` as a first-class shell destination and make the overview/runtime/explorer navigation coherent and responsive for real remote use.
- S06 should layer degraded acquisition telemetry and warning language on top of the new controller surfaces rather than inventing a separate runtime honesty seam.
- S07 should reuse the live pause/resume smoke flow from `S02-UAT.md` when proving the integrated VPS product.

## Files Created/Modified

- `vinted_radar/repository.py` — controller snapshot persistence, controller-aware runtime payloads, request helpers, timing/staleness fields, and config redaction.
- `vinted_radar/services/runtime.py` — cooperative scheduling, heartbeat waiting loop, pause/resume orchestration, and callback-order fix.
- `vinted_radar/dashboard.py` — `/runtime`, controller-backed home/runtime wording, richer `/health`, runtime payload builder, translated runtime labels, and runtime favicon.
- `vinted_radar/cli.py` — `runtime-pause`, `runtime-resume`, richer `runtime-status`, `--now`, and `/runtime` route output.
- `vinted_radar/db_health.py` — `runtime_controller_state` is now a critical table.
- `tests/test_runtime_repository.py` — repository contract coverage for controller truth.
- `tests/test_runtime_service.py` — cooperative scheduler and pause/resume tests.
- `tests/test_runtime_cli.py` — operator CLI coverage for controller-backed status and pause/resume.
- `tests/test_dashboard.py` — runtime route/payload/home wording coverage.
- `tests/test_dashboard_cli.py` — CLI output coverage for `/runtime`.
- `tests/test_db_recovery.py` — recovery coverage for `runtime_controller_state`.
- `README.md` — runtime/operator docs for `/runtime`, pause/resume, and controller semantics.
- `.gsd/KNOWLEDGE.md` — added the controller-vs-cycle runtime pattern and the callback-order drift lesson.
- `.gsd/PROJECT.md` — updated current project state to reflect S02 completion.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marked S02 complete.
- `.gsd/milestones/M002/slices/S02/S02-UAT.md` — recorded live runtime UAT.

## Forward Intelligence

### What the next slice should know
- The runtime truth contract is no longer “latest cycle + hope.” Use `repository.runtime_status()` everywhere that needs current operator state.
- `scheduled` is a healthy waiting state, not a disguised completion state. If a later UI writes “completed” on a healthy waiting runtime, it is regressing S02.
- `/health` now carries controller truth too; it is no longer just a shallow DB ping.

### What's fragile
- Continuous-mode truth still depends on callback and transition ordering in `RadarRuntimeService.run_continuous()` — changing that flow casually can reintroduce transient drift between `/api/runtime` and `/health`.
- Browser-level cleanliness on `/runtime` currently depends on keeping the inline favicon and route-local assets self-contained; removing them can reintroduce noisy console errors.

### Authoritative diagnostics
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s02.db --format json` — fastest authoritative read of controller truth.
- `/api/runtime` — same contract the runtime page reads, useful when diagnosing whether a problem is data or rendering.
- `/health` — quickest high-level confirmation that current runtime state and latest cycle are still aligned.

### What assumptions changed
- “The latest completed cycle is good enough to describe the current runtime.” — false; healthy waiting loops and operator pauses require a separate controller snapshot.
- “Observer callbacks can happen before the next controller transition is persisted.” — false; live smoke showed that order can create a real user-visible truth gap.
