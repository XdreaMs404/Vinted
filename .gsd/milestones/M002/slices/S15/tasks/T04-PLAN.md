---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T04: Operational closure + final acceptance

Close the migration operationally. Remove heavyweight SQLite history tables from the live runtime path, document the final operating model, and run one last integrated acceptance proving bounded storage, reconciliation health, dashboard/runtime behavior, and evidence drill-down on the new platform.

## Inputs

- `README.md`
- `vinted_radar/platform/health.py`
- `vinted_radar/query/feature_marts.py`

## Expected Output

- `Final operating model docs`
- `integrated platform acceptance proof`

## Verification

python -m pytest tests/test_integrated_platform_acceptance.py -q
