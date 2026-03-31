---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T04: Truthful change-fact derivation + replay path

Implement the missing change-fact pipeline instead of approximating marts at query time. Extend the live cutover and historical replay paths so listing-seen/state-refresh batches deterministically produce populated change facts for price deltas, state transitions, engagement shifts, and follow-up miss transitions, then land them in the existing ClickHouse change tables with idempotent replay semantics.

## Inputs

- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/services/projectors.py`
- `vinted_radar/platform/postgres_repository.py`
- `vinted_radar/services/full_backfill.py`
- `infra/clickhouse/migrations/V002__serving_warehouse.sql`

## Expected Output

- `populated live/backfilled change-fact path`
- `idempotent replay coverage for change facts`

## Verification

python -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q
