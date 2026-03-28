---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T03: Product query adapters on ClickHouse

Build ClickHouse-backed analytical query adapters for overview, explorer, and detail. Move the heavy read paths out of the SQLite-oriented repository by introducing dedicated ClickHouse query modules and product-facing adapters that preserve existing payload/drill-down contracts while sourcing their aggregates and listing sets from ClickHouse.

## Inputs

- `vinted_radar/dashboard.py`
- `vinted_radar/repository.py`
- `tests/test_dashboard.py`

## Expected Output

- `ClickHouse-backed overview/explorer/detail query layer`
- `tests/test_clickhouse_queries.py`
- `route contract tests`

## Verification

python -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q
