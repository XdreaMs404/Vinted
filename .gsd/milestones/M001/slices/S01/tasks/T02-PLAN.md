---
estimated_steps: 4
estimated_files: 5
---

# T02: Implement fixture-backed SSR fragment extraction for catalog and item pages

**Slice:** S01 — Public Discovery + Normalized Ingestion
**Milestone:** M001

## Description

Load the `test` skill first and keep `debug-like-expert` in reserve if the fixture payloads are harder to decode than expected. This task retires the highest-risk seam in S01: extracting useful structured data from Vinted’s server-rendered HTML without building a full React Flight decoder. Keep the parser intentionally narrow. It only needs to recover catalog `items`/`pagination` plus item-side `item`, `breadcrumbs`, `attributes`, and `favourite` fragments from `self.__next_f.push(...)` scripts. Missing optional fragments should degrade to `None`; malformed or missing required fragments must fail loudly with context.

## Steps

1. Add representative live HTML fixtures under `tests/fixtures/vinted/`: one Men catalog page, one deeper leaf catalog page, and one item page. Preserve the HTML shape exactly enough for the extractor to parse real SSR payloads.
2. Implement `src/vinted_radar/vinted/flight_extract.py` with targeted helpers such as `extract_catalog_payload(html: str)` and `extract_item_fragments(html: str)`. Scan `self.__next_f.push(...)` scripts, decode only the needed escaped JSON blocks, and avoid any attempt to fully interpret the React Flight protocol.
3. Introduce explicit parser error types or diagnostic payloads that report which fragment type failed, what selector/match strategy was attempted, and enough source context to debug markup changes. Optional fragments must return `None` cleanly.
4. Write `tests/test_flight_extract.py` covering the positive fixture cases plus at least one malformed/missing-fragment case and one optional-fragment-null case.

## Must-Haves

- [ ] Catalog fixtures decode into structured `items` and `pagination` data.
- [ ] Item fixtures decode into the core item fragment plus supporting fragments (`breadcrumbs`, `attributes`, `favourite`) when present.
- [ ] Extraction failures produce actionable diagnostics instead of silent empty lists/dicts.

## Verification

- `python -m pytest tests/test_flight_extract.py`
- Confirm the tests exercise both success and failure/null paths with no live HTTP calls.

## Observability Impact

- Signals added/changed: extractor diagnostics now identify fragment type and failure reason at the HTML parsing seam.
- How a future agent inspects this: rerun `tests/test_flight_extract.py` against fixtures or inspect thrown parser errors during live runs.
- Failure state exposed: exact fragment extraction failure becomes visible instead of surfacing later as mysterious missing listing data.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — extractor scope and verification target.
- `.gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md` plus completed T01 outputs — package layout, test runner, config, and model/repository contracts.

## Expected Output

- `tests/fixtures/vinted/catalog-men.html` — saved real SSR catalog HTML fixture.
- `tests/fixtures/vinted/catalog-leaf.html` — saved deeper sub-category HTML fixture.
- `tests/fixtures/vinted/item-sample.html` — saved item-detail HTML fixture.
- `src/vinted_radar/vinted/flight_extract.py` — targeted catalog/item fragment extraction helpers.
- `tests/test_flight_extract.py` — passing regression tests for SSR extraction behavior.
