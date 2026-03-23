---
estimated_steps: 4
estimated_files: 4
skills_used:
  - debug-like-expert
  - best-practices
  - test
  - review
---

# T01: Expand the SQL explorer and comparison contract

**Slice:** S04 — Full Explorer + Comparative Intelligence
**Milestone:** M002

## Description

Load `debug-like-expert`, `test`, and `review` before coding. This task makes the explorer analytically real. The repository must answer the main corpus-browsing questions directly: filter, sort, page, and compare by the dimensions M002 calls first-class, while keeping low-support and partial-signal honesty explicit instead of decorating over weak evidence.

## Steps

1. Extend `vinted_radar/repository.py` with first-class explorer filters for brand, price band, condition, sold state, query, sort, and paging that stay SQL-first.
2. Add comparison aggregate queries for category, brand, price band, condition, and sold state with support counts, honest fallback rules, and stable drill-down values.
3. Reuse or lightly extend `vinted_radar/scoring.py` only where needed for comparison semantics, without reintroducing full-corpus request-time recomputation.
4. Add targeted repository regressions in `tests/test_explorer_repository.py` and expand `tests/test_repository.py` for filter, paging, comparison, and low-support behaviors.

## Must-Haves

- [x] The explorer repository contract is SQL-first for browsing and comparison, not a thin wrapper over full-corpus Python reshaping.
- [x] Comparison modules return support/uncertainty metadata alongside drill-down values.
- [x] Invalid or low-sample filter/comparison paths degrade honestly instead of producing fake precision.

## Verification

- `python -m pytest tests/test_explorer_repository.py tests/test_repository.py`
- `python -m pytest tests/test_explorer_repository.py -k comparison`

## Observability Impact

- Signals added/changed: explorer filter contract, total-match and page metadata, comparison support counts, and low-support flags.
- How a future agent inspects this: run the explorer repository tests, inspect `/api/explorer`, and compare overview deep-link parameters against the repository contract.
- Failure state exposed: unsupported filters, paging drift, or comparison modules that overstate thin samples fail as payload assertions instead of reaching the UI as plausible-looking but weak output.

## Inputs

- `vinted_radar/repository.py` — current explorer paging/filter seam that needs stronger dimensions and comparison outputs.
- `vinted_radar/scoring.py` — existing contextual scoring semantics that comparison modules may need to reference carefully.
- `tests/test_repository.py` — current repository coverage that should grow with the explorer contract.
- `tests/test_overview_repository.py` — overview query contract that explorer drill-down values should stay compatible with.

## Expected Output

- `vinted_radar/repository.py` — expanded explorer filters, paging, and comparison aggregate contract.
- `vinted_radar/scoring.py` — any minimal shared comparison semantics needed without reintroducing full-corpus runtime work.
- `tests/test_repository.py` — broader repository coverage for explorer filtering/paging behavior.
- `tests/test_explorer_repository.py` — targeted explorer/comparison regressions for the new SQL contract.
