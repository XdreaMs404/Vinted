---
id: S01
parent: M002
milestone: M002
provides:
  - A repository-owned SQL `overview_snapshot()` contract for the default home path, including summary inventory, honesty, freshness, and first comparison modules
  - A French-first `/` overview home backed by SQL aggregates instead of full-corpus request-time Python recomputation
  - A SQL-paged explorer seam and featured-listing drill-down pattern that keeps the main overview path scalable while preserving `/api/dashboard`, `/api/runtime`, `/health`, and listing-detail JSON diagnostics
requires: []
affects:
  - S02
  - S03
  - S04
  - S05
  - S06
  - S07
key_files:
  - vinted_radar/repository.py
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - tests/test_overview_repository.py
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
  - README.md
  - data/vinted-radar-s01.db
key_decisions:
  - D021
  - D022
patterns_established:
  - Keep SQL overview state classification numerically aligned with `state_machine.py` constants so overview, CLI state, and later detail/runtime surfaces do not drift.
  - Keep the overview home SQL-first by building it from `overview_snapshot()` and sourcing featured listing cards from `listing_explorer_page()` instead of the legacy scored-home helpers.
observability_surfaces:
  - `RadarRepository.overview_snapshot()`
  - `RadarRepository.listing_explorer_page()`
  - `/api/dashboard`
  - `/api/explorer`
  - `/api/runtime`
  - `/health`
  - `tests/test_overview_repository.py`
  - `tests/test_dashboard.py`
drill_down_paths:
  - `.gsd/milestones/M002/slices/S01/S01-PLAN.md`
  - `.gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md`
  - `.gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md`
duration: 1 session
verification_result: passed
completed_at: 2026-03-22
---

# S01: SQL-Backed Overview Home + First Comparative Modules

**S01 retired the biggest M002 home-path scale risk: `/` is now a French market-overview surface driven by repository-owned SQL aggregates, with explicit honesty/freshness cues and first comparison modules, instead of the old M001 full-corpus proof screen.**

## What Happened

S01 replaced the old “load the whole scored corpus and assemble a dashboard in Python” posture on the default home route with a repository-owned SQL contract in `vinted_radar/repository.py`.

The new `overview_snapshot()` contract classifies tracked listings in SQL from the existing SQLite evidence boundary (`listings`, `listing_observations`, `catalog_scans`, `item_page_probes`) and returns:
- top-level inventory counts
- explicit honesty counts (observed / inferred / unknown basis, partial signal, thin signal, estimated-publication coverage, confidence mix)
- freshness and degradation cues (latest successful scan, latest runtime-cycle status, recent acquisition failures)
- first comparison modules for category, brand, price band, condition, and sold-state posture
- per-row support counts, sold-like mix, low-support flags, and drill-down lens values
- module-level `status` / `reason` for thin-support and empty states instead of silently hiding weak rows

To keep the SQL classifier from drifting away from the Python state machine, S01 promoted the relevant thresholds/confidence constants into shared `state_machine.py` constants and reused them from the repository SQL path.

On top of that contract, `vinted_radar/dashboard.py` now builds a new home payload that takes its primary market read from `overview_snapshot()` and its featured listing cards from `listing_explorer_page()`. The result is a French-first overview home that now emphasizes:
- tracked inventory, sold-like signal, confidence, and freshness cards
- explicit honesty notes for inferred states, unknowns, partial/thin signals, estimated publication timing, and recent acquisition failures
- comparison modules that remain visible even when support is fragile
- preserved drill-down paths into `/explorer`, `/api/dashboard`, `/api/runtime`, `/health`, and `/api/listings/<id>`

`/api/dashboard` was intentionally kept as the brownfield-compatible machine endpoint while `/` moved to the new overview semantics. That keeps diagnostics and future slice integration stable while still retiring the home-path recomputation risk.

The explorer seam is now SQL-paged and separate from the overview summary. Even in S01, that matters: the home no longer needs full-corpus score loading just to expose a few example listings or give the user a place to continue browsing.

## Verification

Slice-level verification passed in three layers:

1. **Contract / regression tests**
   - `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`
2. **Real local server boot**
   - `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765`
3. **Live route / UAT-style verification on the served app**
   - browser verification confirmed the French overview hero, comparison modules, explorer handoff, and no console/network errors on `/` and `/explorer`
   - direct HTTP checks confirmed `200` responses plus expected JSON structure for `/api/dashboard`, `/api/explorer`, `/api/runtime`, `/health`, and `/api/listings/9101`

Verified live payload facts from `data/vinted-radar-s01.db`:
- `/api/dashboard` reported **6 tracked listings**, **2 sold-like listings**, **3 high-confidence listings**, **1 inferred state**, **1 unknown state**, **1 recent acquisition failure**, and comparison modules for `category`, `brand`, `price_band`, `condition`, and `sold_state`
- `/health` reported `status: ok` and `tracked_listings: 6`
- `/api/runtime` reported the latest runtime cycle as `completed`
- `/api/listings/9101` resolved successfully with `state_code: active` and seller `alice`

## Observability / Diagnostics Confirmed

The slice plan explicitly called out observability surfaces, and they now work as intended:
- `/api/dashboard` exposes the exact overview payload behind `/`, including honesty notes and module support reasons
- `/api/explorer` exposes the SQL-paged listing browse payload
- `/api/runtime` exposes persisted runtime truth from SQLite
- `/health` exposes lightweight service/DB health plus latest runtime context
- `tests/test_overview_repository.py` and `tests/test_dashboard.py` now act as drift alarms for the SQL overview contract and the rendered home route

This is an important slice-level pattern: when the HTML changes, the corresponding JSON payload still gives a faster path to diagnose whether the regression lives in repository data, payload assembly, or rendering.

## Requirements Advanced

- **R007** — advanced. S01 shipped the first comparative modules and stable lens vocabulary for category, brand, price band, condition, and sold state, which S04 can now deepen instead of inventing from scratch.
- **R011** — advanced. The new overview makes inferred states, unknowns, partial/thin signals, estimated-publication gaps, low-support modules, and recent acquisition failures explicit instead of smoothing them away.
- **R012** — advanced. The product now has a real overview home plus a separate SQL-backed explorer seam, which is a meaningful step beyond the old mixed proof screen even though the deeper utility work still belongs to later slices.

## Requirements Validated

- **R004** — validated. S01 now visibly shows what is covered, when it was last seen/scanned, how confident the read is, and where support is weak or degraded, directly on the default home and matching JSON diagnostics.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The slice plan referenced `data/vinted-radar-s01.db` as the demo DB. That database was not originally part of the brownfield repo state, so the seeded local S01 DB had to be materialized and then used for live CLI/browser verification. That does not change the slice scope, but future local verification should assume the seeded demo DB may need recreation in a fresh checkout.

## Known Limitations

- The overview home is now French-first, but the explorer still uses brownfield English copy and layout language. The fully coherent French product shell remains later M002 work.
- The explorer currently executes server-side filters for root, catalog, brand, condition, search, sort, and paging. The comparison modules already emit price-band and sold-state lens values, but full explorer execution for those deeper lens filters is still future work in S04.
- `/api/listings/<id>` remains a drill-down seam and still uses the older detail-building path. S01 removed the primary-path risk on `/` and the browse path, not every downstream detail computation.
- S01 surfaces the latest persisted runtime status, but it does not yet solve the M002 pause/resume/scheduling truth gap. That is the core purpose of S02.

## Follow-ups

- S02 should align its richer runtime-truth surface with the summary/freshness vocabulary S01 established (`latest_successful_scan_at`, `latest_runtime_cycle_status`, recent failures, honesty language).
- S03 should treat the new overview/explorer split as the shell contract to productize responsively rather than collapsing back into a single mixed dashboard.
- S04 should complete the comparative story by wiring explorer execution for the remaining lens vocabulary (especially price band and sold state) and deepening server-side comparative workflows.
- S05 should retire the remaining detail-path legacy posture so the listing detail becomes as productized and provenance-explicit as the new home.

## Files Created/Modified

- `vinted_radar/repository.py` — added the SQL overview CTE/classification contract, comparison modules, explorer filter options, and SQL-paged explorer retrieval
- `vinted_radar/dashboard.py` — rebuilt `/` around the SQL overview payload, added French-first rendering, honesty notes, featured listing drill-down cards, and preserved JSON diagnostics
- `vinted_radar/cli.py` — updated dashboard command output to print the overview, explorer, runtime, and health routes
- `tests/test_overview_repository.py` — added repository-level coverage for summary counts, lens modules, low-support behavior, and honesty metadata
- `tests/test_dashboard.py` — added WSGI contract coverage for the overview home, explorer route, JSON diagnostics, and route semantics
- `tests/test_dashboard_cli.py` — updated CLI route-output expectations
- `README.md` — refreshed route and entrypoint documentation for the new overview/explorer posture
- `data/vinted-radar-s01.db` — seeded local demo DB used for live slice verification
- `.gsd/REQUIREMENTS.md` — refreshed requirement evidence/notes for R004 and R011
- `.gsd/DECISIONS.md` — captured the S01 overview compatibility decision set through D021 and D022
- `.gsd/KNOWLEDGE.md` — recorded the SQL-first overview-home pattern so later slices do not accidentally reintroduce the scored-home path
- `.gsd/PROJECT.md` — refreshed current project state to reflect M002/S01 completion

## Forward Intelligence

### What the next slice should know
- S01’s biggest output is not just the homepage itself; it is the **contract boundary**: `overview_snapshot()` is now the overview source of truth and should be extended, not bypassed.
- The home page and explorer are now separate responsibilities. Future shell or UX work should preserve that split unless there is a very strong reason to merge them again.
- Thin-support comparison rows are intentionally visible. If a later slice hides them for aesthetics, it will regress the slice’s honesty posture.

### What’s fragile
- The overview route is safe now, but later agents could accidentally reintroduce score-loading by sourcing featured cards or comparison facts from legacy helpers instead of repository SQL.
- Explorer support is still asymmetric relative to the comparison vocabulary: category/brand/condition drill-downs execute today; price-band and sold-state still need fuller downstream wiring.
- The detail endpoint is still a secondary legacy seam, so end-to-end scalability is improved but not fully retired across every route.

### Authoritative diagnostics
- `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`
- `http://127.0.0.1:8765/api/dashboard`
- `http://127.0.0.1:8765/api/explorer`
- `http://127.0.0.1:8765/api/runtime`
- `http://127.0.0.1:8765/health`

### What assumptions changed
- “The home route must stay coupled to full-corpus Python scoring.” — false. S01 proved the primary overview read can come straight from repository SQL.
- “Weak comparison rows should disappear until the support is stronger.” — false. S01 established that weak support should stay visible with explicit caution metadata.
- “The old `/api/dashboard` seam has to disappear if the home becomes a product surface.” — false. S01 kept the compatibility endpoint and improved the product route at the same time.
