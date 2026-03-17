---
estimated_steps: 5
estimated_files: 6
---

# T04: Wire item-detail enrichment, SQLite persistence, and the real discover CLI smoke path

**Slice:** S01 — Public Discovery + Normalized Ingestion
**Milestone:** M001

## Description

Load `test` first so the final composition lands with an automated smoke test, and run `lint` on the Python package before handing off. This is the slice-closing composition task. It must turn the earlier parser/discovery pieces into the actual operator entrypoint that supports R010 in batch form and leaves honest diagnostics for R011. The result should be a real `discover` command that can fetch a bounded live sample, persist S01 data into SQLite, write a coverage artifact, and then be checked by a dedicated verification script.

## Steps

1. Implement `src/vinted_radar/vinted/item_detail.py` to fetch item pages, merge the core `item` fragment with supporting `breadcrumbs`, `attributes`, and `favourite` fragments, and keep every missing field nullable while preserving raw fragment names for evidence storage.
2. Add an orchestration layer (for example `src/vinted_radar/runtime/discover_run.py`) that combines config, HTTP client/session reuse, catalog tree discovery, bounded pagination discovery, optional item-detail enrichment, and repository writes into one structured run.
3. Build `src/vinted_radar/cli.py` with a Typer `discover` command supporting `--root`, `--max-pages-per-catalog`, `--db-path`, `--artifacts-dir`, and `--item-details (none|sample|all)`. `sample` should fetch a deterministic bounded subset of item pages suitable for smoke runs.
4. Persist `catalog_nodes`, `listing_identities`, `listing_observations`, `raw_evidence_fragments`, `scan_coverage`, and `discovery_runs`, then emit `artifacts/.../coverage.json` containing requested roots, scanned catalog IDs/pages, unique listings, duplicates, errors, stop reasons, timestamps, and extractor version.
5. Add `tests/test_cli_discover_smoke.py` using mocked fetch responses for composition coverage, plus `scripts/verify_s01_smoke.py` that validates a real smoke run produced roots `5` and `1904`, non-zero persisted rows, and the required coverage artifact fields.

## Must-Haves

- [ ] A real local batch command exists and composes discovery, item enrichment, persistence, and artifact writing.
- [ ] The command leaves inspectable runtime evidence in both SQLite and `coverage.json`.
- [ ] Smoke verification proves roots `5` and `1904` were included and that the run persisted non-zero catalog/listing/observation data.

## Verification

- `python -m pytest tests/test_cli_discover_smoke.py`
- `python -m vinted_radar.cli discover --root men --root women --max-pages-per-catalog 2 --item-details sample --db-path data/radar.db --artifacts-dir artifacts/s01-smoke`
- `python scripts/verify_s01_smoke.py --db-path data/radar.db --coverage artifacts/s01-smoke/coverage.json --expect-root 5 --expect-root 1904`

## Observability Impact

- Signals added/changed: persisted run status, coverage rows, artifact timestamps, duplicate/error counters, and raw evidence fragment metadata now exist for every CLI run.
- How a future agent inspects this: rerun the CLI, inspect `coverage.json`, or query the SQLite tables named in the slice plan.
- Failure state exposed: the verifier and persisted run/coverage records make empty runs, partial persistence, missing roots, and page/item fetch failures immediately visible.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — final slice demo and smoke verification contract.
- `.gsd/milestones/M001/slices/S01/tasks/T03-PLAN.md` plus completed T03 outputs — tree discovery, normalized listing discovery, and coverage counters ready to persist.

## Expected Output

- `src/vinted_radar/vinted/item_detail.py` — item-page enrichment logic.
- `src/vinted_radar/runtime/discover_run.py` — end-to-end discovery run orchestration.
- `src/vinted_radar/cli.py` — Typer batch entrypoint exposing `discover`.
- `tests/test_cli_discover_smoke.py` — passing automated CLI composition smoke test.
- `scripts/verify_s01_smoke.py` — runtime artifact/DB verifier for the live smoke command.
- `artifacts/s01-smoke/coverage.json` — expected artifact shape produced by the real command.
