---
id: T03
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: ["scripts/run_vps_benchmark.py", "tests/test_vps_benchmark_runner.py", ".gsd/milestones/M003/benchmarks/.gitkeep", "python3.cmd", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["D051: Default the VPS benchmark runner to preserve-live mode, which snapshots the live SQLite DB on the VPS, runs bounded batch cycles against the snapshot, and labels live-db runs as destructive."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the new task deliverable directly with the task-plan command and then reran the nearby runtime/schema regression suites to confirm the new runner and shim did not break the existing acquisition/runtime substrate. The final combined regression pass was clean."
completed_at: 2026-04-09T12:33:39.449Z
blocker_discovered: false
---

# T03: Added a VPS benchmark runner that snapshots the live DB safely, executes bounded remote acquisition cycles, and emits local benchmark bundles with resource evidence.

> Added a VPS benchmark runner that snapshots the live DB safely, executes bounded remote acquisition cycles, and emits local benchmark bundles with resource evidence.

## What Happened
---
id: T03
parent: S01
milestone: M003
key_files:
  - scripts/run_vps_benchmark.py
  - tests/test_vps_benchmark_runner.py
  - .gsd/milestones/M003/benchmarks/.gitkeep
  - python3.cmd
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D051: Default the VPS benchmark runner to preserve-live mode, which snapshots the live SQLite DB on the VPS, runs bounded batch cycles against the snapshot, and labels live-db runs as destructive.
duration: ""
verification_result: passed
completed_at: 2026-04-09T12:33:39.450Z
blocker_discovered: false
---

# T03: Added a VPS benchmark runner that snapshots the live DB safely, executes bounded remote acquisition cycles, and emits local benchmark bundles with resource evidence.

**Added a VPS benchmark runner that snapshots the live DB safely, executes bounded remote acquisition cycles, and emits local benchmark bundles with resource evidence.**

## What Happened

Built `scripts/run_vps_benchmark.py` as the missing VPS experiment harness for M003. The script now connects to the VPS over SSH, resolves a named benchmark profile, and runs bounded acquisition experiments through the real `python -m vinted_radar.cli batch` path on the remote host. By default it uses the new `preserve-live` posture: it creates a temporary SQLite snapshot on the VPS, runs the bounded experiment against that snapshot, captures pre/post service posture, DB growth, and resource evidence, exports a final remote SQLite snapshot, copies that snapshot locally, and derives the normalized acquisition benchmark report from the copied DB with the existing benchmark service contract. It also supports an explicit `live-db` mode and persists clear destructive/non-destructive labeling in the artifact bundle and markdown summary.

Added `tests/test_vps_benchmark_runner.py` to cover the new default non-destructive flow, the destructive `live-db` labeling/keep-remote-snapshot path, and the failure-path behavior where the runner still writes a durable local bundle even when a remote batch cycle returns non-zero. Added `.gsd/milestones/M003/benchmarks/.gitkeep` so the artifact directory is present in the repo, recorded D051 for the default preserve-live posture, and added a workstation knowledge note plus a repo-local `python3.cmd` shim because the prior auto-gate failed on this Windows machine by resolving `python3` to a broken app alias instead of a usable interpreter.

## Verification

Verified the new task deliverable directly with the task-plan command and then reran the nearby runtime/schema regression suites to confirm the new runner and shim did not break the existing acquisition/runtime substrate. The final combined regression pass was clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_vps_benchmark_runner.py -q` | 0 | ✅ pass | 1950ms |
| 2 | `python -m pytest tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_schema.py -q` | 0 | ✅ pass | 3354ms |
| 3 | `python -m pytest tests/test_vps_benchmark_runner.py tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_schema.py -q` | 0 | ✅ pass | 1790ms |


## Deviations

Added a repo-local `python3.cmd` shim and a corresponding knowledge note because the triggering verification failure was environmental on this Windows workstation (`python3` resolved to a broken app alias) rather than a code regression. This was outside the narrow task-plan file list but necessary to keep auto-mode verification portable here.

## Known Issues

None.

## Files Created/Modified

- `scripts/run_vps_benchmark.py`
- `tests/test_vps_benchmark_runner.py`
- `.gsd/milestones/M003/benchmarks/.gitkeep`
- `python3.cmd`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Added a repo-local `python3.cmd` shim and a corresponding knowledge note because the triggering verification failure was environmental on this Windows workstation (`python3` resolved to a broken app alias) rather than a code regression. This was outside the narrow task-plan file list but necessary to keep auto-mode verification portable here.

## Known Issues
None.
