# S01: Public Discovery + Normalized Ingestion

**Goal:** Build a first real batch discovery slice that syncs the public Homme/Femme catalog tree, scans public catalog pages, persists normalized listing card data plus targeted raw evidence fragments in SQLite, and reports what coverage was actually observed.
**Demo:** A local user runs `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6` and then `python -m vinted_radar.cli coverage --db data/vinted-radar.db` to inspect the observed Homme/Femme footprint and discovered listings.

## Must-Haves

- Discover the reachable Homme/Femme catalog tree from public HTML and persist the seed registry locally.
- Parse server-rendered listing cards into normalized records with listing ID, canonical URL, pricing, brand/size/condition when present, image, source catalog, `observed_at`, and raw evidence fragments.
- Persist scan/run metadata so coverage, success/failure, and scan footprint remain inspectable after the batch run ends.
- Provide a real CLI batch entrypoint and a coverage/reporting command that future slices can build on.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --request-delay 0.0`
- `python -m vinted_radar.cli coverage --db data/vinted-radar.db`

## Observability / Diagnostics

- Runtime signals: persisted discovery runs, per-catalog scan rows, raw listing discovery sightings, and stored parse evidence fragments.
- Inspection surfaces: `python -m vinted_radar.cli coverage`, SQLite tables (`discovery_runs`, `catalog_scans`, `listing_discoveries`, `listings`, `catalogs`), and CLI summaries printed at batch completion.
- Failure visibility: run status, last error, per-catalog request failure, response status, and zero-item scans remain queryable after execution.
- Redaction constraints: do not store secrets; raw evidence is limited to public card-level fragments rather than full-page archives by default.

## Integration Closure

- Upstream surfaces consumed: public HTML from `https://www.vinted.fr/catalog` and public catalog pages under `/catalog/<id>-...`.
- New wiring introduced in this slice: Typer CLI → public HTTP client → HTML parsers → SQLite repository → coverage reporting.
- What remains before the milestone is truly usable end-to-end: revisits/history, cautious state logic, scoring, dashboard, and continuous mode.

## Tasks

- [ ] **T01: Bootstrap discovery package and verification harness** `est:45m`
  - Why: The repo is empty; S01 needs a runnable Python package, a stable CLI entrypoint, SQLite initialization, and tests before the collector logic lands.
  - Files: `pyproject.toml`, `src/vinted_radar/cli.py`, `src/vinted_radar/db.py`, `tests/test_cli_smoke.py`
  - Do: Create the package layout, define the SQLite schema/bootstrap path, expose a Typer CLI with placeholder `discover` and `coverage` commands wired to the database, and add the first tests so the slice has executable verification from the start.
  - Verify: `python -m pytest tests/test_cli_smoke.py`
  - Done when: the package installs/runs locally, the schema is created on demand, and the smoke tests pass.
- [ ] **T02: Parse public catalog tree and listing cards from SSR HTML** `est:1h15m`
  - Why: The collector depends on extracting both the Homme/Femme catalog graph and listing card data from public HTML without JS execution.
  - Files: `src/vinted_radar/parsers/catalog_tree.py`, `src/vinted_radar/parsers/catalog_page.py`, `tests/fixtures/catalog-root.html`, `tests/fixtures/catalog-page.html`, `tests/test_parsers.py`
  - Do: Implement resilient parsers for the embedded catalog tree and visible catalog cards, normalize the fields needed by S01, and preserve the raw card fragments required for traceability.
  - Verify: `python -m pytest tests/test_parsers.py`
  - Done when: fixtures prove that Femme/Homme trees and listing cards are parsed into stable domain objects with the expected normalized fields.
- [ ] **T03: Wire batch discovery, persistence, and coverage reporting** `est:1h30m`
  - Why: S01 is only real once a live batch run can fetch public pages, persist results, and report the observed footprint rather than just parse fixtures.
  - Files: `src/vinted_radar/http.py`, `src/vinted_radar/services/discovery.py`, `src/vinted_radar/repository.py`, `tests/test_discovery_service.py`
  - Do: Implement the HTTP client, seed syncing, batch scan orchestration, per-run metrics, listing upserts, coverage queries, and CLI summaries with graceful request/parse failure capture.
  - Verify: `python -m pytest` and `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --request-delay 0.0`
  - Done when: a live discovery run completes, coverage surfaces are queryable, and the run records both successful scans and failures in persisted state.

## Files Likely Touched

- `pyproject.toml`
- `vinted_radar/cli.py`
- `vinted_radar/db.py`
- `vinted_radar/http.py`
- `vinted_radar/repository.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/parsers/catalog_tree.py`
- `vinted_radar/parsers/catalog_page.py`
- `tests/test_cli_smoke.py`
- `tests/test_parsers.py`
- `tests/test_discovery_service.py`
rsers.py`
- `tests/test_discovery_service.py`
