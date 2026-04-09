---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T04: Prove lower storage growth on the VPS

Why: The storage slice only matters if the real VPS profile gets cheaper in practice, not just in unit tests.
Do:
- Run a controlled VPS soak comparing the selected strategy before and after compaction/retention changes.
- Record DB growth, bytes per new listing, and any evidence/product regressions.
- Persist the comparison artifact for the final rollout decision.
Done when:
- The milestone has a VPS storage comparison artifact showing materially improved per-discovery cost.

## Inputs

- `scripts/run_vps_benchmark.py`
- `.gsd/milestones/M003/benchmarks/cross-market-frontier-winner.json`

## Expected Output

- `.gsd/milestones/M003/benchmarks/storage-compare.json`
- `.gsd/milestones/M003/benchmarks/storage-compare.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile storage-compare --duration-minutes 180 --output .gsd/milestones/M003/benchmarks/storage-compare.json --markdown .gsd/milestones/M003/benchmarks/storage-compare.md
