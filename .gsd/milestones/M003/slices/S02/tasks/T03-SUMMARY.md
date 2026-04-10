---
id: T03
parent: S02
milestone: M003
provides: []
requires: []
affects: []
key_files: ["vinted_radar/cli.py", "vinted_radar/dashboard.py", "tests/test_runtime_cli.py", "tests/test_dashboard.py"]
key_decisions: []
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task verification command from the plan: python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py -q. The expanded CLI and dashboard suites passed, including the new lane-aware assertions for table output, runtime payloads, HTML rendering, and secret redaction. Verification was completed through deterministic CLI and WSGI tests."
completed_at: 2026-04-09T15:57:59.423Z
blocker_discovered: false
---

# T03: Added lane-aware runtime-status output and /api/runtime summaries with redacted per-lane config and failure visibility.

> Added lane-aware runtime-status output and /api/runtime summaries with redacted per-lane config and failure visibility.

## What Happened
---
id: T03
parent: S02
milestone: M003
key_files:
  - vinted_radar/cli.py
  - vinted_radar/dashboard.py
  - tests/test_runtime_cli.py
  - tests/test_dashboard.py
key_decisions:
  - (none)
duration: ""
verification_result: passed
completed_at: 2026-04-09T15:57:59.423Z
blocker_discovered: false
---

# T03: Added lane-aware runtime-status output and /api/runtime summaries with redacted per-lane config and failure visibility.

**Added lane-aware runtime-status output and /api/runtime summaries with redacted per-lane config and failure visibility.**

## What Happened

Extended the operator-facing runtime surfaces to expose named-lane truth without adding new repository reads. The CLI runtime-status table now prints a per-lane section with each lane’s status, phase, mode, heartbeat timing, resume timer, active/latest cycle IDs, benchmark label, sanitized config, and last error so one broken lane no longer hides healthy siblings. On the dashboard side, the runtime payload builder now emits condensed lane_summaries, /api/runtime now merges those summaries into the existing top-level runtime contract while preserving the raw nested runtime payload, and the /runtime HTML view now renders an État par lane section with the same benchmark/config/error visibility. Regression tests were added to prove redaction-safe config rendering and per-lane truth in both the CLI and runtime/dashboard surfaces.

## Verification

Ran the task verification command from the plan: python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py -q. The expanded CLI and dashboard suites passed, including the new lane-aware assertions for table output, runtime payloads, HTML rendering, and secret redaction. Verification was completed through deterministic CLI and WSGI tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py -q` | 0 | ✅ pass | 2210ms |


## Deviations

None.

## Known Issues

Multi-lane runtime truth is still only available when the active control-plane repository exposes lane-aware runtime state. The existing Postgres mutable-truth control plane remains single-lane, so multi-lane orchestration continues to fail fast against that adapter until a later slice completes the polyglot control-plane migration.

## Files Created/Modified

- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`
- `tests/test_runtime_cli.py`
- `tests/test_dashboard.py`


## Deviations
None.

## Known Issues
Multi-lane runtime truth is still only available when the active control-plane repository exposes lane-aware runtime state. The existing Postgres mutable-truth control plane remains single-lane, so multi-lane orchestration continues to fail fast against that adapter until a later slice completes the polyglot control-plane migration.
