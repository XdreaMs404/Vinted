---
id: T01
parent: S01
milestone: M001
provides:
  - Python package bootstrap with SQLite collector contracts and a pytest repository harness
key_files:
  - pyproject.toml
  - src/vinted_radar/config.py
  - src/vinted_radar/models.py
  - src/vinted_radar/storage/db.py
  - src/vinted_radar/storage/repository.py
  - tests/test_repository.py
key_decisions:
  - Kept `listing_observations` append-only and stored `raw_evidence_fragments` separately so observed facts stay distinct from retained evidence.
patterns_established:
  - `Repository` bootstraps the SQLite schema on open and exposes explicit upsert/append methods for catalogs, runs, identities, observations, evidence, and coverage.
observability_surfaces:
  - SQLite tables `discovery_runs`, `scan_coverage`, `listing_observations`, and `raw_evidence_fragments`, plus `tests/test_repository.py` and `data/_verify_t01.db`
duration: 1h20m
verification_result: passed
completed_at: 2026-03-17T16:25:00+01:00
blocker_discovered: false
---

# T01: Bootstrap the Python collector contracts and pytest harness

**Bootstrapped the `vinted_radar` Python package with SQLite storage contracts, null-tolerant models, and passing repository tests.**

## What Happened

I created `pyproject.toml` with the S01 Python stack (`httpx`, `beautifulsoup4`, `typer`, `pytest`) plus Ruff/pytest configuration and added runtime ignores for `data/`, `artifacts/`, `.pytest_cache/`, and `.ruff_cache/`.

I added `src/vinted_radar/config.py` for the public collector defaults (`https://www.vinted.com`, request headers/timeouts, extractor version, and `men`/`women` root aliases) and `src/vinted_radar/models.py` for typed catalog, run, identity, observation, raw-evidence, and coverage contracts. Public fields that Vinted may omit remain nullable in both the models and the schema.

I implemented `src/vinted_radar/storage/db.py` and `src/vinted_radar/storage/repository.py` to bootstrap the six required SQLite tables: `catalog_nodes`, `discovery_runs`, `listing_identities`, `listing_observations`, `raw_evidence_fragments`, and `scan_coverage`. The repository keeps observations append-only, preserves raw evidence in a separate table, and carries observed/extractor metadata through the stored record paths.

I added `tests/conftest.py` and `tests/test_repository.py` to prove schema creation, append-only history, nullable field round-tripping, and persistence of raw evidence plus scan coverage without any network dependency.

Because this is the first task in the slice and the auto-mode contract requires the slice verification test files to exist up front, I also created explicit pending tests for T02-T04 (`tests/test_flight_extract.py`, `tests/test_catalog_tree.py`, `tests/test_discovery_normalization.py`, `tests/test_cli_discover_smoke.py`) so the broader slice verification fails honestly for the still-unimplemented work rather than by missing-file errors.

## Verification

- `python -m pytest C:/Users/Alexis/Documents/VintedScrap2/tests/test_repository.py -c C:/Users/Alexis/Documents/VintedScrap2/pyproject.toml` ✅
  - 4 tests passed.
  - Verified required table bootstrap, append-only `listing_observations`, null-tolerant persistence, and raw evidence / scan coverage storage.

- `python -m ruff check C:/Users/Alexis/Documents/VintedScrap2/src/vinted_radar C:/Users/Alexis/Documents/VintedScrap2/tests` ✅
- `python -m ruff format --check C:/Users/Alexis/Documents/VintedScrap2/src/vinted_radar C:/Users/Alexis/Documents/VintedScrap2/tests` ✅

- Direct observability check via a Python snippet against `data/_verify_t01.db` ✅
  - Confirmed the presence of `catalog_nodes`, `discovery_runs`, `listing_identities`, `listing_observations`, `raw_evidence_fragments`, and `scan_coverage`.
  - Confirmed persisted `discovery_runs` status plus extractor-version-bearing `scan_coverage` and `raw_evidence_fragments` rows.

- Slice-level verification state recorded for handoff:
  - `python -m pytest tests/test_repository.py tests/test_flight_extract.py tests/test_catalog_tree.py tests/test_discovery_normalization.py tests/test_cli_discover_smoke.py` ⚠️ partial as expected on T01 (`test_repository.py` passed; T02-T04 pending tests failed explicitly).
  - `python -m vinted_radar.cli discover ...` ❌ expected at T01 because `src/vinted_radar/cli.py` belongs to T04.
  - `python scripts/verify_s01_smoke.py ...` ❌ expected at T01 because `scripts/verify_s01_smoke.py` belongs to T04.

## Diagnostics

- Inspect the repository contract in `tests/test_repository.py`.
- Open any SQLite DB via `vinted_radar.storage.repository.Repository` and query:
  - `discovery_runs`
  - `scan_coverage`
  - `listing_observations`
  - `raw_evidence_fragments`
- `data/_verify_t01.db` is a concrete local verification artifact showing the expected tables and observability records.

## Deviations

- Created explicit pending slice test files for T02-T04 even though they were not listed in the task’s Expected Output block, because the auto-mode instructions required first-task creation of slice verification test files.

## Known Issues

- `tests/test_flight_extract.py`, `tests/test_catalog_tree.py`, `tests/test_discovery_normalization.py`, and `tests/test_cli_discover_smoke.py` are intentionally failing placeholders until T02-T04 replace them with real coverage.
- `src/vinted_radar/cli.py` and `scripts/verify_s01_smoke.py` do not exist yet; slice smoke verification remains incomplete until T04.

## Files Created/Modified

- `pyproject.toml` — package metadata, runtime/dev dependencies, pytest config, and Ruff config.
- `.gitignore` — ignores local DB, artifacts, and test/lint caches.
- `src/vinted_radar/__init__.py` — base package exports for collector configuration.
- `src/vinted_radar/config.py` — collector defaults, extractor version, and root alias resolution.
- `src/vinted_radar/models.py` — typed contracts for catalogs, runs, identities, observations, evidence, and coverage.
- `src/vinted_radar/storage/__init__.py` — storage package export surface.
- `src/vinted_radar/storage/db.py` — SQLite bootstrap schema and table helpers.
- `src/vinted_radar/storage/repository.py` — repository API for runs, catalogs, identities, observations, evidence, and coverage.
- `tests/conftest.py` — shared repository/database fixtures.
- `tests/test_repository.py` — contract tests for the storage boundary.
- `tests/test_flight_extract.py` — explicit pending T02 slice test placeholder.
- `tests/test_catalog_tree.py` — explicit pending T03 slice test placeholder.
- `tests/test_discovery_normalization.py` — explicit pending T03 slice test placeholder.
- `tests/test_cli_discover_smoke.py` — explicit pending T04 slice test placeholder.
