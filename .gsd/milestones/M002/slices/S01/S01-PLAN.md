# S01: SQL-Backed Overview Home + First Comparative Modules

**Goal:** Replace the M001 truth-screen home with a French-first market overview whose primary payload comes from repository-owned SQL aggregates instead of full-corpus Python recomputation, while keeping coverage, freshness, confidence, and uncertainty explicit.
**Demo:** Run `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765`, open `http://127.0.0.1:8765/`, and verify that `/` presents a French market overview backed by SQL summary/comparison queries, with clear coverage/freshness/confidence cues and drill-down paths into `/explorer`, `/api/runtime`, and listing detail JSON.

## Must-Haves

- Replace the home-path full-corpus `load_listing_scores()` / `build_market_summary()` posture with repository-owned SQL overview queries that return summary blocks and first comparison modules for category, brand, price band, condition, and sold-state lenses.
- Make `/` read like a French market-overview product surface rather than an M001 debugger dashboard, while preserving clear navigation into `/explorer` and runtime diagnostics.
- Support active requirement `R011` on this slice by keeping partial, degraded, inferred, estimated, and low-support signals visible instead of smoothing them away.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765`
- Browser verification at `http://127.0.0.1:8765/` confirms French overview headings, visible coverage/freshness/confidence honesty, first comparison modules, and working links to `/explorer`, `/api/dashboard`, `/api/runtime`, and `/health`.

## Observability / Diagnostics

- Runtime signals: overview payload support counts, low-support / partial-signal flags, latest successful scan window, latest runtime-cycle status, and recent acquisition failures.
- Inspection surfaces: `/api/dashboard` (and any compatibility alias added in this slice), `/api/runtime`, `/health`, seeded pytest fixtures, and the underlying SQLite tables queried through `RadarRepository`.
- Failure visibility: empty or thin-support modules must expose explicit reasons; home-route regressions remain diagnosable through JSON payloads instead of HTML-only symptoms.
- Redaction constraints: expose only public listing metadata, aggregate counts, and already-retained evidence signals; no secrets or operator credentials belong in the overview payload.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/repository.py`, `vinted_radar/state_machine.py`, `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, and the existing SQLite evidence/runtime tables.
- New wiring introduced in this slice: repository-owned SQL overview contract, French overview payload/rendering on `/`, and compatibility wiring from the local dashboard command into the new home semantics.
- What remains before the milestone is truly usable end-to-end: S02 still needs richer persisted runtime truth, S03 still needs the full responsive product shell / VPS path, and S04 still needs the deeper explorer/comparison workflow.

## Tasks

- [ ] **T01: Define the SQL overview contract and comparison lenses** `est:1h30m`
  - Why: The home-path scale risk only goes away if overview counts, honesty cues, and comparison modules can be assembled in SQL without scoring the entire corpus in Python first.
  - Files: `vinted_radar/repository.py`, `vinted_radar/state_machine.py`, `tests/test_overview_repository.py`, `tests/test_history_repository.py`
  - Do: promote the current listing-state evidence into a reusable SQL overview contract; expose summary blocks plus category/brand/price-band/condition/sold-state comparison modules with support metadata and drill-down lens values; keep observed/inferred/estimated/partial-signal honesty explicit.
  - Verify: `python -m pytest tests/test_overview_repository.py tests/test_history_repository.py`
  - Done when: repository tests prove that the overview home can get its primary payload from SQL aggregates and comparison modules without requiring full-corpus Python ranking work.
- [ ] **T02: Rebuild `/` as a French overview home on top of the SQL contract** `est:1h30m`
  - Why: S01 is only complete when the actual default route stops reading like an M001 debug dashboard and starts behaving like the new market overview product surface.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, `README.md`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`, `tests/test_overview_repository.py`
  - Do: refactor the home payload/rendering to consume the T01 SQL contract, switch the main copy and sectioning to French-first overview language, surface low-support and degraded-signal notes in the UI, and preserve links to `/explorer`, runtime diagnostics, and listing-detail JSON without reintroducing full-corpus Python recomputation on the primary path.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: `/` and its JSON payload render the new overview surface, the local dashboard command still serves it cleanly, and browser verification shows the expected French overview / comparison / honesty signals.

## Files Likely Touched

- `vinted_radar/repository.py`
- `vinted_radar/dashboard.py`
- `vinted_radar/cli.py`
- `vinted_radar/state_machine.py`
- `tests/test_overview_repository.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
- `README.md`
