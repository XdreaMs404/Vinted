---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T04: Run a real cross-market smoke benchmark on the VPS

Why: The slice only retires once cross-market ingestion runs on the real VPS.
Do:
- Benchmark a conservative cross-market smoke profile on the VPS (FR + one additional market) using the new registry and identity contracts.
- Verify that artifacts, runtime surfaces, and stored data stay partitioned by market.
- Record additive yield and any domain-specific failures for later transport/frontier work.
Done when:
- The milestone has a real VPS artifact showing safe multi-market ingestion without identity mixing.

## Inputs

- `scripts/run_vps_benchmark.py`
- `46.225.113.129`

## Expected Output

- `.gsd/milestones/M003/benchmarks/cross-market-smoke.json`
- `.gsd/milestones/M003/benchmarks/cross-market-smoke.md`

## Verification

python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile cross-market-smoke --duration-minutes 60 --output .gsd/milestones/M003/benchmarks/cross-market-smoke.json --markdown .gsd/milestones/M003/benchmarks/cross-market-smoke.md
