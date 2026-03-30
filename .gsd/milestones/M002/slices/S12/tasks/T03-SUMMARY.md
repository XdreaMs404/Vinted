---
id: T03
parent: S12
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/cli.py", "vinted_radar/services/runtime.py", "vinted_radar/services/discovery.py", "vinted_radar/platform/postgres_repository.py", "tests/test_runtime_cli.py", ".gsd/milestones/M002/slices/S12/tasks/T03-SUMMARY.md"]
key_decisions: ["Use the existing enable_polyglot_reads cutover flag to switch runtime-status, pause/resume, and runtime cycle/controller persistence to PostgreSQL mutable truth, while mirroring discovery bookkeeping into PostgreSQL on the same path."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python3 -m py_compile vinted_radar/cli.py vinted_radar/services/runtime.py vinted_radar/services/discovery.py vinted_radar/platform/postgres_repository.py tests/test_runtime_cli.py` passed. `python3 -m pytest tests/test_runtime_cli.py -q` passed with 13 tests green, including the new polyglot-read runtime CLI coverage."
completed_at: 2026-03-30T21:24:57.193Z
blocker_discovered: false
---

# T03: Routed runtime CLI control-plane commands and runtime cycle/controller persistence through PostgreSQL mutable truth when polyglot reads are enabled.

> Routed runtime CLI control-plane commands and runtime cycle/controller persistence through PostgreSQL mutable truth when polyglot reads are enabled.

## What Happened
---
id: T03
parent: S12
milestone: M002
key_files:
  - vinted_radar/cli.py
  - vinted_radar/services/runtime.py
  - vinted_radar/services/discovery.py
  - vinted_radar/platform/postgres_repository.py
  - tests/test_runtime_cli.py
  - .gsd/milestones/M002/slices/S12/tasks/T03-SUMMARY.md
key_decisions:
  - Use the existing enable_polyglot_reads cutover flag to switch runtime-status, pause/resume, and runtime cycle/controller persistence to PostgreSQL mutable truth, while mirroring discovery bookkeeping into PostgreSQL on the same path.
duration: ""
verification_result: passed
completed_at: 2026-03-30T21:24:57.194Z
blocker_discovered: false
---

# T03: Routed runtime CLI control-plane commands and runtime cycle/controller persistence through PostgreSQL mutable truth when polyglot reads are enabled.

**Routed runtime CLI control-plane commands and runtime cycle/controller persistence through PostgreSQL mutable truth when polyglot reads are enabled.**

## What Happened

Wired the runtime CLI control-plane path to select PostgreSQL mutable truth under the polyglot-read cutover, so runtime-status, runtime-pause, runtime-resume, and runtime batch/continuous control-plane persistence now resolve through one mutable-truth source instead of SQLite when the cutover is enabled. Activated the previously injected control-plane repository path inside RadarRuntimeService for cycle/controller writes and continuous-controller heartbeats, added a PostgreSQL repository factory helper, and updated the default discovery service to mirror discovery bookkeeping into PostgreSQL mutable truth. Also preserved replay idempotence by tagging direct catalog-projection rows with emitted batch event/manifest identities when evidence batches exist, then added runtime CLI regression tests covering the new Postgres-backed cutover behavior.

## Verification

`python3 -m py_compile vinted_radar/cli.py vinted_radar/services/runtime.py vinted_radar/services/discovery.py vinted_radar/platform/postgres_repository.py tests/test_runtime_cli.py` passed. `python3 -m pytest tests/test_runtime_cli.py -q` passed with 13 tests green, including the new polyglot-read runtime CLI coverage.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile vinted_radar/cli.py vinted_radar/services/runtime.py vinted_radar/services/discovery.py vinted_radar/platform/postgres_repository.py tests/test_runtime_cli.py` | 0 | ✅ pass | 100ms |
| 2 | `python3 -m pytest tests/test_runtime_cli.py -q` | 0 | ✅ pass | 550ms |


## Deviations

Updated `vinted_radar/services/discovery.py` in addition to the task-plan input files because the PostgreSQL runtime-status/control-plane path needs discovery bookkeeping projected into mutable truth to keep the cutover coherent.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/cli.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/platform/postgres_repository.py`
- `tests/test_runtime_cli.py`
- `.gsd/milestones/M002/slices/S12/tasks/T03-SUMMARY.md`


## Deviations
Updated `vinted_radar/services/discovery.py` in addition to the task-plan input files because the PostgreSQL runtime-status/control-plane path needs discovery bookkeeping projected into mutable truth to keep the cutover coherent.

## Known Issues
None.
