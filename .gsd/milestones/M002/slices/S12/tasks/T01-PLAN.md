---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: PostgreSQL mutable schema

Design and migrate the PostgreSQL control-plane/current-state schema. Create versioned PostgreSQL tables for runtime controller state, runtime cycles, discovery runs, catalogs, listing identity/current state, recent presence summaries, manifests, and outbox checkpoints, with explicit keys and indexes for idempotent projectors and operational queries.

## Inputs

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/cli.py`

## Expected Output

- `PostgreSQL schema migrations for mutable truth`
- `tests/test_postgres_schema.py`

## Verification

python -m pytest tests/test_postgres_schema.py -q
