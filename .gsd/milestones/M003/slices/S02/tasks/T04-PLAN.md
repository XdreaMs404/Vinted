---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T04: Prove the lane runtime on the VPS

Why: The slice is not retired until the runtime contract survives on the real VPS.
Do:
- Run a bounded dual-lane smoke on the VPS using conservative frontier + expansion configs.
- Verify that `/runtime`, `/api/runtime`, `/health`, and the benchmark artifact bundle all stay truthful while both lanes run.
- Record any operator-facing surprises before later slices build on the lane model.
Done when:
- The repo has a VPS smoke artifact proving real dual-lane operation and healthy serving/runtime surfaces.

## Inputs

- `scripts/run_vps_benchmark.py`
- `http://46.225.113.129:8765`

## Expected Output

- `.gsd/milestones/M003/benchmarks/dual-lane-smoke.json`
- `.gsd/milestones/M003/benchmarks/dual-lane-smoke.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile dual-lane-smoke --duration-minutes 30 --verify-base-url http://46.225.113.129:8765 --output .gsd/milestones/M003/benchmarks/dual-lane-smoke.json --markdown .gsd/milestones/M003/benchmarks/dual-lane-smoke.md
