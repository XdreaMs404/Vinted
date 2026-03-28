---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: ClickHouse fact + rollup schema

Design the ClickHouse analytical schema. Add raw fact tables for listing-seen events, probe events, and derived change events; define partitions/order keys and TTL policy; and create the first materialized views/rollups for listing-hourly/daily, category/brand daily metrics, and other serving primitives the product needs.

## Inputs

- `vinted_radar/repository.py`
- `vinted_radar/dashboard.py`
- `.gsd/DECISIONS.md`

## Expected Output

- `ClickHouse schema + materialized views`
- `tests/test_clickhouse_schema.py`

## Verification

python -m pytest tests/test_clickhouse_schema.py -q
