---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: CLI/runtime cutover to PostgreSQL

Cut the CLI/runtime control surfaces over to PostgreSQL-backed mutable truth. Make runtime-status, pause/resume, controller heartbeats, and discovery bookkeeping resolve through the new PostgreSQL repositories/config while preserving existing JSON/product contracts for later UI slices.

## Inputs

- `vinted_radar/cli.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/platform/postgres_repository.py`

## Expected Output

- `PostgreSQL-backed runtime CLI path`
- `tests/test_runtime_cli_postgres.py`

## Verification

python -m pytest tests/test_runtime_cli_postgres.py -q
