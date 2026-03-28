---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T04: Live cutover proof + runbook

Prove the cut-over platform in a real live-cycle acceptance flow. Run a narrow but real collector cycle on PostgreSQL + ClickHouse + object storage, verify dashboard/runtime/health/browser behavior on that stack, and document the exact operational sequence for production cutover and rollback on the VPS.

## Inputs

- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`
- `README.md`

## Expected Output

- `Live cutover smoke proof`
- `production cutover + rollback runbook`

## Verification

python -m pytest tests/test_cutover_smoke.py -q
