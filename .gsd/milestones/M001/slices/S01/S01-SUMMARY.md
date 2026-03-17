---
id: S01
parent: M001
milestone: M001
provides:
  - Public Homme/Femme seed sync from the embedded `/catalog` tree
  - SQLite-backed normalized listing ingestion with card-level raw evidence fragments
  - Batch CLI coverage reporting over persisted runs, scans, listings, and sightings
requires: []
affects:
  - S02
  - S06
key_files:
  - pyproject.toml
  - vinted_radar/cli.py
  - vinted_radar/parsers/catalog_tree.py
  - vinted_radar/parsers/catalog_page.py
  - vinted_radar/repository.py
  - vinted_radar/services/discovery.py
key_decisions:
  - D010
  - D011
patterns_established:
  - Public acquisition stays browserless while `/catalog` keeps exposing `catalogTree` and SSR item cards.
  - Coverage and failures are first-class persisted runtime surfaces, not transient console output.
observability_surfaces:
  - `python -m vinted_radar.cli coverage --db <path>`
  - SQLite tables: `discovery_runs`, `catalog_scans`, `listings`, `listing_discoveries`, `catalogs`
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-17
---

# S01: Public Discovery + Normalized Ingestion

**SQLite-backed batch discovery CLI that syncs the public Homme/Femme catalog tree, ingests SSR listing cards, and reports observed coverage from live runs.**

## What Happened

The repository moved from planning-only bootstrap into a real runnable collector slice. The shipped Python package exposes a Typer CLI, initializes a SQLite schema on demand, and keeps discovery runs, per-catalog scans, normalized listings, and listing sightings queryable after execution.

For seed discovery, the collector parses the embedded `catalogTree` flight payload already present in the public `/catalog` HTML and persists the full Homme/Femme catalog graph locally. For listing ingestion, it reads server-rendered `new-item-box__container` cards from public catalog pages, normalizes listing identity, brand, size, condition, prices, image, and canonical URL, and stores targeted raw card fragments rather than full-page archives.

The batch flow was wired end to end with graceful request/parse failure capture. A live verification run scanned six leaf categories with zero failures, persisted 576 sightings / 576 unique listing IDs, and produced root-level coverage output for both Femmes and Hommes.

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --request-delay 0.0`
- `python -m vinted_radar.cli coverage --db data/vinted-radar.db`

## Requirements Advanced

- R001 — Public Homme/Femme discovery now exists as a live batch collector with full seed sync and persisted coverage reporting.
- R011 — Missing or failing catalog requests now degrade into persisted scan failures instead of collapsing the run silently.
- R010 — The first local batch runtime entrypoint exists and exercises the real acquisition path.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The implementation used a flat `vinted_radar/` package instead of the initially sketched `src/vinted_radar/` layout so `python -m vinted_radar.cli ...` works from the repo root without an install step.

## Known Limitations

Revisit scheduling, historical observation evolution, state inference, scoring, dashboard surfaces, and continuous mode do not exist yet. The batch collector can sync the full seed registry every run, but smoke verification still relies on `--max-leaf-categories` to keep live checks fast.

## Follow-ups

- Plan S02 on top of the existing SQLite schema instead of replacing it.
- Extend listing sightings into durable multi-observation history with first/last seen and freshness surfaces.
- Decide whether full sweeps should remain sequential or move to a paced concurrent model once multi-day runtime begins.

## Files Created/Modified

- `pyproject.toml` — package metadata and test config.
- `README.md` — current local entrypoints.
- `vinted_radar/cli.py` — discovery and coverage commands.
- `vinted_radar/db.py` — SQLite schema bootstrap.
- `vinted_radar/parsers/catalog_tree.py` — embedded catalog tree extraction.
- `vinted_radar/parsers/catalog_page.py` — SSR listing card parsing.
- `vinted_radar/repository.py` — persistence and coverage queries.
- `vinted_radar/services/discovery.py` — batch orchestration.
- `tests/test_cli_smoke.py` — empty-state CLI proof.
- `tests/test_parsers.py` — parser contract coverage.
- `tests/test_discovery_service.py` — persistence / failure-path integration coverage.

## Forward Intelligence

### What the next slice should know
- `/catalog` currently exposes the full Homme/Femme tree in `self.__next_f.push(...)`, which makes seed sync cheap and broad without browser automation.
- Listing-card level evidence is enough for S01, but S02 should treat `listing_discoveries` as the bridge into a richer observation model rather than bolting on a parallel history table with duplicated semantics.
- The persisted failure surface is already useful: `catalog_scans.error_message`, `response_status`, and `discovery_runs.last_error` tell you quickly whether the break is network, parse, or selection logic.

### What's fragile
- `catalogTree` extraction depends on the current escaped payload shape in the Next flight script — if Vinted materially changes the embedding, seed sync is the first place to look.
- Listing parsing depends on `new-item-box__container` and related `data-testid`/summary fragments — these selectors are public but still UI-coupled.

### Authoritative diagnostics
- `python -m vinted_radar.cli coverage --db data/vinted-radar.db` — fastest truthful summary of the last persisted run.
- SQLite `catalog_scans` rows — canonical record of what was requested, what failed, and how many listings were seen per page.

### What assumptions changed
- "We may need browser automation to get enough public seed structure." — false for now; the public `/catalog` HTML already carries the necessary tree and listing-card surfaces.
