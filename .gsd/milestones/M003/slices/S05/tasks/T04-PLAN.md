---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T04: Select the cross-market production-candidate acquisition strategy

Why: The user wants the best system possible, which may require combining FR optimization with additional markets where the marginal yield is strong.
Do:
- Run a cross-market additive benchmark using the adaptive planner and the transport winners from S04.
- Compare the chosen multi-market candidate against the FR-only winner on discoveries, duplicates, challenge rate, and resource/storage cost.
- Select the production-candidate strategy that later slices must optimize for storage and rollout.
Done when:
- A benchmark artifact names the current best acquisition strategy across FR and extra-market options.

## Inputs

- `scripts/run_vps_benchmark.py`
- `.gsd/milestones/M003/benchmarks/transport-matrix.json`

## Expected Output

- `.gsd/milestones/M003/benchmarks/cross-market-frontier-winner.json`
- `.gsd/milestones/M003/benchmarks/cross-market-frontier-winner.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile cross-market-frontier-winner --duration-minutes 180 --output .gsd/milestones/M003/benchmarks/cross-market-frontier-winner.json --markdown .gsd/milestones/M003/benchmarks/cross-market-frontier-winner.md
