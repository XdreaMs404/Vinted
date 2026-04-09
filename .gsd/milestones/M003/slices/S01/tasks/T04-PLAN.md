---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T04: Capture the real VPS baseline benchmark

Why: The milestone needs a real baseline floor before any optimization claims can be judged.
Do:
- Use the new runner to benchmark the current FR `page_limit=1` production-like profile on the real VPS.
- Persist the JSON/Markdown outputs under `.gsd/milestones/M003/benchmarks/` and summarize the baseline in the milestone research artifact.
- Capture enough window length to normalize run cadence, duplicates, challenge pressure, and storage growth.
Done when:
- The repo contains a durable baseline artifact future slices can compare against mechanically.

## Inputs

- `scripts/run_vps_benchmark.py`
- `46.225.113.129`

## Expected Output

- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json`
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.md`
- `.gsd/milestones/M003/M003-RESEARCH.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile baseline-fr-page1 --duration-minutes 90 --output .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --markdown .gsd/milestones/M003/benchmarks/baseline-fr-page1.md
