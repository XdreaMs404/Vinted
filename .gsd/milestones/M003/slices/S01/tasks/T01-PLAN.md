---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: Define the acquisition benchmark scorecard contract

Why: Later slices need one stable definition of “better”, or the project will regress into intuition-led tuning.
Do:
- Add a benchmark domain/service that normalizes experiment config, run windows, and outcome metrics from discovery runs, catalog scans, runtime cycles, and DB/file growth.
- Define explicit score fields for net new listings per hour, duplicate ratio, challenge/degraded counts, bytes per new listing, and CPU/RAM snapshots.
- Reuse the existing price-filter and long-run audit patterns where they already fit instead of inventing a second reporting style.
Done when:
- The benchmark service can ingest synthetic fixtures and render a deterministic winner table from stored run facts.

## Inputs

- `vinted_radar/price_filter_benchmark.py`
- `vinted_radar/long_run_audit.py`
- `vinted_radar/repository.py`

## Expected Output

- `vinted_radar/services/acquisition_benchmark.py`
- `tests/test_acquisition_benchmark.py`

## Verification

python -m pytest tests/test_acquisition_benchmark.py -q
