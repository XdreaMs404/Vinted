---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T03: End-to-end application cutover

Cut product and operator reads/writes over to the new platform. Switch dashboard, CLI, runtime status, health, and collector write paths so the live app resolves mutable truth from PostgreSQL, analytics from ClickHouse, and proof from manifests/object storage, while preserving existing user-visible contracts and adding an emergency fallback path only as a temporary migration safety valve.

## Inputs

- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/query/explorer_clickhouse.py`
- `vinted_radar/query/detail_clickhouse.py`
- `vinted_radar/platform/postgres_repository.py`

## Expected Output

- `New platform default read/write path`
- `browser/CLI route proofs on cut-over stack`

## Verification

python -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q
