---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T04: Backfill + PostgreSQL control-plane smoke

Backfill and prove one real control-plane run on PostgreSQL. Add a controlled SQLite-to-PostgreSQL backfill for runtime/discovery/catalog/current-state data, then run a narrow batch/continuous smoke against PostgreSQL-backed mutable truth and assert that runtime-status and bookkeeping stay correct without SQLite mutation writes.

## Inputs

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/platform/postgres_repository.py`

## Expected Output

- `SQLite-to-PostgreSQL backfill command`
- `collector smoke proof on PostgreSQL`

## Verification

python -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py -q
