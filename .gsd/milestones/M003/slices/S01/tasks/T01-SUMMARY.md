---
id: T01
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: ["vinted_radar/services/acquisition_benchmark.py", "tests/test_acquisition_benchmark.py", ".gsd/DECISIONS.md"]
key_decisions: ["D049: acquisition benchmark leaderboards rank by net new listings/hour first, then duplicate ratio, challenge rate, degraded count, bytes/new listing, mean CPU, peak RAM, and experiment ID for deterministic ties."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task verification command after fixing repository window loaders to normalize sqlite3.Row values before filtering. The final verification passed: python -m pytest tests/test_acquisition_benchmark.py -q."
completed_at: 2026-04-09T12:04:27.268Z
blocker_discovered: false
---

# T01: Added the acquisition benchmark service contract with repository-window ingestion, explicit score fields, and deterministic leaderboard tests.

> Added the acquisition benchmark service contract with repository-window ingestion, explicit score fields, and deterministic leaderboard tests.

## What Happened
---
id: T01
parent: S01
milestone: M003
key_files:
  - vinted_radar/services/acquisition_benchmark.py
  - tests/test_acquisition_benchmark.py
  - .gsd/DECISIONS.md
key_decisions:
  - D049: acquisition benchmark leaderboards rank by net new listings/hour first, then duplicate ratio, challenge rate, degraded count, bytes/new listing, mean CPU, peak RAM, and experiment ID for deterministic ties.
duration: ""
verification_result: passed
completed_at: 2026-04-09T12:04:27.270Z
blocker_discovered: false
---

# T01: Added the acquisition benchmark service contract with repository-window ingestion, explicit score fields, and deterministic leaderboard tests.

**Added the acquisition benchmark service contract with repository-window ingestion, explicit score fields, and deterministic leaderboard tests.**

## What Happened

Added a new acquisition benchmark service that can collect repository-window facts from discovery runs, catalog scans, and runtime cycles, normalize experiment config and benchmark windows, and combine those facts with storage/resource snapshots. The service computes the scorecard fields required by the slice—net new listings/hour, duplicate ratio, challenge and degraded counts/rates, bytes per new listing, and CPU/RAM summaries—then produces a deterministic leaderboard plus markdown/JSON report outputs. Added tests covering deterministic ranking from synthetic fixtures, repository-backed fact collection from stored SQLite rows, and report persistence.

## Verification

Ran the task verification command after fixing repository window loaders to normalize sqlite3.Row values before filtering. The final verification passed: python -m pytest tests/test_acquisition_benchmark.py -q.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_acquisition_benchmark.py -q` | 0 | ✅ pass | 1474ms |


## Deviations

Added markdown/JSON report writing helpers in the same service so T02 can reuse the exact normalized contract instead of re-deriving leaderboard data in the CLI layer.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/services/acquisition_benchmark.py`
- `tests/test_acquisition_benchmark.py`
- `.gsd/DECISIONS.md`


## Deviations
Added markdown/JSON report writing helpers in the same service so T02 can reuse the exact normalized contract instead of re-deriving leaderboard data in the CLI layer.

## Known Issues
None.
