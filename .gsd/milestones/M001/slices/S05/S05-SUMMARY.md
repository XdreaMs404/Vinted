---
id: S05
parent: M001
milestone: M001
provides:
  - Local mixed dashboard with market-summary modules, coverage/freshness/confidence cards, and filterable ranking proof
  - Listing-detail drill-down with history, transitions, score factors, and state reasons
  - Matching JSON diagnostics for the exact dashboard payload and selected listing detail
requires:
  - slice: S03
    provides: cautious state explanations, confidence labels, basis kinds, and listing history/state inputs
  - slice: S04
    provides: demand/premium score payloads, contextual price explanations, and market-summary aggregates
affects:
  - S06
key_files:
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
  - .gsd/REQUIREMENTS.md
key_decisions:
  - D015
patterns_established:
  - Drive dashboard HTML and JSON diagnostics from the same server-side payload assembly.
observability_surfaces:
  - `python -m vinted_radar.cli dashboard --db <path> --host 127.0.0.1 --port 8765`
  - `http://127.0.0.1:8765/api/dashboard`
  - `http://127.0.0.1:8765/api/listings/<id>`
  - `http://127.0.0.1:8765/health`
drill_down_paths:
  - .gsd/milestones/M001/slices/S05/S05-PLAN.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-17
---

# S05: Mixed Dashboard + Filters + Listing Detail

**A local dashboard now renders the market summary first, keeps ranking proof directly underneath, and drills into listing history, signals, and inference basis without inventing separate client-side logic.**

## What Happened

S05 turned the existing CLI-first radar into an actual local product surface. The new `vinted_radar/dashboard.py` assembles one server-side payload from the repository, state machine, and scoring layer, then uses that same payload both for the HTML dashboard and for JSON diagnostic endpoints. That keeps the browser view truthful: if something looks wrong in the UI, `/api/dashboard` and `/api/listings/<id>` expose the exact server-side data that produced it.

The dashboard itself is server-rendered and dependency-light. It shows latest-run coverage, freshness, and confidence cards; performing and rising segment modules; separate demand and premium ranking tables; filter controls for root/state/catalog/search/row count; and a sticky listing-detail panel with history, transition events, score-factor breakdowns, and state reasons. The CLI gained a `dashboard` command that serves this UI locally and prints the dashboard/API URLs.

This slice also repaired the test floor. The suite was still carrying a dead `src/`-era `storage.Repository` harness plus several placeholder `pytest.fail(...)` files. Those were replaced with contracts against the active `RadarRepository`, parser, discovery, dashboard, and CLI surfaces so `python -m pytest` is meaningful again.

Live verification used a fresh `data/vinted-radar-s05.db` generated from real public discovery plus a small probe pass. The resulting market surface is still shallow — after one run the live dataset is overwhelmingly first-pass active listings — but the dashboard truthfully shows that shallowness instead of hiding it.

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli discover --db data/vinted-radar-s05.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s05.db --limit 8 --request-delay 0.0`
- `python -m vinted_radar.cli market-summary --db data/vinted-radar-s05.db --limit 6 --format json`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765`
- Browser verification at `http://127.0.0.1:8765`:
  - initial render loads with the expected dashboard sections
  - root filter changes the URL and segment/ranking surface (`root=Femmes`)
  - listing detail panel remains populated with score/state/history content
  - no console errors or failed requests after the favicon fix and reload pass

## Requirements Advanced

- R004 — coverage, freshness, and confidence surfaces now exist in the main product UI instead of only the CLI.
- R005 — the demand-led ranking is now rendered on the dashboard with drill-down score explanations.
- R006 — the separate premium ranking is now rendered on the dashboard with contextual-price detail.
- R008 — performing and rising segments now lead the main product surface.
- R009 — the mixed dashboard, filters, and listing-detail drill-down now exist end to end.

## Requirements Validated

- R004 — browser-verified dashboard cards and detail surfaces now make coverage/freshness/confidence visible in the product.
- R005 — demand ranking is visible and explainable on the main product surface.
- R006 — premium ranking is visibly separate and context-aware on the main product surface.
- R008 — the main product surface now summarizes performing and rising segments.
- R009 — the main product surface now combines summary, rankings, filters, and listing detail as required.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The written plan referenced `data/vinted-radar-s02.db` for live verification, but that DB was not present locally. The live pass used a fresh `data/vinted-radar-s05.db` generated during this slice instead. That changed the proof dataset, not the feature scope.

## Known Limitations

The dashboard is server-rendered with full-page reloads for filter changes rather than a richer reactive client. That is acceptable for S05, but not yet the most fluid UX.

The live browser-verified dataset is still mostly first-pass active listings after one discovery run, so demand rows are flat and the segment modules are dominated by recent-arrival counts. The UI is honest about that, but S06 still needs repeated runtime history to make the market read more informative.

## Follow-ups

- Build S06 around a real batch orchestration command plus a continuous loop that keeps discovery, state refresh, score recomputation, and dashboard serving coherent.
- Consider adding an explicit global time-window card once continuous mode creates a broader observation span than the latest run alone.
- Revisit whether dashboard filters should expose confidence/basis once the continuous loop creates more mixed state distributions.

## Files Created/Modified

- `vinted_radar/dashboard.py` — server-side dashboard payload assembly, WSGI app, HTML renderer, and JSON diagnostic endpoints.
- `vinted_radar/cli.py` — local `dashboard` entrypoint wired to the dashboard server.
- `README.md` — documented the dashboard entrypoint and diagnostics URLs.
- `tests/test_dashboard.py` — payload and WSGI route coverage for the dashboard surface.
- `tests/test_dashboard_cli.py` — CLI wiring coverage for the dashboard command.
- `tests/conftest.py` — removed the dead legacy storage import that broke pytest collection.
- `tests/test_repository.py` — replaced obsolete `src/` storage tests with contracts for the active `RadarRepository`.
- `tests/test_catalog_tree.py` — real parser coverage instead of a placeholder failure.
- `tests/test_discovery_normalization.py` — real card-normalization coverage instead of a placeholder failure.
- `tests/test_flight_extract.py` — real escaped-flight extraction coverage instead of a placeholder failure.
- `tests/test_cli_discover_smoke.py` — real discover CLI smoke coverage instead of a placeholder failure.
- `.gsd/REQUIREMENTS.md` — marked the dashboard-owned product requirements as validated.
- `.gsd/DECISIONS.md` — recorded the dashboard delivery architecture decision.
- `.gsd/KNOWLEDGE.md` — captured the shared HTML/JSON payload pattern.

## Forward Intelligence

### What the next slice should know
- The dashboard already exposes truthful JSON at `/api/dashboard` and `/api/listings/<id>`; S06 should lean on those diagnostics instead of adding ad hoc debug state.
- Filter changes currently round-trip through query params and full page reloads, which keeps the implementation simple and reproducible for debugging.
- The product surface is now real enough that S06 should verify end-to-end workflows against the dashboard, not just against CLI tables.

### What's fragile
- Live first-pass data produces flat demand scores and repetitive segment cards — that is a data-shape limitation, not necessarily a UI bug.
- The server is intentionally minimal and single-process; if S06 adds heavier background orchestration, dashboard/data refresh coordination will need care.

### Authoritative diagnostics
- `http://127.0.0.1:8765/api/dashboard` — exact payload behind the rendered dashboard.
- `http://127.0.0.1:8765/api/listings/<id>` — exact payload behind the selected listing detail panel.
- `python -m vinted_radar.cli market-summary --db <path> --format json` — fastest non-browser check for segment-level summary logic.

### What assumptions changed
- "S05 needs a JS-heavy frontend or a separate client app." — false; a server-rendered local dashboard was enough to satisfy the slice without drifting away from the existing truth surfaces.
