---
id: T01
parent: S15
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/services/lifecycle.py", "vinted_radar/platform/config.py", "vinted_radar/platform/health.py", "vinted_radar/cli.py", "tests/test_lifecycle_jobs.py", "README.md"]
key_decisions: ["Treat delivered/failed outbox rows, bootstrap audit rows, and completed runtime-cycle history as transient PostgreSQL data that is archived to object storage before prune (recorded as D060).", "Keep bounded-storage observability on one `platform-lifecycle` CLI/report surface instead of scattering retention state across hidden config and ad hoc commands."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the new lifecycle service and CLI/report surface with targeted pytest coverage. `tests/test_lifecycle_jobs.py` passed end to end, covering lifecycle config defaults/overrides, ClickHouse TTL enforcement, PostgreSQL archive/prune behavior, object-store lifecycle rule configuration, and CLI rendering. `tests/test_platform_config.py` also passed after the shared config contract gained lifecycle fields."
completed_at: 2026-03-31T14:42:39.042Z
blocker_discovered: false
---

# T01: Added a `platform-lifecycle` retention command that enforces ClickHouse TTL, archives/prunes transient PostgreSQL rows, and reports explicit storage posture.

> Added a `platform-lifecycle` retention command that enforces ClickHouse TTL, archives/prunes transient PostgreSQL rows, and reports explicit storage posture.

## What Happened
---
id: T01
parent: S15
milestone: M002
key_files:
  - vinted_radar/services/lifecycle.py
  - vinted_radar/platform/config.py
  - vinted_radar/platform/health.py
  - vinted_radar/cli.py
  - tests/test_lifecycle_jobs.py
  - README.md
key_decisions:
  - Treat delivered/failed outbox rows, bootstrap audit rows, and completed runtime-cycle history as transient PostgreSQL data that is archived to object storage before prune (recorded as D060).
  - Keep bounded-storage observability on one `platform-lifecycle` CLI/report surface instead of scattering retention state across hidden config and ad hoc commands.
duration: ""
verification_result: passed
completed_at: 2026-03-31T14:42:39.042Z
blocker_discovered: false
---

# T01: Added a `platform-lifecycle` retention command that enforces ClickHouse TTL, archives/prunes transient PostgreSQL rows, and reports explicit storage posture.

**Added a `platform-lifecycle` retention command that enforces ClickHouse TTL, archives/prunes transient PostgreSQL rows, and reports explicit storage posture.**

## What Happened

Implemented a dedicated lifecycle service for bounded platform storage. The new service reasserts ClickHouse TTL policies for fact and rollup tables, archives transient PostgreSQL rows under the object-store archives prefix before pruning them, and configures/report object-store lifecycle rules for raw events, manifests, parquet, and archive prefixes. I extended the shared platform config with explicit lifecycle settings, added CLI/report rendering for the new storage-posture surface, documented the operator contract, and added focused lifecycle tests. During verification I found and fixed an archive-key collision between delivered and failed outbox lifecycle jobs so each archive payload now persists under its own object key.

## Verification

Verified the new lifecycle service and CLI/report surface with targeted pytest coverage. `tests/test_lifecycle_jobs.py` passed end to end, covering lifecycle config defaults/overrides, ClickHouse TTL enforcement, PostgreSQL archive/prune behavior, object-store lifecycle rule configuration, and CLI rendering. `tests/test_platform_config.py` also passed after the shared config contract gained lifecycle fields.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_lifecycle_jobs.py -q` | 0 | ✅ pass | 1091ms |
| 2 | `python3 -m pytest tests/test_platform_config.py -q` | 0 | ✅ pass | 602ms |


## Deviations

Local verification used `python3 -m pytest ...` instead of the plan's `python -m pytest ...` because this workstation does not expose a `python` binary in PATH.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/services/lifecycle.py`
- `vinted_radar/platform/config.py`
- `vinted_radar/platform/health.py`
- `vinted_radar/cli.py`
- `tests/test_lifecycle_jobs.py`
- `README.md`


## Deviations
Local verification used `python3 -m pytest ...` instead of the plan's `python -m pytest ...` because this workstation does not expose a `python` binary in PATH.

## Known Issues
None.
