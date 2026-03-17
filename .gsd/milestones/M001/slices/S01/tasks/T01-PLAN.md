---
estimated_steps: 4
estimated_files: 8
---

# T01: Bootstrap the Python collector contracts and pytest harness

**Slice:** S01 — Public Discovery + Normalized Ingestion
**Milestone:** M001

## Description

Load the `test` skill before implementation so the new pytest setup follows project conventions from the start, and use `lint` on touched Python files before handoff. This task turns the blank repository into a runnable Python collector workspace with explicit storage and model contracts. Use `httpx` for HTTP, `beautifulsoup4` for HTML parsing, `typer` for CLI plumbing, `pytest` for tests, and SQLite for local persistence. The goal is not a placeholder scaffold: the schema and repository layer must already reflect S01’s real data boundary so S02 can extend it without destructive redesign.

## Steps

1. Create `pyproject.toml` and the base `src/vinted_radar/` package layout with dependencies, pytest configuration, and module wiring; update `.gitignore` to exclude local runtime outputs such as `data/`, `artifacts/`, and `.pytest_cache/`.
2. Add `src/vinted_radar/config.py` and `src/vinted_radar/models.py` with base URL `https://www.vinted.com`, default headers/timeouts, root aliases (`men` -> `5`, `women` -> `1904`), extractor version plumbing, and typed models for `CatalogNode`, `DiscoveryRun`, `ListingIdentity`, `ListingObservation`, `RawEvidenceFragment`, and coverage counters. Keep public fields nullable where Vinted may omit them.
3. Implement `src/vinted_radar/storage/db.py` and `src/vinted_radar/storage/repository.py` to bootstrap SQLite tables for `catalog_nodes`, `discovery_runs`, `listing_identities`, `listing_observations`, `raw_evidence_fragments`, and `scan_coverage`. Observations must be append-only, raw evidence must be stored separately from normalized facts, and every record path must carry `observed_at` / extractor metadata needed later.
4. Add `tests/conftest.py` and `tests/test_repository.py` proving schema creation, append-only observation behavior, nullable field handling, and raw evidence persistence without any live network dependency.

## Must-Haves

- [ ] The repo has a real Python package/test runner, not loose scripts.
- [ ] SQLite tables and typed models match the slice boundary: catalog registry, run tracking, listing identities, append-only observations, raw evidence, and scan coverage.
- [ ] Null public fields are first-class citizens in the schema and repository API rather than treated as errors.

## Verification

- `python -m pytest tests/test_repository.py`
- Confirm the test creates a temp DB, bootstraps the required tables, and passes without internet access.

## Observability Impact

- Signals added/changed: durable `discovery_runs` / `scan_coverage` tables and extractor-version-bearing observation/evidence records.
- How a future agent inspects this: open the SQLite DB created in tests or by later runtime tasks and inspect the schema/tables through the repository layer.
- Failure state exposed: missing tables, incorrect nullability, or non-append observation behavior fail deterministically in `tests/test_repository.py`.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — authoritative slice goal, verification targets, and task ordering.
- `.gsd/DECISIONS.md` — includes `D002`, `D003`, and `D010`, which require public-only collection, observed-vs-inferred separation, and the Python/SQLite delivery stack.

## Expected Output

- `pyproject.toml` — Python package metadata, dependencies, and pytest/tool configuration.
- `.gitignore` — local runtime/test outputs ignored.
- `src/vinted_radar/config.py` — base collector configuration and root mappings.
- `src/vinted_radar/models.py` — typed contracts for catalogs, listings, observations, evidence, and coverage.
- `src/vinted_radar/storage/db.py` and `src/vinted_radar/storage/repository.py` — SQLite bootstrap and repository operations.
- `tests/conftest.py` and `tests/test_repository.py` — passing contract tests for the storage boundary.
