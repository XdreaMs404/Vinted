---
id: T03
parent: S02
milestone: M002
provides:
  - French-first `/runtime` page, controller-backed `/api/runtime`, and overview/runtime copy that now reads current controller truth instead of inferring from the last completed cycle
key_files:
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - README.md
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
key_decisions:
  - D025: keep the runtime UI/API grounded in the controller snapshot rather than the latest cycle row
patterns_established:
  - During continuous mode, controller transitions back to `scheduled`/`paused` must happen before observer-facing callbacks so `/runtime`, `/api/runtime`, `/health`, and `/` do not drift through an avoidable idle window
observability_surfaces:
  - `/runtime`
  - `/api/runtime`
  - `/health`
  - `python -m vinted_radar.cli runtime-status --format json`
  - `tests/test_dashboard.py`
  - browser verification on `http://127.0.0.1:8781/runtime`
duration: 55m
verification_result: passed
completed_at: 2026-03-23T09:45:00+01:00
blocker_discovered: false
---

# T03: Expose runtime truth through `/runtime`, `/api/runtime`, and the overview shell

**Added a dedicated French runtime page, extended the runtime API/shell to read controller truth, and fixed the last-cycle drift window found during live smoke verification.**

## What Happened

I turned the new controller contract into the real product/runtime surface.

In `vinted_radar/dashboard.py`, I added:
- a dedicated `build_runtime_payload()` seam on top of `repository.runtime_status(...)`
- a French-first `/runtime` HTML page that shows current status, phase, heartbeat age, pause timing, next resume timing, recent failures, and immutable recent-cycle history
- a richer `/health` payload with `current_runtime_status` and controller data
- overview-home runtime wording that now reads `current_runtime_status` from the controller-backed freshness summary instead of implying that the runtime is simply whatever the last cycle row says
- diagnostics links that now include both `/runtime` and `/api/runtime`

I also updated `vinted_radar/cli.py` and `README.md` so the local server output and operator docs advertise the runtime page and the pause/resume controller semantics.

During live smoke verification, I found two real issues:

1. **Observer drift window between cycle completion and re-scheduling**
   - `/api/runtime` and `/health` could briefly disagree because `run_continuous()` called the observer callback before persisting the next `scheduled` / `paused` controller state.
   - I fixed the order in `vinted_radar/services/runtime.py` so the controller transition happens before callback-driven observation.

2. **Runtime page console noise from a missing favicon**
   - The new `/runtime` page emitted a 404 favicon request, which showed up as a browser console error during verification.
   - I added an inline SVG favicon and re-ran the browser assertions to get a clean runtime page load.

I also polished the runtime page copy so the product surface is French-first (`planifié`, `en pause`, `en cours`, `collecte`, `attente`) while JSON/runtime contract values stay machine-readable.

## Verification

I verified T03 in three layers:

1. Route/CLI regression tests:
   - `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_runtime_cli.py`
2. Full slice regression pack:
   - `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_db_recovery.py`
3. Real local smoke with the actual CLI continuous loop:
   - started `python -m vinted_radar.cli continuous --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8781`
   - exercised `runtime-pause` and `runtime-resume`
   - confirmed `/api/runtime` and `/health` agree on `running`, then `paused`, then `scheduled`
   - verified `/runtime` and `/` in the browser, including a clean runtime-page console/network state after the favicon fix

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_runtime_cli.py` | 0 | ✅ pass | 0.73s |
| 2 | `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_db_recovery.py` | 0 | ✅ pass | 1.26s |
| 3 | `python -m vinted_radar.cli continuous --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8781` | n/a (ready) | ✅ pass | ready in ~9s |
| 4 | `python -m vinted_radar.cli runtime-pause --db data/vinted-radar-s02.db` + `/api/runtime` + `/health` | 0 + HTTP 200 | ✅ pass | live smoke |
| 5 | `python -m vinted_radar.cli runtime-resume --db data/vinted-radar-s02.db` + `/api/runtime` + `/health` | 0 + HTTP 200 | ✅ pass | live smoke |
| 6 | `browser_assert @ http://127.0.0.1:8781/runtime` (`url_contains`, runtime text, no_console_errors_since, no_failed_requests_since) | n/a | ✅ pass | live smoke |

## Diagnostics

The authoritative runtime inspection surfaces are now:
- `/runtime` for the French operator view
- `/api/runtime` for the raw controller + cycle payload
- `/health` for quick controller/current-status confirmation
- `python -m vinted_radar.cli runtime-status --format json`
- `tests/test_dashboard.py` for route and payload drift

If `/runtime` and `/health` disagree in the future, look first at the ordering inside `RadarRuntimeService.run_continuous()` before blaming the WSGI layer.

## Deviations

- I made one extra runtime-service change during T03: scheduling/pausing now persists before observer callbacks, because live smoke proved the previous order could create a user-visible truth gap between `/api/runtime` and `/health`.

## Known Issues

- The new runtime page is local-server verified, but S03 still owns the responsive VPS shell and remote phone/desktop serving path.
- The runtime page and home copy are now French-first, but the explorer remains intentionally brownfield-English until the shell slice takes broader product copy/layout ownership.

## Files Created/Modified

- `vinted_radar/dashboard.py` — added `build_runtime_payload()`, `/runtime`, controller-backed home/runtime wording, runtime-page rendering, richer `/health`, translated runtime labels, and favicon fix.
- `vinted_radar/services/runtime.py` — moved schedule/pause transitions ahead of observer callbacks to remove the live drift window.
- `vinted_radar/cli.py` — local dashboard output now advertises `/runtime`.
- `README.md` — documented `/runtime`, pause/resume controls, and controller-vs-cycle semantics.
- `tests/test_dashboard.py` — added payload/route coverage for controller-backed runtime truth and the new runtime page.
- `tests/test_dashboard_cli.py` — updated dashboard CLI route expectations for `/runtime`.
- `.gsd/milestones/M002/slices/S02/S02-PLAN.md` — marked T03 complete.
