---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T04: Analytical parity + route proof

Prove analytical correctness and performance on the new boundary. Add parity/reconciliation checks between representative SQLite-era outputs and ClickHouse marts during migration, then run focused dashboard/explorer/detail route verification so the cutover path has both correctness and latency evidence.

## Inputs

- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/query/explorer_clickhouse.py`
- `vinted_radar/query/detail_clickhouse.py`

## Expected Output

- `Analytical parity checks`
- `ClickHouse-backed route verification proof`

## Verification

python -m pytest tests/test_clickhouse_parity.py -q
