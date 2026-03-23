---
id: T01
parent: S04
milestone: M002
provides:
  - SQL-first explorer filters, paging, and comparison modules with explicit support metadata
key_files:
  - vinted_radar/repository.py
  - vinted_radar/db.py
  - tests/test_explorer_repository.py
  - tests/test_repository.py
key_decisions:
  - S04 uses one repository-owned classified explorer snapshot for filters, paging, and comparison modules instead of request-time full-corpus reshaping.
patterns_established:
  - Explorer browsing and comparison stay SQL-first, with low-support rows preserved and labeled rather than filtered away.
observability_surfaces:
  - /api/explorer, tests/test_explorer_repository.py, tests/test_repository.py::test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: Expand the SQL explorer and comparison contract

**Expanded the repository into a single SQL-first explorer snapshot with filter, paging, comparison, and honesty semantics, then hardened legacy DB bootstrap so real proof snapshots still open.**

## What Happened

`vinted_radar/repository.py` now exposes a richer explorer contract instead of a thin paged listing seam. The explorer snapshot covers root, catalog, brand, condition, sold-state, price-band, query, sort, page, and page-size filtering, and returns comparison modules for category, brand, price band, condition, and sold state with support counts, support ratios, and low-support honesty metadata.

I added a dedicated `tests/test_explorer_repository.py` suite to pin filter-option counts, filtered paging, comparison-module drill-down values, and low-support behavior. I also expanded `tests/test_repository.py` with a regression that opens a legacy `listings` table lacking late-added metadata columns, because browser proof on the richer S04 demo DB exposed that `connect_database()` could still fail before migrations ran.

The resulting repository seam is now the authoritative explorer/query contract for the dashboard and detail-navigation work in T02/T03.

## Verification

Repository-focused explorer and schema-bootstrap coverage passed, and the same code later held under the full test suite and browser-backed slice proof.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_explorer_repository.py tests/test_repository.py` | 0 | PASS | 0.34s |
| 2 | `python -m pytest` | 0 | PASS | 4.09s |

## Diagnostics

Inspect `/api/explorer` for the serialized explorer contract, `tests/test_explorer_repository.py` for supported filter/comparison semantics, and `tests/test_repository.py::test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes` for the historical-snapshot bootstrap guardrail.

## Deviations

The written task did not call out `vinted_radar/db.py`, but slice-level browser verification against a richer historical DB exposed a real bootstrap fault (`sqlite3.OperationalError: no such column: created_at_ts`). I fixed that by moving dependent index creation into a post-migration schema step and added a regression so older proof DBs remain openable.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/repository.py` — expanded the explorer snapshot, filter options, summary, comparison modules, sorting, and paging contract.
- `vinted_radar/db.py` — moved legacy-dependent listing indexes to post-migration bootstrap so historical snapshots open cleanly.
- `tests/test_explorer_repository.py` — added targeted explorer contract regressions for state/price-band filters and low-support comparison modules.
- `tests/test_repository.py` — added explorer filter coverage plus a legacy-schema migration regression.
