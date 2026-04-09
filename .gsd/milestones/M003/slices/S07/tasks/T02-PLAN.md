---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T02: Deploy and soak the production-candidate profile on the VPS

Why: The milestone only matters if the real VPS runs the chosen profile successfully.
Do:
- Deploy the chosen profile to the VPS, restart only the affected services, and preserve backups/rollback points.
- Run a guarded production-candidate soak long enough to collect meaningful benchmark/storage/runtime evidence.
- Keep the public product surfaces under verification during the soak rather than checking them only at the end.
Done when:
- The VPS is running the candidate profile and the soak artifact shows stable collector + serving health.

## Inputs

- `scripts/run_vps_benchmark.py`
- `http://46.225.113.129:8765`

## Expected Output

- `.gsd/milestones/M003/benchmarks/production-candidate-soak.json`
- `.gsd/milestones/M003/benchmarks/production-candidate-soak.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile production-candidate-soak --duration-minutes 480 --verify-base-url http://46.225.113.129:8765 --output .gsd/milestones/M003/benchmarks/production-candidate-soak.json --markdown .gsd/milestones/M003/benchmarks/production-candidate-soak.md
