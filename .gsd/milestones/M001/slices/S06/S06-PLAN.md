# S06: Local Batch + Continuous End-to-End Loop

**Goal:** Ship a simple local operator workflow that can run the radar once or keep it running continuously, while persisting truthful runtime diagnostics and exposing them through both the CLI and dashboard.
**Demo:** Run `python -m vinted_radar.cli batch --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --request-delay 0.0`, then run `python -m vinted_radar.cli continuous --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --interval-seconds 1 --max-cycles 2 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8766`, open `http://127.0.0.1:8766`, and verify that the dashboard plus runtime diagnostics reflect the assembled radar loop.

## Must-Haves

- Provide one straightforward batch command that runs discovery plus state refresh as a coherent radar cycle and leaves inspectable runtime state behind.
- Provide one continuous command that repeats the radar cycle on an interval without losing failure visibility.
- Persist runtime-cycle status, phase, counts, and last-error diagnostics in SQLite, then expose the same truth through the dashboard and a CLI inspection command.

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli batch --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --request-delay 0.0`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s06.db --format json`
- `python -m vinted_radar.cli continuous --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --interval-seconds 1 --max-cycles 2 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8766`
- Browser verification at `http://127.0.0.1:8766` with explicit checks against `/api/dashboard`, `/api/runtime`, and `/health`

## Observability / Diagnostics

- Runtime signals: persisted runtime-cycle status, phase, discovery run linkage, probe counts, tracked-listing counts, freshness counts, and last error.
- Inspection surfaces: `runtime-status` CLI output, `/api/runtime`, `/health`, existing dashboard JSON endpoints, and the `runtime_cycles` table in SQLite.
- Failure visibility: failed or interrupted cycles retain their phase and `last_error` instead of disappearing into console-only output.
- Redaction constraints: diagnostics expose only public listing metadata, public URLs, counts, and already-retained evidence fragments; no secrets are introduced.

## Integration Closure

- Upstream surfaces consumed: `DiscoveryService`, `StateRefreshService`, `RadarRepository`, `load_listing_scores`, `build_market_summary`, and the existing dashboard application.
- New wiring introduced in this slice: runtime-cycle persistence, batch/continuous orchestration commands, dashboard runtime diagnostics, and end-to-end local operator flow.
- What remains before the milestone is truly usable end-to-end: nothing inside M001 beyond real-world runtime time itself.

## Tasks

- [ ] **T01: Persist runtime cycles and orchestrate one truthful radar cycle** `est:1h30m`
  - Why: S06 needs durable runtime state and a real composed batch loop before continuous mode can exist.
  - Files: `vinted_radar/db.py`, `vinted_radar/repository.py`, `vinted_radar/services/runtime.py`, `tests/test_runtime_service.py`
  - Do: add SQLite-backed runtime-cycle tracking with phase/status/error fields, implement a runtime service that composes discovery plus state refresh into one batch cycle, and persist summary counts after each cycle.
  - Verify: `python -m pytest tests/test_runtime_service.py tests/test_discovery_service.py tests/test_state_machine.py`
  - Done when: one batch cycle can run through the runtime service, leaves persisted runtime diagnostics behind, and failed phases remain inspectable.
- [ ] **T02: Expose operator commands and dashboard/runtime diagnostics** `est:1h30m`
  - Why: the slice is only useful if one operator can run it simply and inspect the current runtime truth without reading raw tables.
  - Files: `vinted_radar/cli.py`, `vinted_radar/dashboard.py`, `README.md`, `tests/test_runtime_cli.py`, `tests/test_dashboard.py`
  - Do: add `batch`, `continuous`, and `runtime-status` CLI commands, wire optional dashboard serving into continuous mode, expose runtime diagnostics through the dashboard and JSON endpoints, and keep the old focused commands available for drill-down.
  - Verify: `python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_cli_smoke.py`
  - Done when: batch and continuous commands are documented, runtime status is inspectable from both CLI and browser, and the dashboard reflects the latest radar cycle state.
- [ ] **T03: Run live end-to-end proof and refresh the GSD handoff** `est:1h`
  - Why: S06 is the milestone-closure slice; it needs real local proof plus current state artifacts.
  - Files: `.gsd/milestones/M001/slices/S06/S06-PLAN.md`, `.gsd/milestones/M001/slices/S06/S06-SUMMARY.md`, `.gsd/milestones/M001/M001-ROADMAP.md`, `.gsd/PROJECT.md`, `.gsd/STATE.md`, `.gsd/KNOWLEDGE.md`, `.gsd/REQUIREMENTS.md`
  - Do: run the real batch and continuous workflows against a fresh DB, verify the dashboard/runtime APIs in the browser, capture any runtime lessons, mark the roadmap slice complete, and update requirement/state artifacts.
  - Verify: the slice verification commands plus explicit browser assertions on the live local dashboard.
  - Done when: the assembled loop is verified locally, slice docs reflect current reality, and the next milestone can start without re-deriving S06 behavior.

## Files Likely Touched

- `vinted_radar/services/runtime.py`
- `vinted_radar/repository.py`
- `vinted_radar/db.py`
- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`
- `README.md`
- `tests/test_runtime_service.py`
- `tests/test_runtime_cli.py`
