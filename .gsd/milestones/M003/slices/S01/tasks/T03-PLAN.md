---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T03: Build the VPS experiment runner and artifact bundle flow

Why: The user explicitly wants the system to test itself on the real VPS, not rely on copied shell output.
Do:
- Create a remote benchmark runner script that connects to the VPS, launches bounded experiments with safe configs, collects resulting DB/metric snapshots, and writes local JSON/Markdown artifacts under `.gsd/milestones/M003/benchmarks/`.
- Ensure the runner can preserve the live service posture when required and can label destructive vs non-destructive modes clearly.
- Include resource snapshots (`ps`, `vmstat`, disk growth) in the collected artifact bundle.
Done when:
- One script can drive a bounded VPS experiment end to end and leave a reproducible artifact bundle behind.

## Inputs

- `scripts/verify_vps_serving.py`
- `.gsd/milestones/M002/M002-VPS-SHADOW-ASSESSMENT.md`

## Expected Output

- `scripts/run_vps_benchmark.py`
- `tests/test_vps_benchmark_runner.py`

## Verification

python -m pytest tests/test_vps_benchmark_runner.py -q
