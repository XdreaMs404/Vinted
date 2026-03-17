---
id: S02
parent: M001
milestone: M001
provides:
  - Per-run normalized listing history in `listing_observations`
  - CLI freshness, revisit-plan, and listing history inspection surfaces
  - Forward migration from S01 discovery-only SQLite databases
requires:
  - slice: S01
    provides: Public seed sync, normalized listings, discovery diagnostics, and the batch `discover` entrypoint
affects:
  - S03
  - S04
  - S06
key_files:
  - vinted_radar/db.py
  - vinted_radar/repository.py
  - vinted_radar/services/discovery.py
  - vinted_radar/cli.py
  - tests/test_history_repository.py
  - tests/test_history_cli.py
key_decisions:
  - D011
  - D012
patterns_established:
  - `listing_observations` holds one row per listing per run for cadence/freshness queries.
  - `listing_discoveries` remains the lower-level per-sighting evidence surface.
observability_surfaces:
  - `python -m vinted_radar.cli freshness --db <path>`
  - `python -m vinted_radar.cli revisit-plan --db <path> --limit <n>`
  - `python -m vinted_radar.cli history --db <path> --listing-id <id>`
  - SQLite tables: `listing_observations`, `listing_discoveries`, `catalog_scans`
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T01-PLAN.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-17
---

# S02: Intelligent Revisits + Observation History

**Per-run listing history, freshness buckets, and revisit planning surfaces built on repeated batch runs against the same SQLite database.**

## What Happened

S02 turned repeated `discover` runs into durable listing history rather than just more overwritten listing rows. The data model now stores one normalized observation per listing per run in `listing_observations`, while preserving the existing `listing_discoveries` rows as the lower-level page/category diagnostic surface.

The SQLite bootstrap path now performs forward migration for S01 databases by creating the new history table and backfilling it from legacy discovery rows. Discovery runs persist both detailed discoveries and aggregated per-run observations, which makes first seen, last seen, observation count, average revisit gap, freshness buckets, and ranked revisit candidates cheap to query.

The CLI surface was extended with `freshness`, `revisit-plan`, and `history` commands. Fixture tests prove repeated-run history and migration behavior, and a live two-run smoke DB confirmed that real public data now produces repeated observations, fresh-followup listings, first-pass-only listings, and per-listing timelines. Live verification also exposed a terminal-encoding bug on Unicode titles; the CLI now sanitizes display output instead of crashing while keeping JSON output lossless.

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli discover --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0`
- `python -m vinted_radar.cli discover --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0`
- `python -m vinted_radar.cli freshness --db data/vinted-radar-s02.db`
- `python -m vinted_radar.cli revisit-plan --db data/vinted-radar-s02.db --limit 5`
- `python -m vinted_radar.cli history --db data/vinted-radar-s02.db --listing-id 4176710128`

## Requirements Advanced

- R002 — repeated batch runs now preserve first seen, last seen, observation count, cadence, and timeline history for listings.
- R010 — the local batch mode now produces durable temporal history when rerun against the same database.
- R011 — migration and history inspection keep legacy data usable instead of silently dropping it.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The original live proof only planned `freshness` and `revisit-plan`, but a real history lookup command was also shipped because S02 needed a truthful listing-level drill-down rather than only aggregate surfaces.

## Known Limitations

History is still driven by repeated batch collection; there is no continuous scheduler yet, and cadence reflects when the collector was run, not a managed revisit policy. There is still no state machine, no scoring, and no UI layer beyond the CLI.

## Follow-ups

- Build S03 directly on `listing_observations` and freshness buckets instead of recomputing history from raw discoveries.
- Decide how state inference should treat listings that remain first-pass-only versus fresh-followup versus stale-followup.
- Revisit the ranking formula in `revisit-plan` if continuous scheduling introduces stronger operational priorities.

## Files Created/Modified

- `vinted_radar/card_payload.py` — reusable normalization fallback for raw card payloads.
- `vinted_radar/db.py` — new history table plus forward migration/backfill logic.
- `vinted_radar/repository.py` — history, freshness, revisit planning, and timeline queries.
- `vinted_radar/services/discovery.py` — per-run observation persistence during discovery.
- `vinted_radar/cli.py` — history/freshness/revisit commands and safe terminal output.
- `tests/fixtures/catalog-page-women-run2.html` — second-run fixture for repeated history tests.
- `tests/test_history_repository.py` — repository and migration coverage.
- `tests/test_history_cli.py` — CLI JSON surface coverage.
- `README.md` — updated local entrypoints.

## Forward Intelligence

### What the next slice should know
- `listing_observations` is the correct truth surface for per-listing temporal reasoning; `listing_discoveries` is still valuable, but it is the debug layer, not the primary history model.
- First-pass-only listings are already explicit in freshness output, which gives S03 a clean place to express uncertainty without inventing more data than the collector actually saw.
- JSON output remains the most faithful inspection surface; table output is intentionally sanitized for terminal compatibility.

### What's fragile
- The backfill migration can only infer normalized historical fields from the S01 data that survived; truly old per-run field differences may be unavailable when they were never stored separately.
- CLI priority scoring in `revisit-plan` is heuristic and should not be mistaken for product-level demand logic.

### Authoritative diagnostics
- `python -m vinted_radar.cli freshness --db <path>` — fastest summary of whether repeated runs are actually producing follow-up history.
- `python -m vinted_radar.cli history --db <path> --listing-id <id>` — canonical listing-level temporal proof.
- SQLite `listing_observations` — authoritative one-row-per-listing-per-run history store.

### What assumptions changed
- "CLI display is a thin problem once the data model is correct." — false on live data; real public titles can break terminal output unless the display boundary is hardened.
