---
id: S04
parent: M002
milestone: M002
provides:
  - A SQL-first explorer workspace with scoped comparisons, honest support cues, and context-preserving listing navigation
requires:
  - slice: S01
    provides: SQL overview/repository seams and first drill-down compatibility paths
  - slice: S03
    provides: shared French shell, route context, and responsive serving contract
affects:
  - S05
  - S06
  - S07
key_files:
  - vinted_radar/repository.py
  - vinted_radar/dashboard.py
  - vinted_radar/db.py
  - tests/test_explorer_repository.py
  - tests/test_dashboard.py
key_decisions:
  - Keep S04 on one repository-owned classified explorer snapshot that feeds filters, paging, comparison modules, and detail-navigation context.
patterns_established:
  - Preserve the active analytical lens through shared `ExplorerFilters`/query helpers across overview, explorer, and detail instead of building route-local hrefs.
observability_surfaces:
  - /explorer, /api/explorer, /api/listings/<id>, tests/test_explorer_repository.py, tests/test_dashboard.py, .gsd/milestones/M002/slices/S04/S04-UAT.md
drill_down_paths:
  - .gsd/milestones/M002/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T03-SUMMARY.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
---

# S04: Full Explorer + Comparative Intelligence

**Turned `/explorer` into the main SQL-backed browse-and-compare workspace, then closed the overview/explorer/detail loop with preserved analytical context and real-browser proof on a richer demo DB.**

## What Happened

S04 replaced the old thin explorer seam with a repository-owned classified snapshot that can answer the real browsing questions directly: root/catalog/brand/condition/state/price-band/search filters, sorting, paging, result summaries, and comparison modules with explicit support counts and honesty metadata.

On top of that contract, the explorer UI was rebuilt into a filter-first browsing workspace that shows active filter state, result totals, support-aware comparison panels, and paged listing cards instead of relying on a wide debug table as the primary interaction model. The README now documents the public explorer workflow and supported query parameters.

The slice then wired the main analytical loop: overview/explorer drill-downs target the shared explorer contract, listing detail preserves the active explorer lens in both HTML and JSON form, and the user can return to the same filtered result set. During real-browser proof on a richer historical DB, verification exposed a genuine legacy SQLite bootstrap bug; that was fixed by migrating late-added listing metadata columns before creating dependent indexes, and a dedicated regression now guards that path.

## Verification

The slice passed both targeted and full automated coverage plus a live browser proof on the S04 demo DB.

## Requirements Advanced

- R011 — explorer comparisons and result summaries now keep thin-support and partial-signal caveats visible inside the primary browse flow instead of relying on diagnostics alone.
- R012 — the product now offers a real browse-and-compare explorer workflow with scoped filters, comparisons, and context-preserving drill-down beyond the overview-only market read.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

Slice proof on `data/vinted-radar-s04.db` exposed a legacy schema-bootstrap fault (`created_at_ts` missing before dependent indexes were created). Fixing `vinted_radar/db.py` was not spelled out in the written slice plan, but it was required to make the promised real-DB explorer/browser proof truthful.

## Known Limitations

- S05 still needs a more narrative, progressive-detail reading surface; listing detail is now context-preserving, but not yet narrative-first.
- S06 still needs degraded acquisition and challenge-aware truth to flow through explorer/detail surfaces, not just the underlying runtime data.
- S07 still needs mounted/VPS acceptance for the richer S04 explorer workflow rather than only the S03 shell contract.

## Follow-ups

- Use the shared explorer-context helpers when S05 deepens listing detail so the new narrative panels do not break return-to-results behavior.
- Reuse the S04 legacy-DB bootstrap regression whenever future schema changes add columns with dependent indexes.
- Add mounted-prefix/browser proof for the richer explorer filters and detail round-trip during S07 serving acceptance.

## Files Created/Modified

- `vinted_radar/repository.py` — expanded the SQL explorer snapshot, summaries, filter options, and comparison modules.
- `vinted_radar/dashboard.py` — rebuilt explorer rendering and preserved analytical context across overview, explorer, and detail.
- `vinted_radar/db.py` — moved dependent listing indexes to a post-migration bootstrap step for historical DB compatibility.
- `README.md` — documented the richer explorer workflow and public query contract.
- `tests/test_explorer_repository.py` — added dedicated explorer contract regressions.
- `tests/test_dashboard.py` — added richer explorer and context-preserving navigation coverage.
- `.gsd/milestones/M002/slices/S04/S04-UAT.md` — recorded the browser-backed explorer/detail UAT flow.

## Forward Intelligence

### What the next slice should know
- The explorer/detail loop is now query-contract-driven; extending filters or adding detail modules should go through the shared explorer helpers instead of custom route-local href building.

### What's fragile
- Historical SQLite snapshots with older schemas — they now open correctly again, but any future column+index change can reintroduce bootstrap breakage if migrations and dependent indexes are not ordered carefully.

### Authoritative diagnostics
- `tests/test_dashboard.py` plus the filtered-browser proof URL in `S04-UAT.md` — together they catch both query-state drift and real rendered-flow regressions.

### What assumptions changed
- "Fixture-backed route tests are enough to prove the explorer slice" — the richer S04 browser proof DB exposed a real legacy-schema bootstrap fault that the fixtures did not catch, so real proof DB opening is part of the slice truth now.
