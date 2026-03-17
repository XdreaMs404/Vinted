---
estimated_steps: 6
estimated_files: 5
---

# T01: Bootstrap discovery package and verification harness

**Slice:** S01 — Public Discovery + Normalized Ingestion
**Milestone:** M001

## Description

Create the first runnable Python package shape for the radar so S01 has a real CLI entrypoint, SQLite schema bootstrap, and executable smoke tests before the collector logic is added.

## Steps

1. Create `pyproject.toml` with the runtime and test dependencies needed for a Typer + SQLite based collector package.
2. Add the `vinted_radar` package skeleton, including a CLI entrypoint and database bootstrap module.
3. Define the initial schema tables for runs, catalogs, listings, discoveries, and scan diagnostics.
4. Expose `discover` and `coverage` commands that initialize the DB and report placeholder state cleanly.
5. Add a smoke test that proves the CLI can initialize the schema and report an empty coverage state.
6. Run the targeted smoke test and fix any environment or packaging issues immediately.

## Must-Haves

- [ ] The project has a real Python package and module entrypoint.
- [ ] The SQLite schema initializes idempotently from the CLI.
- [ ] Smoke tests exist and pass.

## Verification

- `python -m pytest tests/test_cli_smoke.py`
- `python -m vinted_radar.cli coverage --db data/test-smoke.db`

## Observability Impact

- Signals added/changed: `discovery_runs`, `catalog_scans`, `listing_discoveries`, `listings`, and `catalogs` schema surfaces.
- How a future agent inspects this: run `python -m vinted_radar.cli coverage --db <path>` or inspect the SQLite DB directly.
- Failure state exposed: schema/bootstrap failures become immediate CLI errors instead of silent missing tables.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — the execution contract for the slice.
- `.gsd/DECISIONS.md` — the collector stack decision already recorded for S01.

## Expected Output

- `pyproject.toml` — package metadata and CLI entrypoint.
- `vinted_radar/cli.py` — runnable discovery/coverage command group.
- `vinted_radar/db.py` — schema initialization helpers.
- `tests/test_cli_smoke.py` — executable proof that the bootstrap works.
 works.
