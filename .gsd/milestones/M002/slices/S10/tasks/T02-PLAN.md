---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T02: Bootstrap stack + migration runners

Introduce provider bootstrap and migration runners. Add versioned SQL migration directories for PostgreSQL and ClickHouse, local compose/bootstrap helpers for PostgreSQL + ClickHouse + MinIO, and CLI doctor/bootstrap commands that validate connectivity, schema version, and writable object-store prefixes.

## Inputs

- `README.md`
- `vinted_radar/cli.py`
- `vinted_radar/db.py`

## Expected Output

- `infra/docker-compose.data-platform.yml`
- `vinted_radar/platform/migrations.py`
- `tests/test_data_platform_bootstrap.py`

## Verification

python -m pytest tests/test_data_platform_bootstrap.py -q
