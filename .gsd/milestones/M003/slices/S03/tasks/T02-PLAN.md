---
estimated_steps: 7
estimated_files: 6
skills_used: []
---

# T02: Make storage and identity contracts market-aware

Why: The data model currently assumes one market and can silently collide when another domain reuses IDs or similar URLs.
Do:
- Make hot-path identity and persisted history market-aware in SQLite/current-state paths and the platform projections that acquisition/runtime depend on.
- Add compatibility/backfill logic so existing FR data stays readable and does not require destructive reset unless explicitly chosen.
- Update key uniqueness, foreign keys, and query helpers carefully; treat this as a correctness slice before it is a throughput slice.
Done when:
- Storage-level tests prove market separation and FR compatibility together.

## Inputs

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/platform/postgres_schema/__init__.py`

## Expected Output

- `market-aware storage keys and migrations`
- `tests/test_repository_market_partitioning.py`

## Verification

python -m pytest tests/test_repository_market_partitioning.py tests/test_postgres_backfill.py tests/test_clickhouse_parity.py -q
