---
id: T02
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: ["vinted_radar/cli.py", "vinted_radar/services/acquisition_benchmark.py", "tests/test_acquisition_benchmark.py", "tests/test_acquisition_benchmark_cli.py", "README.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["D050: Use repeatable JSON spec files as the acquisition benchmark CLI input, resolve each spec's db_path relative to the spec file, and redact proxy URLs plus secret-shaped config keys before printing or writing benchmark reports."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task verification command after implementing the CLI commands, report redaction helpers, richer markdown rendering, and the new CLI test file. The command passed cleanly and exercised both the acquisition benchmark service contract and the new operator-facing CLI/report flow: python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py -q."
completed_at: 2026-04-09T12:20:33.495Z
blocker_discovered: false
---

# T02: Added acquisition benchmark CLI commands that build redacted leaderboard artifacts from spec files or saved experiment bundles.

> Added acquisition benchmark CLI commands that build redacted leaderboard artifacts from spec files or saved experiment bundles.

## What Happened
---
id: T02
parent: S01
milestone: M003
key_files:
  - vinted_radar/cli.py
  - vinted_radar/services/acquisition_benchmark.py
  - tests/test_acquisition_benchmark.py
  - tests/test_acquisition_benchmark_cli.py
  - README.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D050: Use repeatable JSON spec files as the acquisition benchmark CLI input, resolve each spec's db_path relative to the spec file, and redact proxy URLs plus secret-shaped config keys before printing or writing benchmark reports.
duration: ""
verification_result: passed
completed_at: 2026-04-09T12:20:33.495Z
blocker_discovered: false
---

# T02: Added acquisition benchmark CLI commands that build redacted leaderboard artifacts from spec files or saved experiment bundles.

**Added acquisition benchmark CLI commands that build redacted leaderboard artifacts from spec files or saved experiment bundles.**

## What Happened

Extended the acquisition benchmark service so reports now carry a summary block with compared profiles and an explicit winner_reason, render richer markdown that explains the methodology and why the winner ranked first, and run a redaction pass that masks proxy credentials, DSNs, and secret-shaped config values before anything is printed or persisted. Added two Typer entrypoints in vinted_radar/cli.py: acquisition-benchmark builds a report from repeatable JSON spec files, writes JSON/Markdown artifacts, and prints a safe leaderboard with explicit artifact paths; acquisition-benchmark-report reads either a saved report or a raw experiment bundle and re-renders the same report surfaces. Added focused CLI tests for spec loading, relative db_path resolution, artifact writing, winner explanation output, and credential redaction, expanded the existing service test to cover the richer summary/markdown contract, documented the operator flow in README.md, and recorded the downstream-facing CLI contract as D050 plus a knowledge note about portable relative db_path handling.

## Verification

Ran the task verification command after implementing the CLI commands, report redaction helpers, richer markdown rendering, and the new CLI test file. The command passed cleanly and exercised both the acquisition benchmark service contract and the new operator-facing CLI/report flow: python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py -q.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_acquisition_benchmark.py tests/test_acquisition_benchmark_cli.py -q` | 0 | ✅ pass | 1799ms |


## Deviations

Added a second CLI command (`acquisition-benchmark-report`) so saved benchmark payloads and raw experiment bundles can be inspected or re-rendered without rebuilding them from scratch, and documented the JSON spec-file contract in `README.md` for downstream automation.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/cli.py`
- `vinted_radar/services/acquisition_benchmark.py`
- `tests/test_acquisition_benchmark.py`
- `tests/test_acquisition_benchmark_cli.py`
- `README.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Added a second CLI command (`acquisition-benchmark-report`) so saved benchmark payloads and raw experiment bundles can be inspected or re-rendered without rebuilding them from scratch, and documented the JSON spec-file contract in `README.md` for downstream automation.

## Known Issues
None.
