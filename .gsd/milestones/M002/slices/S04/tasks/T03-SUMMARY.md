---
id: T03
parent: S04
milestone: M002
provides:
  - Deep-linkable overview → explorer → listing detail navigation with preserved explorer context and truthful back-to-results behavior
key_files:
  - vinted_radar/dashboard.py
  - vinted_radar/repository.py
  - tests/test_dashboard.py
  - .gsd/milestones/M002/slices/S04/S04-UAT.md
key_decisions:
  - Preserve the active analytical lens in query-string form so overview drill-downs, explorer comparison links, and listing detail all share one route contract.
patterns_established:
  - Explorer context should be rendered, not merely preserved invisibly, so detail pages explain why the user is looking at a listing.
observability_surfaces:
  - listing detail `explorer_context`, /api/listings/<id>, tests/test_dashboard.py, browser proof at the filtered explorer URL
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: Wire overview drill-down and context-preserving listing navigation

**Closed the analytical loop so overview and explorer drill-downs land in the right filtered slice, listing detail preserves that slice, and the user can return without losing context.**

## What Happened

I wired the explorer/detail flow through shared query helpers instead of route-local link building. Explorer listing links now preserve the active filter/query/sort/page-size lens, comparison rows hydrate their drill-down links against the current explorer state, and listing detail renders a visible `Contexte explorateur` section plus a `Retour aux résultats` action.

I also extended the detail payload to carry explorer-context diagnostics so the HTML and JSON routes reflect the same preserved analytical lens. Dashboard route tests now cover comparison-link preservation and detail back-link construction.

The final browser proof used the richer S04 demo DB to verify the real user loop: filtered explorer open, listing drill-down, context visible on detail, then return to the same explorer URL.

## Verification

Targeted explorer-transition route tests passed, and browser verification confirmed the round-trip flow on the live local server against the S04 demo DB.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py -k explorer` | 0 | PASS | 0.36s |
| 2 | Browser verification at `http://127.0.0.1:8783/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12` | n/a | PASS | interactive |

## Diagnostics

Use `/api/listings/<id>` to inspect the serialized `explorer_context`, and `tests/test_dashboard.py` to see the expected route/query preservation behavior. The authoritative live proof path is documented in `.gsd/milestones/M002/slices/S04/S04-UAT.md`.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/dashboard.py` — preserved explorer query state in detail/API links, added explorer-context rendering on detail, and hydrated comparison drill-down links.
- `vinted_radar/repository.py` — supported the richer explorer/detail contract consumed by navigation and comparison drill-downs.
- `tests/test_dashboard.py` — added transition coverage for explorer comparison links and detail back-link payloads.
- `.gsd/milestones/M002/slices/S04/S04-UAT.md` — documented the real explorer → detail → return proof flow for future verification.
