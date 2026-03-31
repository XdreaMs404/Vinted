---
id: T04
parent: S12
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/cli.py", "tests/test_postgres_backfill.py", "tests/test_runtime_service.py", ".gsd/milestones/M002/slices/S12/tasks/T04-SUMMARY.md"]
key_decisions: ["D045: provide an explicit `postgres-backfill` CLI command and prove runtime cutover with a service-level smoke test that asserts SQLite runtime tables stay untouched when control-plane writes are redirected."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python3 -m py_compile vinted_radar/cli.py vinted_radar/services/postgres_backfill.py vinted_radar/services/runtime.py tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py` passed. `python3 -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` passed with 24 tests green, including the new backfill coverage and the external control-plane smoke test that proves SQLite runtime tables stay empty when the runtime writes through an injected control-plane repository."
completed_at: 2026-03-31T05:58:08Z
blocker_discovered: false
---

# T04: Added a PostgreSQL mutable-truth backfill CLI and external control-plane smoke proof.

> Added a `postgres-backfill` CLI and regression proof that runtime control can run through PostgreSQL mutable truth without SQLite runtime writes.

## What Happened
---
id: T04
parent: S12
milestone: M002
provides:
  - `postgres-backfill` CLI entrypoint plus regression guards for external control-plane runtime execution.
key_files:
  - vinted_radar/cli.py
  - tests/test_postgres_backfill.py
  - tests/test_runtime_service.py
  - .gsd/milestones/M002/slices/S12/tasks/T04-SUMMARY.md
key_decisions:
  - D045: provide an explicit `postgres-backfill` CLI command and prove runtime cutover with a service-level smoke test that asserts SQLite runtime tables stay untouched when control-plane writes are redirected.
patterns_established:
  - External control-plane smoke tests should assert SQLite `runtime_cycles` and `runtime_controller_state` stay empty when runtime truth is redirected away from SQLite.
observability_surfaces:
  - `python3 -m vinted_radar.cli postgres-backfill --db <sqlite.db> --format json`
duration: ""
verification_result: passed
completed_at: 2026-03-31T05:58:08Z
blocker_discovered: false
---

# T04: Added a PostgreSQL mutable-truth backfill CLI and external control-plane smoke proof.

**Added a `postgres-backfill` CLI and regression proof that runtime control can run through PostgreSQL mutable truth without SQLite runtime writes.**

## What Happened

Added the missing operational entrypoint for the existing SQLite-to-PostgreSQL mutable-truth backfill by wiring a new `postgres-backfill` CLI command in `vinted_radar/cli.py`. The command now loads platform config, forwards `--db`, `--now`, and `--sync-runtime-control/--skip-runtime-control` into `backfill_postgres_mutable_truth(...)`, supports `table` and `json` output, redacts PostgreSQL credentials in rendered output, and fails cleanly with a contextual error message when config or execution breaks.

Then I added the regression proof that had been missing from the reopened task. `tests/test_postgres_backfill.py` seeds a real SQLite source database, projects it into a spy mutable-truth repository, and asserts that discovery runs, catalogs, listing identity/presence/current-state rows, runtime cycles, and runtime controller state are backfilled correctly, including the `--skip-runtime-control` path. In `tests/test_runtime_service.py` I added an in-memory external control-plane repository and a batch-cycle smoke test that runs the real `RadarRuntimeService` against it, proving the cycle completes, the external control plane receives the runtime truth, and SQLite `runtime_cycles` / `runtime_controller_state` remain untouched.

This replaces the auto-mode recovery placeholder with a real task summary and leaves S12 ready to continue from a truthful T04 closeout instead of a missing-summary handoff.

## Verification

`python3 -m py_compile vinted_radar/cli.py vinted_radar/services/postgres_backfill.py vinted_radar/services/runtime.py tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py` passed. `python3 -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` passed with 24 tests green, including the new backfill coverage and the external control-plane smoke test that proves SQLite runtime tables stay empty when the runtime writes through an injected control-plane repository.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/cli.py vinted_radar/services/postgres_backfill.py vinted_radar/services/runtime.py tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py` | 0 | ✅ pass | 80ms |
| 2 | `python3 -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` | 0 | ✅ pass | 1505ms |

## Diagnostics

Run `python3 -m vinted_radar.cli postgres-backfill --db <sqlite.db> --format json` to inspect redacted target DSN plus discovery/catalog/listing/runtime row counts. Re-run `python3 -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` if mutable-truth cutover work regresses. If runtime cutover ever looks suspect again, check that `tests/test_runtime_service.py` still proves SQLite `runtime_cycles` and `runtime_controller_state` remain empty when an external control-plane repository is injected.

## Deviations

Used a service-level external control-plane smoke test in `tests/test_runtime_service.py` instead of adding another live PostgreSQL fixture. S10 already covers real platform wiring; the regression risk this task needed to retire was silent fallback to SQLite runtime mutation when an external control-plane repository is injected.

## Known Issues

GSD forensics still show a harness-level warning where some execute-task prompts try to read `~/.gsd/...` as `/root/.gsd/...`. This task is now complete and the placeholder summary has been replaced, but that template-path warning was not fixed inside this repository.

## Files Created/Modified

- `vinted_radar/cli.py` — added the `postgres-backfill` command, option forwarding, JSON/table output, and backfill report rendering.
- `tests/test_postgres_backfill.py` — added real SQLite-to-spy mutable-truth backfill coverage, including the runtime-control skip path and CLI contract verification.
- `tests/test_runtime_service.py` — added an external control-plane runtime smoke test that proves batch execution leaves SQLite runtime mutation tables empty.
- `.gsd/milestones/M002/slices/S12/tasks/T04-SUMMARY.md` — replaced the auto-mode recovery placeholder with the real task closeout record.


## Deviations
Used a service-level external control-plane smoke test in `tests/test_runtime_service.py` instead of adding another live PostgreSQL fixture. S10 already covers real platform wiring; the regression risk this task needed to retire was silent fallback to SQLite runtime mutation when an external control-plane repository is injected.

## Known Issues
GSD forensics still show a harness-level warning where some execute-task prompts try to read `~/.gsd/...` as `/root/.gsd/...`. This task is now complete and the placeholder summary has been replaced, but that template-path warning was not fixed inside this repository.
