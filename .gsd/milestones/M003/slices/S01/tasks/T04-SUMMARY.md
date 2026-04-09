---
id: T04
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: ["scripts/run_vps_benchmark.py", "tests/test_vps_benchmark_runner.py", ".gsd/milestones/M003/benchmarks/baseline-fr-page1.json", ".gsd/milestones/M003/benchmarks/baseline-fr-page1.md", ".gsd/milestones/M003/M003-RESEARCH.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["D052: auto-load .env.vps SSH defaults/askpass and upload the remote experiment helper as a temporary file instead of inlining multiline Python through ssh -c."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Verified the runner changes with `python -m pytest tests/test_vps_benchmark_runner.py -q`, which passed. Then ran the real task-plan command `python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 90 --output .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/baseline-fr-page1.md`. That live benchmark command exited non-zero because the remote batch process could not import `typer`, but it still wrote the durable baseline JSON/Markdown artifacts and captured the failing stderr plus preserved service/resource/storage state."
completed_at: 2026-04-09T13:02:54.697Z
blocker_discovered: false
---

# T04: Captured the real VPS baseline artifact and hardened the benchmark runner for unattended SSH execution.

> Captured the real VPS baseline artifact and hardened the benchmark runner for unattended SSH execution.

## What Happened
---
id: T04
parent: S01
milestone: M003
key_files:
  - scripts/run_vps_benchmark.py
  - tests/test_vps_benchmark_runner.py
  - .gsd/milestones/M003/benchmarks/baseline-fr-page1.json
  - .gsd/milestones/M003/benchmarks/baseline-fr-page1.md
  - .gsd/milestones/M003/M003-RESEARCH.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D052: auto-load .env.vps SSH defaults/askpass and upload the remote experiment helper as a temporary file instead of inlining multiline Python through ssh -c.
duration: ""
verification_result: mixed
completed_at: 2026-04-09T13:02:54.698Z
blocker_discovered: false
---

# T04: Captured the real VPS baseline artifact and hardened the benchmark runner for unattended SSH execution.

**Captured the real VPS baseline artifact and hardened the benchmark runner for unattended SSH execution.**

## What Happened

Updated `scripts/run_vps_benchmark.py` so the plain task-plan command can run non-interactively from this workstation by auto-loading `.env.vps` SSH defaults/askpass settings, propagating the configured identity file into both SSH and SCP calls, and uploading the remote experiment helper as a temporary script instead of trying to inline multiline Python through `ssh -c`. Added focused regression coverage in `tests/test_vps_benchmark_runner.py` for both the `.env.vps` transport loading path and the uploaded remote-script execution path. Then executed the real task-plan benchmark command against `46.225.113.129` and persisted the durable named artifacts at `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json` and `.gsd/milestones/M003/benchmarks/baseline-fr-page1.md`. The capture reached the VPS, preserved live service posture, snapshotted the working SQLite database, and recorded a truthful current baseline floor: the first bounded cycle failed immediately because the remote host's bare `python3 -m vinted_radar.cli batch ...` path raised `ModuleNotFoundError: No module named 'typer'`. Appended that measured baseline finding to `.gsd/milestones/M003/M003-RESEARCH.md`, recorded the runner transport choice as D052, and added a knowledge note that future live VPS benchmarks should use `--remote-python /root/Vinted/venv/bin/python` (or install `typer` into the host `python3`) before expecting long windows to run successfully.

## Verification

Verified the runner changes with `python -m pytest tests/test_vps_benchmark_runner.py -q`, which passed. Then ran the real task-plan command `python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 90 --output .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/baseline-fr-page1.md`. That live benchmark command exited non-zero because the remote batch process could not import `typer`, but it still wrote the durable baseline JSON/Markdown artifacts and captured the failing stderr plus preserved service/resource/storage state.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_vps_benchmark_runner.py -q` | 0 | ✅ pass | 4263ms |
| 2 | `python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 90 --output .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/baseline-fr-page1.md` | 1 | ❌ fail | 230440ms |


## Deviations

The written task plan expected a 90-minute comparable run window, but the live VPS profile failed in the first bounded cycle because the host `python3` environment is missing `typer`. I treated that saved failure bundle as the truthful current baseline floor and documented the limitation in the milestone research artifact instead of fabricating a healthy long-window measurement.

## Known Issues

The current live benchmark still depends on the remote Python interpreter path. On 46.225.113.129, bare `python3 -m vinted_radar.cli ...` fails before acquisition begins; future live benchmark captures should use `/root/Vinted/venv/bin/python` or repair the host `python3` environment.

## Files Created/Modified

- `scripts/run_vps_benchmark.py`
- `tests/test_vps_benchmark_runner.py`
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json`
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.md`
- `.gsd/milestones/M003/M003-RESEARCH.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
The written task plan expected a 90-minute comparable run window, but the live VPS profile failed in the first bounded cycle because the host `python3` environment is missing `typer`. I treated that saved failure bundle as the truthful current baseline floor and documented the limitation in the milestone research artifact instead of fabricating a healthy long-window measurement.

## Known Issues
The current live benchmark still depends on the remote Python interpreter path. On 46.225.113.129, bare `python3 -m vinted_radar.cli ...` fails before acquisition begins; future live benchmark captures should use `/root/Vinted/venv/bin/python` or repair the host `python3` environment.
