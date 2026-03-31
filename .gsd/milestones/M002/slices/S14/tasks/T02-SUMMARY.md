---
id: T02
parent: S14
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/services/reconciliation.py", "vinted_radar/cli.py", "vinted_radar/dashboard.py", "vinted_radar/platform/health.py", "vinted_radar/platform/postgres_repository.py", "tests/platform_test_fakes.py", "tests/test_reconciliation.py"]
key_decisions: ["Reuse one shared cutover snapshot helper across CLI, dashboard runtime payloads, and health JSON instead of re-deriving deployment mode independently in each surface.", "Reconciliation should compare source SQLite baselines to PostgreSQL, ClickHouse, and object-storage snapshots with row-count parity everywhere and time-window parity wherever the target store preserves source timestamps."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified with `python3 -m pytest tests/test_reconciliation.py -q`, which passed all four focused tests. The suite proved PostgreSQL, ClickHouse, and manifest-backed object storage reconcile against the SQLite source, the new CLI forwards options and emits the reconciliation report, platform health text shows explicit cutover warnings, and runtime/health payloads expose the cutover snapshot."
completed_at: 2026-03-31T13:08:53.205Z
blocker_discovered: false
---

# T02: Added a cross-store reconciliation command and made cutover state explicit in CLI, runtime, and health diagnostics.

> Added a cross-store reconciliation command and made cutover state explicit in CLI, runtime, and health diagnostics.

## What Happened
---
id: T02
parent: S14
milestone: M002
key_files:
  - vinted_radar/services/reconciliation.py
  - vinted_radar/cli.py
  - vinted_radar/dashboard.py
  - vinted_radar/platform/health.py
  - vinted_radar/platform/postgres_repository.py
  - tests/platform_test_fakes.py
  - tests/test_reconciliation.py
key_decisions:
  - Reuse one shared cutover snapshot helper across CLI, dashboard runtime payloads, and health JSON instead of re-deriving deployment mode independently in each surface.
  - Reconciliation should compare source SQLite baselines to PostgreSQL, ClickHouse, and object-storage snapshots with row-count parity everywhere and time-window parity wherever the target store preserves source timestamps.
duration: ""
verification_result: passed
completed_at: 2026-03-31T13:08:53.205Z
blocker_discovered: false
---

# T02: Added a cross-store reconciliation command and made cutover state explicit in CLI, runtime, and health diagnostics.

**Added a cross-store reconciliation command and made cutover state explicit in CLI, runtime, and health diagnostics.**

## What Happened

Completed the partial reconciliation work by wiring the existing reconciliation service into a new `platform-reconcile` CLI command, adding table and JSON output, and failing the command when any store mismatches the SQLite baseline. Finished cutover observability by loading one shared cutover snapshot into `runtime-status`, runtime payload construction, `/api/runtime`, `/health`, and the runtime page controller facts so operators can see explicit read-path and dual-write state instead of inferring it from raw booleans. Added `tests/test_reconciliation.py` to cover the real reconciliation flow against a backfilled SQLite corpus plus fake PostgreSQL/ClickHouse/object-storage targets, the new CLI command wiring, platform health cutover rendering, and the runtime/health cutover surfaces.

## Verification

Verified with `python3 -m pytest tests/test_reconciliation.py -q`, which passed all four focused tests. The suite proved PostgreSQL, ClickHouse, and manifest-backed object storage reconcile against the SQLite source, the new CLI forwards options and emits the reconciliation report, platform health text shows explicit cutover warnings, and runtime/health payloads expose the cutover snapshot.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_reconciliation.py -q` | 0 | ✅ pass | 927ms |


## Deviations

Used `python3` instead of `python` for verification because the local shell exposes `python3` rather than `python`.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/services/reconciliation.py`
- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`
- `vinted_radar/platform/health.py`
- `vinted_radar/platform/postgres_repository.py`
- `tests/platform_test_fakes.py`
- `tests/test_reconciliation.py`


## Deviations
Used `python3` instead of `python` for verification because the local shell exposes `python3` rather than `python`.

## Known Issues
None.
