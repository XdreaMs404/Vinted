---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: Instrument storage-growth and bytes-per-new-listing audits

Why: Storage work is blind unless the system can attribute growth to concrete tables, payload paths, and per-discovery cost.
Do:
- Add storage-growth audit helpers that measure DB/table/index growth, bytes per run, and bytes per new listing.
- Make the benchmark/reporting pipeline ingest these metrics automatically.
- Keep the audit usable both locally and against VPS snapshots.
Done when:
- Automated tests can compute table-growth attribution and bytes-per-new-listing from fixture snapshots.

## Inputs

- `vinted_radar/long_run_audit.py`
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json`

## Expected Output

- `storage audit helpers`
- `tests/test_storage_audit.py`

## Verification

python -m pytest tests/test_storage_audit.py tests/test_long_run_audit.py -q
