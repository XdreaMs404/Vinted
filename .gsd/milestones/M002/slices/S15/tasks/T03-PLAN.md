---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: AI-ready feature + evidence marts

Build AI-ready feature and evidence marts on top of the cut-over warehouse. Materialize listing/day, segment/day, price-change, state-transition, and evidence-pack style outputs that future grounded AI and product-level intelligence can consume without scanning raw events, while preserving traceability back to manifests and observed windows.

## Inputs

- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/query/explorer_clickhouse.py`
- `vinted_radar/query/detail_clickhouse.py`
- `.gsd/REQUIREMENTS.md`

## Expected Output

- `AI-ready feature marts`
- `tests/test_feature_marts.py`

## Verification

python -m pytest tests/test_feature_marts.py -q
