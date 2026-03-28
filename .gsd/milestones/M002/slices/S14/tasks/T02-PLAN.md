---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Reconciliation + cutover controls

Add reconciliation and cutover controls. Implement row-count/time-window reconciliation across SQLite, PostgreSQL, ClickHouse, and object storage manifests; expose cutover mode in config/health/runtime diagnostics; and make dual-write/read-cutover state explicit so deployment is observable instead of implicit.

## Inputs

- `vinted_radar/services/full_backfill.py`
- `vinted_radar/platform/postgres_repository.py`
- `vinted_radar/platform/clickhouse_ingest.py`

## Expected Output

- `Cross-store reconciliation command`
- `cutover state diagnostics`
- `tests/test_reconciliation.py`

## Verification

python -m pytest tests/test_reconciliation.py -q
