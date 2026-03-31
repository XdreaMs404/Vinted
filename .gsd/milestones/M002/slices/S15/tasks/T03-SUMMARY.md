---
id: T03
parent: S15
milestone: M002
provides: []
requires: []
affects: []
key_files: ["infra/clickhouse/migrations/V002__serving_warehouse.sql", "vinted_radar/platform/clickhouse_ingest.py", "vinted_radar/services/projectors.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S15/tasks/T03-SUMMARY.md"]
key_decisions: ["Treat the absence of any active change-fact projection/ingest path as a plan-level blocker for S15/T03 rather than shipping query-time approximations that would violate the intended warehouse-materialized contract."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "No task-plan verification command was run. I stopped after proving that the current warehouse contract cannot support the planned price-change and state-transition marts truthfully because the change-fact tables are defined in schema but not populated by the active cutover pipeline."
completed_at: 2026-03-31T15:06:50.578Z
blocker_discovered: true
---

# T03: Documented that S15/T03 is blocked because the current ClickHouse cutover path never populates change facts required for price-change and state-transition marts.

> Documented that S15/T03 is blocked because the current ClickHouse cutover path never populates change facts required for price-change and state-transition marts.

## What Happened
---
id: T03
parent: S15
milestone: M002
key_files:
  - infra/clickhouse/migrations/V002__serving_warehouse.sql
  - vinted_radar/platform/clickhouse_ingest.py
  - vinted_radar/services/projectors.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S15/tasks/T03-SUMMARY.md
key_decisions:
  - Treat the absence of any active change-fact projection/ingest path as a plan-level blocker for S15/T03 rather than shipping query-time approximations that would violate the intended warehouse-materialized contract.
duration: ""
verification_result: untested
completed_at: 2026-03-31T15:06:50.578Z
blocker_discovered: true
---

# T03: Documented that S15/T03 is blocked because the current ClickHouse cutover path never populates change facts required for price-change and state-transition marts.

**Documented that S15/T03 is blocked because the current ClickHouse cutover path never populates change facts required for price-change and state-transition marts.**

## What Happened

I halted execution after validating a plan-level mismatch in the current warehouse contract. ClickHouse V002 defines `fact_listing_change_events` and `serving_listing_latest_change`, but the active cutover path only ingests listing-seen and probe batches: `vinted_radar/platform/clickhouse_ingest.py` maps `vinted.discovery.listing-seen.batch` to `fact_listing_seen_events` and `vinted.state-refresh.probe.batch` to `fact_listing_probe_events`, and `vinted_radar/services/projectors.py` likewise only projects listing-seen and probe batches into PostgreSQL mutable truth. No live producer, projector, or ingest path currently emits ClickHouse change events. That makes the written task invalid as stated for the price-change and state-transition mart outputs. I recorded the mismatch in `.gsd/KNOWLEDGE.md` and wrote a blocker-oriented task summary with concrete resume guidance instead of shipping an unplanned approximation.

## Verification

No task-plan verification command was run. I stopped after proving that the current warehouse contract cannot support the planned price-change and state-transition marts truthfully because the change-fact tables are defined in schema but not populated by the active cutover pipeline.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| — | No verification commands discovered | — | — | — |


## Deviations

Stopped before implementation because local validation showed the current ClickHouse cutover path does not populate change facts, making the written mart contract invalid for price-change and state-transition outputs.

## Known Issues

The current warehouse can support listing/day and segment/day style marts from existing rollups, but it cannot truthfully support warehouse-materialized price-change and state-transition marts until a populated change-event source exists or the task is explicitly re-scoped.

## Files Created/Modified

- `infra/clickhouse/migrations/V002__serving_warehouse.sql`
- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/services/projectors.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S15/tasks/T03-SUMMARY.md`


## Deviations
Stopped before implementation because local validation showed the current ClickHouse cutover path does not populate change facts, making the written mart contract invalid for price-change and state-transition outputs.

## Known Issues
The current warehouse can support listing/day and segment/day style marts from existing rollups, but it cannot truthfully support warehouse-materialized price-change and state-transition marts until a populated change-event source exists or the task is explicitly re-scoped.
