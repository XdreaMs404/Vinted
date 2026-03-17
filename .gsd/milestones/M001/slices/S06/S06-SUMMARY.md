---
id: S06
parent: M001
milestone: M001
provides:
  - A real local `batch` operator command that runs one coherent discovery plus state-refresh radar cycle
  - A real local `continuous` operator command that repeats the radar cycle while optionally serving the dashboard from the same DB
  - Persisted runtime-cycle diagnostics in SQLite, exposed through `runtime-status`, `/api/runtime`, `/health`, and the dashboard runtime card
requires:
  - slice: S01
    provides: public discovery, normalized listing persistence, and coverage footprint
  - slice: S02
    provides: repeated observation history, freshness, and revisit surfaces
  - slice: S03
    provides: cautious state evaluation, confidence labels, and item-page probe evidence
  - slice: S04
    provides: demand/premium scoring and market-summary assembly from repository-backed evidence
  - slice: S05
    provides: the server-rendered dashboard and truthful JSON diagnostics
affects:
  - M002
key_files:
  - vinted_radar/services/runtime.py
  - vinted_radar/repository.py
  - vinted_radar/db.py
  - vinted_radar/cli.py
  - vinted_radar/dashboard.py
  - tests/test_runtime_service.py
  - tests/test_runtime_cli.py
key_decisions:
  - D016
patterns_established:
  - Persist operator runtime state in `runtime_cycles` and let both the CLI and dashboard read that table instead of inventing separate scheduler state files.
observability_surfaces:
  - `python -m vinted_radar.cli runtime-status --db <path>`
  - `http://127.0.0.1:8765/api/runtime`
  - `http://127.0.0.1:8765/health`
  - `runtime_cycles` in SQLite
  - dashboard runtime card
drill_down_paths:
  - .gsd/milestones/M001/slices/S06/S06-PLAN.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-17
---

# S06: Local Batch + Continuous End-to-End Loop

**The radar now has a real local operator loop: one command runs a batch cycle, one command keeps it alive continuously, and both modes leave durable runtime truth behind in the same SQLite database the dashboard already reads.**

## What Happened

S06 closed the last missing runtime seam in M001. Up to S05, the repository had all the evidence, state, scoring, and UI pieces, but the operator still had to glue discovery, state refresh, and dashboard serving together manually. This slice introduced `vinted_radar/services/runtime.py`, which orchestrates one coherent radar cycle around the existing `DiscoveryService` and `StateRefreshService`, and persists each cycle into a new SQLite `runtime_cycles` table with status, phase, configured limits, linked discovery run id, probe counts, freshness snapshot, and last-error state.

That runtime truth is not hidden behind a separate daemon file or in-memory scheduler object. `runtime-status` reads it from SQLite, the dashboard runtime card reads it from SQLite, `/api/runtime` exposes it directly, and `/health` now includes the latest runtime-cycle state alongside the broader dashboard health payload. The runtime service marks phases explicitly (`starting`, `discovery`, `state_refresh`, `summarizing`, `completed`) so a future agent can see whether the loop is currently scanning, probing, or simply idle between cycles.

The CLI now exposes three operator-level entrypoints:

- `batch` for one composed discovery + state-refresh cycle
- `continuous` for repeated cycles on an interval, with optional dashboard serving in the same process lifetime
- `runtime-status` for table or JSON inspection of recent runtime cycles and failures

The focused commands (`discover`, `state-refresh`, `dashboard`, `coverage`, `freshness`, `state`, `score`, etc.) remain in place as lower-level diagnostics. S06 did not replace them; it added the missing top-level operating loop.

Live verification used a fresh `data/vinted-radar-s06.db`. The batch cycle completed successfully with 4 successful scans, 384 unique listing IDs, and 6 state probes. The continuous loop then ran repeated 2-leaf cycles while serving the dashboard on `127.0.0.1:8766`; completed continuous cycles added more follow-up history and moved the DB from 399 tracked listings to 414+ while `/api/runtime` and the dashboard runtime card truthfully showed in-flight phases (`discovery`, `state_refresh`) for the currently running cycle.

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli batch --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --request-delay 0.0`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s06.db --format json`
- `python -m vinted_radar.cli continuous --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8766`
- Browser verification at `http://127.0.0.1:8766`:
  - dashboard renders the runtime card, demand proof table, and diagnostics section while the continuous loop is running
  - explicit browser assertions passed for visible runtime state, visible demand proof, zero console errors, and zero failed requests on the main dashboard page
- Direct local HTTP checks confirmed:
  - `/api/runtime` exposed a running continuous cycle plus multiple completed continuous cycles in history
  - `/health` included the latest runtime cycle and tracked listing count
  - `/api/dashboard` reflected the current DB-backed dashboard payload during continuous operation

## Requirements Advanced

- R001 — S06 now gives broad public discovery a real operator loop instead of leaving it as a manual command sequence.
- R002 — repeated continuous cycles now make persisted revisit history operational rather than theoretical.
- R003 — the state-refresh loop is now part of the top-level operator workflow instead of a separate manual follow-up step.
- R011 — runtime failures now stay inspectable through persisted cycle phase/error state instead of disappearing into transient console output.

## Requirements Validated

- R010 — batch and continuous operator modes now both exist, were live-verified against a fresh DB, and expose persisted runtime diagnostics through the CLI plus dashboard.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The written demo command in the plan used `--max-cycles 2` for continuous verification, but the strongest live browser proof came from leaving the continuous loop running past that short cap so the dashboard could be inspected while a cycle was actively in-flight. The feature scope did not change; only the exact live verification shape did.

## Known Limitations

The dashboard can legitimately show an in-progress discovery run with zeroed latest-run scan counters while still rendering rankings and freshness from the last completed evidence already in SQLite. That is truthful but potentially surprising if someone expects all runtime and market surfaces to update atomically.

Continuous mode currently runs the whole discovery + state-refresh cycle on a fixed interval. It does not yet prioritize different sub-loops independently or add backoff/jitter logic beyond the existing request delay.

The code path is complete, but the milestone’s “multi-day credibility” still depends on actually leaving it running long enough to accumulate richer history. S06 removed the implementation blocker; it did not compress calendar time.

## Follow-ups

- Reassess M001 once the continuous loop has been left running long enough to inspect a genuinely multi-day market read instead of a same-session growth curve.
- Decide in M002 whether the dashboard should distinguish the current in-flight cycle from the last completed market snapshot more explicitly.
- Consider whether continuous mode should later split discovery cadence from probe cadence once real runtime history reveals where the operator value is highest.

## Files Created/Modified

- `vinted_radar/services/runtime.py` — new runtime orchestration service for composed batch cycles and repeated continuous cycles.
- `vinted_radar/db.py` — added SQLite `runtime_cycles` schema and index.
- `vinted_radar/repository.py` — added runtime-cycle persistence, phase updates, and runtime status hydration helpers.
- `vinted_radar/cli.py` — added `batch`, `continuous`, and `runtime-status` operator commands plus runtime-aware dashboard output.
- `vinted_radar/dashboard.py` — added `/api/runtime`, runtime state in `/health`, background dashboard server startup helper, and the runtime card/diagnostic link on the dashboard.
- `README.md` — documented the new operator workflow, runtime API, and runtime-cycle diagnostics.
- `tests/test_runtime_service.py` — covered completed cycles plus continuous failure persistence/continuation.
- `tests/test_runtime_cli.py` — covered CLI wiring for `batch`, `continuous`, and `runtime-status`.
- `tests/test_dashboard.py` — extended dashboard coverage to runtime payloads and runtime-aware health output.
- `tests/test_dashboard_cli.py` — updated dashboard CLI expectations for the runtime API URL.
- `.gsd/REQUIREMENTS.md` — validated R010 and refreshed coverage counts.
- `.gsd/DECISIONS.md` — recorded the S06 runtime observability architecture decision.
- `.gsd/KNOWLEDGE.md` — captured the runtime-cycle persistence pattern and the in-flight dashboard truth lesson.
- `.gsd/PROJECT.md` — updated the project’s current state and architecture to include the operator loop.
- `.gsd/STATE.md` — advanced the global state from S06 planning to completed handoff.
- `.gsd/milestones/M001/M001-ROADMAP.md` — marked S06 complete.
- `.gsd/milestones/M001/slices/S06/S06-PLAN.md` — marked all S06 tasks complete.

## Forward Intelligence

### What the next slice should know
- `runtime_cycles` is now the authoritative operator truth for batch/continuous phase, counts, and failures; do not create parallel scheduler state unless there is a compelling new boundary.
- The dashboard’s runtime card and `/api/runtime` are the fastest way to answer “what is the loop doing right now?” without reading raw logs.
- `continuous --dashboard` is the strongest end-to-end local proof path because it exercises orchestration, persistence, and the product surface against the same DB.

### What's fragile
- The dashboard mixes last completed market evidence with the currently running runtime cycle. That is truthful, but it can look inconsistent if someone assumes the market tables are always tied to the in-flight run.
- The current process tracker can misclassify the long-running command because the CLI prints “failed” counts and 404 favicon lines during ordinary operation; rely on `/health` and `/api/runtime` first.

### Authoritative diagnostics
- `python -m vinted_radar.cli runtime-status --db <path> --format json` — exact persisted runtime-cycle history, including last error and phase.
- `http://127.0.0.1:8765/api/runtime` — same runtime truth as JSON from the dashboard process itself.
- `http://127.0.0.1:8765/health` — quickest combined signal that the dashboard is serving and the DB has current runtime state.

### What assumptions changed
- “S06 only needs a loop wrapper around existing commands.” — false; without persisted runtime phase/error state, continuous mode would have been operationally opaque and hard to trust.
- “The dashboard can only be truthful once a cycle fully completes.” — false; it can show in-flight runtime truth and last completed market evidence side by side, as long as that distinction stays explicit.
