---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T05: AI-ready feature marts on trustworthy warehouse change facts

Build the deferred AI-ready marts only after the change-fact source exists. Materialize/export listing-day, segment-day, price-change, state-transition, and evidence-pack outputs from ClickHouse rollups plus populated change facts, and keep manifest/window traceability explicit so downstream grounded-intelligence work does not need raw-event rescans.

## Inputs

- `infra/clickhouse/migrations/V002__serving_warehouse.sql`
- `vinted_radar/query/detail_clickhouse.py`
- `vinted_radar/query/explorer_clickhouse.py`
- `vinted_radar/query/overview_clickhouse.py`

## Expected Output

- `feature mart query/export surface`
- `traceable evidence-pack outputs backed by populated warehouse facts`

## Verification

python -m pytest tests/test_feature_marts.py -q
