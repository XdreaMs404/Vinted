---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: Historical backfill pipeline

Build the full historical backfill pipeline. Add commands/workers that migrate legacy SQLite discovery, observation, probe, and runtime history into PostgreSQL current-state/control-plane rows, ClickHouse facts/rollups, and Parquet evidence manifests, with resumable checkpoints and dry-run support for large corpora.

## Inputs

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/platform/postgres_repository.py`
- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/platform/lake_writer.py`

## Expected Output

- `Full SQLite migration/backfill pipeline`
- `tests/test_full_backfill.py`

## Verification

python -m pytest tests/test_full_backfill.py -q
