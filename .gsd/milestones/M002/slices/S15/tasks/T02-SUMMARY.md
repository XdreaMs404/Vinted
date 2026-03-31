---
id: T02
parent: S15
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/services/platform_audit.py", "vinted_radar/platform/health.py", "vinted_radar/cli.py", "vinted_radar/dashboard.py", "tests/test_platform_audit.py"]
key_decisions: ["Consolidated day-to-day migration trust on one `platform-audit` contract instead of forcing operators to correlate reconciliation, checkpoint, lifecycle, and backfill state manually (recorded as D061)."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the new audit contract with targeted pytest coverage. `python3 -m pytest tests/test_platform_audit.py -q` passed, covering service aggregation, the new `platform-audit` CLI JSON output, and the runtime/health payload exposure of the `platform_audit` surface."
completed_at: 2026-03-31T15:02:27.816Z
blocker_discovered: false
---

# T02: Added a unified `platform-audit` surface that wraps reconciliation, ingest lag, lifecycle drift, and backfill posture into CLI and runtime/health payloads.

> Added a unified `platform-audit` surface that wraps reconciliation, ingest lag, lifecycle drift, and backfill posture into CLI and runtime/health payloads.

## What Happened
---
id: T02
parent: S15
milestone: M002
key_files:
  - vinted_radar/services/platform_audit.py
  - vinted_radar/platform/health.py
  - vinted_radar/cli.py
  - vinted_radar/dashboard.py
  - tests/test_platform_audit.py
key_decisions:
  - Consolidated day-to-day migration trust on one `platform-audit` contract instead of forcing operators to correlate reconciliation, checkpoint, lifecycle, and backfill state manually (recorded as D061).
duration: ""
verification_result: passed
completed_at: 2026-03-31T15:02:27.816Z
blocker_discovered: false
---

# T02: Added a unified `platform-audit` surface that wraps reconciliation, ingest lag, lifecycle drift, and backfill posture into CLI and runtime/health payloads.

**Added a unified `platform-audit` surface that wraps reconciliation, ingest lag, lifecycle drift, and backfill posture into CLI and runtime/health payloads.**

## What Happened

Implemented a dedicated platform-audit service that reuses the existing reconciliation contract and adds operator-readable status for PostgreSQL current-state checkpoints, ClickHouse analytical ingest checkpoints, lifecycle dry-run posture, and full-backfill checkpoint progress. Exposed that contract through a new `platform-audit` CLI command, surfaced the summary in `runtime-status`, and mirrored the same `platform_audit` payload into `/api/runtime`, `build_runtime_payload()`, and `/health` so runtime-facing diagnostics and health checks read one bounded audit surface. Added focused tests covering the new service, CLI JSON output, and runtime/health payload wiring.

## Verification

Verified the new audit contract with targeted pytest coverage. `python3 -m pytest tests/test_platform_audit.py -q` passed, covering service aggregation, the new `platform-audit` CLI JSON output, and the runtime/health payload exposure of the `platform_audit` surface.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_platform_audit.py -q` | 0 | ✅ pass | 460ms |


## Deviations

Used a new `vinted_radar/services/platform_audit.py` aggregation seam and wrapped the existing reconciliation implementation instead of renaming the already-present `vinted_radar/services/reconciliation.py` service from the planner snapshot. Local verification used `python3 -m pytest ...` because this workstation does not expose a `python` binary in PATH.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/services/platform_audit.py`
- `vinted_radar/platform/health.py`
- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`
- `tests/test_platform_audit.py`


## Deviations
Used a new `vinted_radar/services/platform_audit.py` aggregation seam and wrapped the existing reconciliation implementation instead of renaming the already-present `vinted_radar/services/reconciliation.py` service from the planner snapshot. Local verification used `python3 -m pytest ...` because this workstation does not expose a `python` binary in PATH.

## Known Issues
None.
