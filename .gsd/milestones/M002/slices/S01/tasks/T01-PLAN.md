---
estimated_steps: 4
estimated_files: 4
skills_used:
  - code-optimizer
  - best-practices
  - test
  - review
---

# T01: Define the SQL overview contract and comparison lenses

**Slice:** S01 — SQL-Backed Overview Home + First Comparative Modules
**Milestone:** M002

## Description

Load `test` before coding and keep `code-optimizer` active while shaping the queries. This task retires the slice's highest technical risk: the current home route still pulls the whole corpus through `load_listing_scores()` and Python-side market summary logic. Replace that posture with repository-owned SQL that can answer the overview page's first question directly from SQLite, while preserving the honesty boundaries around observed, inferred, estimated, and partial signals.

## Steps

1. Add a reusable repository-level SQL state snapshot / aggregate seam that derives the overview home's summary counts from `listings`, `listing_observations`, `catalog_scans`, and `item_page_probes` without requiring full-corpus Python ranking work.
2. Expose SQL-backed overview summary blocks and first comparison modules for category, brand, price band, condition, and sold-state lenses, including support counts and deep-linkable lens values for later explorer/detail slices.
3. Keep R011 support explicit in the contract by surfacing low-support, partial-signal, observed-vs-inferred, and estimated-publication honesty fields rather than flattening them into one confidence number.
4. Add seeded repository tests that assert the overview counts, comparison ordering, support-threshold behavior, and honesty metadata over a realistic SQLite fixture.

## Must-Haves

- [ ] The repository can supply the overview home's primary counts and comparison modules without `load_listing_scores()` over the full corpus.
- [ ] The SQL contract includes category, brand, price band, condition, and sold-state comparison lenses with support metadata and drill-down values.
- [ ] Honesty fields distinguish observed, inferred, estimated, partial, or thin-support signals instead of hiding them.

## Verification

- `python -m pytest tests/test_overview_repository.py`
- `python -m pytest tests/test_history_repository.py`

## Observability Impact

- Signals added/changed: SQL overview support counts, low-support flags, sold-state mix, and honesty metadata for each comparison lens.
- How a future agent inspects this: run `python -m pytest tests/test_overview_repository.py` and inspect the repository payloads through the seeded fixture DB.
- Failure state exposed: missing support, contradictory state classification, or thin-signal modules fail as explicit contract assertions instead of surfacing later as vague UI regressions.

## Inputs

- `vinted_radar/repository.py` — current history, explorer, and state-input SQL seams that the overview contract should build on.
- `vinted_radar/state_machine.py` — the existing state vocabulary and confidence thresholds the new SQL contract must stay aligned with.
- `tests/test_dashboard.py` — existing seeded dashboard fixture patterns that can be reused for overview contract coverage.
- `tests/test_history_repository.py` — current repository-history assertions that protect the evidence backbone while the new overview queries are added.
- `amélioration/review_approfondie_2026-03-22.md` — review evidence that the home path still has scale debt and needs SQL-backed aggregates.

## Expected Output

- `vinted_radar/repository.py` — SQL-backed overview query helpers and any shared aggregate/state-classification SQL needed by the home route.
- `vinted_radar/state_machine.py` — any shared threshold/constants cleanup needed to keep the SQL and Python state vocabulary aligned.
- `tests/test_overview_repository.py` — new regression tests covering overview summary blocks, comparison modules, support thresholds, and honesty metadata.
- `tests/test_history_repository.py` — updated regression coverage if the shared repository seam or vocabulary changes.
