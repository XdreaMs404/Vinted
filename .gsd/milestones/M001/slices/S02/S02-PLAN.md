# S02: Intelligent Revisits + Observation History

**Goal:** Turn repeated batch runs into durable listing history by preserving per-observation snapshots, exposing first/last seen plus revisit cadence, and surfacing freshness and revisit priorities from the persisted SQLite data.
**Demo:** Run the collector twice against the same SQLite database, then inspect `python -m vinted_radar.cli freshness --db data/vinted-radar.db`, `python -m vinted_radar.cli revisit-plan --db data/vinted-radar.db --limit 5`, and `python -m vinted_radar.cli history --db data/vinted-radar.db --listing-id <revisited-id>` to see repeated observations, cadence, and freshness.

## Must-Haves

- Preserve multiple timestamped normalized observations per listing without losing the card-level raw evidence already shipped in S01.
- Expose per-listing first seen, last seen, observation count, and revisit cadence from persisted history rather than only the last-write-wins listing row.
- Provide freshness and revisit-priority surfaces that future slices can build on for state inference and scheduling.
- Migrate the existing SQLite database forward cleanly so S01 data remains usable.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli discover --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0`
- `python -m vinted_radar.cli discover --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0`
- `python -m vinted_radar.cli freshness --db data/vinted-radar-s02.db`
- `python -m vinted_radar.cli revisit-plan --db data/vinted-radar-s02.db --limit 5`

## Observability / Diagnostics

- Runtime signals: persisted normalized listing observations, per-listing history summaries, freshness buckets, and revisit candidate scores.
- Inspection surfaces: `python -m vinted_radar.cli freshness`, `python -m vinted_radar.cli revisit-plan`, `python -m vinted_radar.cli history --listing-id <id>`, plus SQLite tables `listing_observations` and the existing `listing_discoveries` / `catalog_scans` tables.
- Failure visibility: migration failures, empty history state, and listings that have only a single observation remain explicit instead of being collapsed into the current listing row.
- Redaction constraints: continue storing only public listing-card evidence fragments and normalized public fields.

## Integration Closure

- Upstream surfaces consumed: S01 SQLite schema, `discover` batch workflow, parser outputs, and listing/card evidence payloads.
- New wiring introduced in this slice: discovery run → per-observation persistence → history/freshness/revisit summary queries → CLI inspection commands.
- What remains before the milestone is truly usable end-to-end: state inference, score calculation, dashboard surfaces, and continuous runtime.

## Tasks

- [x] **T01: Extend persistence for observation history and migrations** `est:1h`
  - Why: S02 needs a durable per-observation model and must preserve S01 data instead of forcing a fresh database.
  - Files: `vinted_radar/db.py`, `vinted_radar/repository.py`, `tests/test_history_repository.py`
  - Do: Add the normalized observation storage and forward-only schema migration path, keep existing discovery diagnostics intact, and expose repository queries for listing history, freshness, and revisit candidates.
  - Verify: `python -m pytest tests/test_history_repository.py`
  - Done when: existing databases migrate cleanly and repeated observations can be queried into per-listing history summaries.
- [x] **T02: Record repeated observations and expose history/freshness CLI surfaces** `est:1h15m`
  - Why: The slice only becomes real when repeated `discover` runs produce inspectable history and revisit planning outputs through the actual entrypoint.
  - Files: `vinted_radar/services/discovery.py`, `vinted_radar/cli.py`, `tests/test_history_cli.py`
  - Do: Persist normalized observation rows during discovery, add freshness / revisit-plan / history CLI commands, and make the outputs explicit about observation count, freshness bucket, and cadence.
  - Verify: `python -m pytest tests/test_history_cli.py`
  - Done when: the CLI can show a listing timeline, aggregate freshness, and ranked revisit candidates from a database with repeated runs.
- [x] **T03: Verify multi-run history against fixture and live data** `est:1h`
  - Why: S02 depends on repeated runs over the same database, so it needs both deterministic tests and a real two-run smoke check.
  - Files: `tests/test_discovery_service.py`, `README.md`, `.gsd/milestones/M001/slices/S02/tasks/T01-PLAN.md`
  - Do: Add repeated-run integration coverage, document the history/freshness entrypoints, and verify the real CLI flow with two runs against the same SQLite file.
  - Verify: `python -m pytest` and the S02 live verification commands from this plan.
  - Done when: repeated runs demonstrably change history/freshness surfaces in both tests and a real local DB.

## Files Likely Touched

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/cli.py`
- `tests/test_history_repository.py`
- `tests/test_history_cli.py`
- `tests/test_discovery_service.py`
- `README.md`
