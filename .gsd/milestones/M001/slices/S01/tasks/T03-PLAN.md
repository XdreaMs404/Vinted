---
estimated_steps: 5
estimated_files: 5
---

# T03: Discover catalog trees and normalize paginated listing stubs with coverage accounting

**Slice:** S01 — Public Discovery + Normalized Ingestion
**Milestone:** M001

## Description

Load `test` before coding and run `lint` on the touched Python modules before finishing. This task closes the core discovery contract for R001. It must walk the public Men and Women entry points, canonicalize categories by numeric catalog ID even when slug language changes, paginate only within the reported bounds, and turn catalog listing stubs into normalized records that keep missing data explicit. Build discovery around injected fetch/session abstractions so tests can cover the logic without live network calls.

## Steps

1. Implement `src/vinted_radar/vinted/catalog_tree.py` to fetch and parse root catalog pages for Men (`/catalog/5-men`) and Women (`/catalog/1904-women`) with BeautifulSoup, extract reachable sub-category links, canonicalize `/catalog/<id>-...` URLs by numeric ID, and preserve parent/root relationships plus last-seen metadata.
2. Implement `src/vinted_radar/vinted/discovery.py` (and `src/vinted_radar/vinted/normalize.py` if helpful) to request paginated catalog pages, extract `items`/`pagination` through the T02 parser, stop strictly at first-page `total_pages`, and never continue optimistically once the bound is known.
3. Normalize catalog listing stubs into canonical identity and observation-ready records, preserving observed values as fetched (for example `currency_code`) and representing absent public fields as `None` instead of default guesses.
4. Track per-catalog coverage counters for pages scanned, unique listings, duplicate listing IDs, errors, and stop reasons so the later CLI can persist and report honest footprint data.
5. Add `tests/test_catalog_tree.py` and `tests/test_discovery_normalization.py` covering mixed-language slugs, root/parent derivation, bounded pagination, null-tolerant normalization, duplicate detection, and error/stop accounting.

## Must-Haves

- [ ] Numeric catalog ID is the canonical category key regardless of slug language.
- [ ] Discovery stops at reported pagination bounds and records why scanning stopped.
- [ ] Normalization and coverage accounting tolerate missing/partial public data without crashing.

## Verification

- `python -m pytest tests/test_catalog_tree.py tests/test_discovery_normalization.py`
- Confirm the tests use injected fixtures/stubs, not the live site.

## Observability Impact

- Signals added/changed: structured per-catalog coverage counters and stop reasons become first-class outputs from discovery.
- How a future agent inspects this: run the catalog/discovery tests or inspect the coverage models returned by discovery before persistence.
- Failure state exposed: pagination overruns, bad catalog canonicalization, duplicate spikes, and normalization errors become explicit test failures or coverage anomalies.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — discovery scope, root IDs, and verification contract.
- `.gsd/milestones/M001/slices/S01/tasks/T02-PLAN.md` plus completed T02 outputs — SSR fragment extractor and live-shaped fixtures.

## Expected Output

- `src/vinted_radar/vinted/catalog_tree.py` — sub-category discovery and catalog canonicalization logic.
- `src/vinted_radar/vinted/discovery.py` — bounded pagination and coverage-aware listing discovery.
- `src/vinted_radar/vinted/normalize.py` — listing stub normalization helpers if split out.
- `tests/test_catalog_tree.py` — passing tests for catalog tree parsing and canonical IDs.
- `tests/test_discovery_normalization.py` — passing tests for pagination, normalization, duplicates, and coverage counters.
