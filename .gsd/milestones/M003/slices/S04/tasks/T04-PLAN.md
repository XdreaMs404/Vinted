---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T04: Run the VPS transport matrix and record the winner

Why: The slice is only complete when the measured transport winner comes from the real VPS, not from local fixture tests.
Do:
- Run a VPS matrix across the main candidate transport recipes for FR and any active extra market.
- Persist artifacts comparing at least concurrency and session behavior variants.
- Select and document the winning recipe to be consumed by later slices.
Done when:
- The repo contains a VPS-backed transport winner artifact that later slices can reference mechanically.

## Inputs

- `scripts/run_vps_benchmark.py`
- `46.225.113.129`

## Expected Output

- `.gsd/milestones/M003/benchmarks/transport-matrix.json`
- `.gsd/milestones/M003/benchmarks/transport-matrix.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile transport-matrix --duration-minutes 120 --output .gsd/milestones/M003/benchmarks/transport-matrix.json --markdown .gsd/milestones/M003/benchmarks/transport-matrix.md
