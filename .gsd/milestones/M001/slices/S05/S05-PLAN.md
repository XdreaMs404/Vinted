# S05: Mixed Dashboard + Filters + Listing Detail

**Goal:** Ship a local web dashboard that renders the existing coverage, freshness, state, and scoring surfaces into one mixed product view with useful filters and a listing detail drill-down.
**Demo:** Run `python -m vinted_radar.cli dashboard --db data/vinted-radar.db --host 127.0.0.1 --port 8765`, open `http://127.0.0.1:8765`, filter the rankings, and open a listing detail panel that shows timeline, signals, score breakdown, and inference basis.

## Must-Haves

- Render market summary, coverage/freshness/confidence context, and listing-level ranking proof in one local dashboard.
- Support useful filter state without recomputing business logic in the UI.
- Provide a listing detail drill-down with timeline, transitions/signals, and inference basis from the existing repository/state/scoring surfaces.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli discover --db data/vinted-radar-s05.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s05.db --limit 8 --request-delay 0.0`
- `python -m vinted_radar.cli market-summary --db data/vinted-radar-s05.db --limit 6 --format json`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` + browser verification at `http://127.0.0.1:8765`

## Observability / Diagnostics

- Runtime signals: latest run metadata, freshness buckets, state confidence counts, filtered result count, and explicit empty-state messaging.
- Inspection surfaces: HTML dashboard, `/api/dashboard` JSON payload, `/api/listings/<id>` JSON detail payload, existing CLI commands (`coverage`, `freshness`, `state`, `score`, `market-summary`).
- Failure visibility: dashboard empty states, surfaced scan failures from the latest run, and JSON endpoints that expose the exact server-side payload.
- Redaction constraints: only already-public normalized fields, score/state explanations, and stored evidence fragments already retained in SQLite.

## Integration Closure

- Upstream surfaces consumed: `RadarRepository` history/coverage/state inputs, `evaluate_listing_state`, `load_listing_scores`, `build_rankings`, and `build_market_summary`.
- New wiring introduced in this slice: server-side dashboard payload assembly, local HTTP serving, filter query parsing, and listing-detail drill-down.
- What remains before the milestone is truly usable end-to-end: continuous runtime orchestration and long-lived local operation in S06.

## Tasks

- [ ] **T01: Build dashboard payloads and restore a truthful test harness** `est:1h15m`
  - Why: S05 needs stable server-side payload assembly and working tests before adding a UI shell.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/repository.py`, `tests/test_dashboard.py`, `tests/conftest.py`, `tests/test_repository.py`
  - Do: add dashboard-focused payload builders and filter parsing on top of the existing state/scoring surfaces, expose listing-detail payload assembly, and remove or quarantine legacy prototype-only pytest wiring that no longer matches the active package.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_scoring.py tests/test_state_machine.py tests/test_history_repository.py`
  - Done when: dashboard payloads cover summary, rankings, filters, and detail drill-down, and pytest no longer fails during collection on legacy imports.
- [ ] **T02: Serve the mixed dashboard and wire the CLI entrypoint** `est:1h30m`
  - Why: the slice is only real once the local operator can open the product surface in a browser.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, `README.md`, `tests/test_dashboard_cli.py`
  - Do: implement a local HTTP server and server-rendered dashboard page with a strong visual hierarchy, filter controls, ranking tables, drill-down links, and JSON diagnostic endpoints; add a `dashboard` CLI command that serves the app without introducing new business logic paths.
  - Verify: `python -m pytest tests/test_dashboard_cli.py tests/test_dashboard.py tests/test_cli_smoke.py`
  - Done when: the dashboard server starts from the CLI, renders the mixed market view, and exposes JSON diagnostics for the same server-side payload.
- [ ] **T03: Run live browser verification and persist the S05 handoff** `est:45m`
  - Why: S05 is an integration slice with a UI promise; it needs live proof and a clean downstream handoff.
  - Files: `.gsd/milestones/M001/slices/S05/S05-PLAN.md`, `.gsd/milestones/M001/slices/S05/S05-SUMMARY.md`, `.gsd/milestones/M001/M001-ROADMAP.md`, `.gsd/PROJECT.md`, `.gsd/STATE.md`, `.gsd/KNOWLEDGE.md`
  - Do: verify the real dashboard against the current local DB in a browser, record any UI/data lessons that matter for S06, mark the slice complete, and refresh the global GSD state/docs.
  - Verify: the slice verification commands plus explicit browser assertions on the live dashboard.
  - Done when: the real dashboard is interactively verified, slice artifacts are updated, and the next slice can continue from current state without re-discovery.

## Files Likely Touched

- `vinted_radar/dashboard.py`
- `vinted_radar/cli.py`
- `vinted_radar/repository.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
- `README.md`
