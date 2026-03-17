# S01: Public Discovery + Normalized Ingestion

**Goal:** Prove that public Vinted Homme/Femme discovery is technically viable without login and land a local-first batch ingestion backbone that stores canonical listing identities, first observations, targeted raw evidence, and honest coverage artifacts.
**Demo:** Running `python -m vinted_radar.cli discover --root men --root women --max-pages-per-catalog 2 --item-details sample --db-path data/radar.db --artifacts-dir artifacts/s01-smoke` creates a SQLite database plus a coverage artifact showing which catalog IDs/pages were scanned, how many unique listings were observed, what errors or stop reasons occurred, and sample item-detail evidence fragments.

This plan is ordered risk-first: bootstrap the blank repo into a testable Python collector, prove the fragile SSR HTML extraction seam with fixtures, then wire real Men/Women tree discovery and finally compose the live batch CLI. That sequencing directly advances **R001** (public discovery), supports **R010** (local batch entrypoint as the first step toward runtime modes), and supports **R011** (null-tolerant normalization, explicit error accounting, and inspectable evidence instead of silent failure).

## Must-Haves

- A local batch command discovers Vinted Men (`catalog/5`) and Women (`catalog/1904`) roots plus reachable sub-categories from public HTML without login, canonicalizing categories by numeric catalog ID rather than slug text.
- The run persists S02-ready data boundaries: catalog registry, canonical listing identities, append-only observations with `observed_at`, targeted raw evidence fragments, and null-tolerant normalized fields that keep observed values separate from missing data.
- The slice leaves honest inspection surfaces behind: automated extractor/discovery tests, a smoke verifier, SQLite run/coverage tables, and `coverage.json` summarizing scanned catalogs/pages, unique listings, duplicates, errors, timestamps, and stop reasons.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `python -m pytest tests/test_repository.py tests/test_flight_extract.py tests/test_catalog_tree.py tests/test_discovery_normalization.py tests/test_cli_discover_smoke.py`
- `python -m vinted_radar.cli discover --root men --root women --max-pages-per-catalog 2 --item-details sample --db-path data/radar.db --artifacts-dir artifacts/s01-smoke`
- `python scripts/verify_s01_smoke.py --db-path data/radar.db --coverage artifacts/s01-smoke/coverage.json --expect-root 5 --expect-root 1904`

## Observability / Diagnostics

- Runtime signals: `discovery_runs` and `scan_coverage` rows, per-catalog/page counters, extractor version, raw evidence fragment metadata, and `coverage.json` written for each smoke run.
- Inspection surfaces: `python -m vinted_radar.cli discover ...`, SQLite tables (`catalog_nodes`, `listing_identities`, `listing_observations`, `raw_evidence_fragments`, `scan_coverage`, `discovery_runs`), and `artifacts/<run>/coverage.json`.
- Failure visibility: persisted run status, phase-specific errors, duplicate counts, stop reasons, timestamps, and extractor diagnostics showing which fragment/catalog/page failed.
- Redaction constraints: persist only public catalog/listing content and targeted evidence fragments; never store cookies, auth headers, or full-page archives by default.

## Integration Closure

- Upstream surfaces consumed: `.gsd/milestones/M001/M001-ROADMAP.md`, `.gsd/milestones/M001/slices/S01/S01-RESEARCH.md`, `.gsd/REQUIREMENTS.md` (`R001`, `R010`, `R011`), and `.gsd/DECISIONS.md` (`D002`, `D003`, `D010`).
- New wiring introduced in this slice: Python package bootstrap, Typer `discover` CLI, HTTP HTML collector, SSR fragment extractor, SQLite repository, coverage artifact writer, and smoke verification script.
- What remains before the milestone is truly usable end-to-end: S02 revisit/history persistence and freshness, S03 cautious states/confidence, S04 scoring, S05 dashboard, and S06 continuous runtime composition.

## Tasks

- [x] **T01: Bootstrap the Python collector contracts and pytest harness** `est:1h15m`
  - Why: The repo is still a blank slate. S01 needs a concrete runtime stack, storage contract, and test runner before discovery logic can be implemented safely or handed to later slices.
  - Files: `pyproject.toml`, `.gitignore`, `src/vinted_radar/config.py`, `src/vinted_radar/models.py`, `src/vinted_radar/storage/db.py`, `src/vinted_radar/storage/repository.py`, `tests/conftest.py`, `tests/test_repository.py`
  - Do: Create the Python package and dependencies (`httpx`, `beautifulsoup4`, `typer`, `pytest`), add runtime/test ignores for local state, define typed models for catalogs/listings/observations/raw evidence/coverage, and bootstrap SQLite tables that keep observations append-only and raw evidence separate. The schema must allow nullable public fields, record `extractor_version`, and be ready for later revisit history instead of a one-row-per-listing shortcut.
  - Verify: `python -m pytest tests/test_repository.py`
  - Done when: The repository bootstraps a SQLite DB with the required S01 tables, repository tests pass, and the base package/tooling exist for subsequent tasks without relying on ad hoc scripts.
- [ ] **T02: Implement fixture-backed SSR fragment extraction for catalog and item pages** `est:1h30m`
  - Why: The highest technical risk is extracting useful data from `self.__next_f.push(...)` HTML payloads without overbuilding a full React Flight decoder.
  - Files: `src/vinted_radar/vinted/flight_extract.py`, `tests/fixtures/vinted/catalog-men.html`, `tests/fixtures/vinted/catalog-leaf.html`, `tests/fixtures/vinted/item-sample.html`, `tests/test_flight_extract.py`
  - Do: Save representative live catalog/item HTML fixtures, implement narrow extraction helpers for catalog `items`/`pagination` plus item-side `item`, `breadcrumbs`, `attributes`, and `favourite` fragments, and surface actionable parser diagnostics when fragments are absent or malformed. Optional fragments must return `None` cleanly rather than crashing the run.
  - Verify: `python -m pytest tests/test_flight_extract.py`
  - Done when: Fixture tests prove that catalog and item HTML can be decoded into structured fragments, and extractor failures are explicit enough to debug when Vinted markup shifts.
- [ ] **T03: Discover catalog trees and normalize paginated listing stubs with coverage accounting** `est:2h`
  - Why: This task closes the core R001 discovery proof by walking Men/Women roots, normalizing listing stubs from catalog pages, and reporting exactly what was or was not scanned.
  - Files: `src/vinted_radar/vinted/catalog_tree.py`, `src/vinted_radar/vinted/discovery.py`, `src/vinted_radar/vinted/normalize.py`, `tests/test_catalog_tree.py`, `tests/test_discovery_normalization.py`
  - Do: Implement BeautifulSoup-based category link discovery from the Men (`5`) and Women (`1904`) roots, canonicalize categories by numeric catalog ID across mixed-language slugs, paginate from first-page metadata only, normalize catalog listing stubs into identity/observation-ready records with explicit nulls, and track pages scanned, duplicates, errors, and stop reasons per catalog. Keep observed currency codes exactly as fetched.
  - Verify: `python -m pytest tests/test_catalog_tree.py tests/test_discovery_normalization.py`
  - Done when: Tests prove correct catalog ID parsing, parent/root relationships, bounded pagination, null-tolerant normalization, and honest coverage counters for duplicate/error/stop conditions.
- [ ] **T04: Wire item-detail enrichment, SQLite persistence, and the real discover CLI smoke path** `est:2h`
  - Why: S01 is only truly complete when a local operator can run one batch command that discovers, enriches, persists, and leaves inspectable artifacts behind for later slices.
  - Files: `src/vinted_radar/vinted/item_detail.py`, `src/vinted_radar/runtime/discover_run.py`, `src/vinted_radar/cli.py`, `tests/test_cli_discover_smoke.py`, `scripts/verify_s01_smoke.py`, `artifacts/s01-smoke/coverage.json`
  - Do: Compose the HTTP collector, extractor, catalog discovery, item-detail enrichment, and SQLite repository into a Typer `discover` command supporting `--root`, `--max-pages-per-catalog`, `--db-path`, `--artifacts-dir`, and `--item-details (none|sample|all)`. Persist catalog nodes, listing identities, observations, raw evidence fragments, coverage rows, and per-run status; emit `coverage.json`; add a mocked CLI smoke test plus a real-run verification script that asserts roots `5` and `1904`, non-zero persisted data, and required coverage fields.
  - Verify: `python -m pytest tests/test_cli_discover_smoke.py && python -m vinted_radar.cli discover --root men --root women --max-pages-per-catalog 2 --item-details sample --db-path data/radar.db --artifacts-dir artifacts/s01-smoke && python scripts/verify_s01_smoke.py --db-path data/radar.db --coverage artifacts/s01-smoke/coverage.json --expect-root 5 --expect-root 1904`
  - Done when: The batch command runs end-to-end against a limited live budget, leaves durable DB/artifact proof, and the verifier passes without manual inspection.

## Files Likely Touched

- `pyproject.toml`
- `.gitignore`
- `src/vinted_radar/config.py`
- `src/vinted_radar/models.py`
- `src/vinted_radar/storage/db.py`
- `src/vinted_radar/storage/repository.py`
- `src/vinted_radar/vinted/flight_extract.py`
- `src/vinted_radar/vinted/catalog_tree.py`
- `src/vinted_radar/vinted/discovery.py`
- `src/vinted_radar/vinted/item_detail.py`
- `src/vinted_radar/runtime/discover_run.py`
- `src/vinted_radar/cli.py`
- `tests/test_repository.py`
- `tests/test_flight_extract.py`
- `tests/test_catalog_tree.py`
- `tests/test_discovery_normalization.py`
- `tests/test_cli_discover_smoke.py`
- `scripts/verify_s01_smoke.py`
