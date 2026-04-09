---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T03: Benchmark FR fixed-depth versus adaptive frontier on the VPS

Why: The first hard proof target is beating the current FR loop, because that baseline is already measured and operationally relevant.
Do:
- Run a VPS benchmark comparing the old FR page-1 loop, one or more fixed deeper profiles, and the adaptive FR planner.
- Persist artifacts that show the winner on net useful yield, not only raw request volume.
- Keep the comparison apples-to-apples on duration and benchmark methodology.
Done when:
- The milestone has a real FR benchmark artifact proving whether adaptive depth beats the current baseline.

## Inputs

- `scripts/run_vps_benchmark.py`
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json`

## Expected Output

- `.gsd/milestones/M003/benchmarks/fr-frontier-comparison.json`
- `.gsd/milestones/M003/benchmarks/fr-frontier-comparison.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile fr-frontier-comparison --duration-minutes 180 --output .gsd/milestones/M003/benchmarks/fr-frontier-comparison.json --markdown .gsd/milestones/M003/benchmarks/fr-frontier-comparison.md
