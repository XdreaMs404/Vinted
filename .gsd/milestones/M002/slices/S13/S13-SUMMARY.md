---
id: S13
parent: M002
milestone: M002
provides:
  - A ClickHouse V002 serving warehouse with append-only listing-seen/probe facts, long-lived rollups, latest-per-listing serving tables, and materialized-view wiring.
  - A replay-safe outbox-to-ClickHouse ingest worker with checkpoint, lag, and failure state that operators and downstream cutover work can inspect.
  - A repository-shaped ClickHouse product-query adapter that preserves overview, explorer, and listing-detail route contracts while sourcing analytics from ClickHouse.
  - A reusable route-parity verifier and backend-shape normalization rule for SQLite-to-ClickHouse analytical cutover.
requires:
  - slice: S10
    provides: The PostgreSQL/ClickHouse/S3 platform foundation, versioned migrations, shared config, and outbox/bootstrap seams that S13 extends for serving analytics.
  - slice: S11
    provides: The manifested parquet evidence-lake contract that S13 ingests into ClickHouse instead of inventing a second raw-evidence format.
  - slice: S12
    provides: The PostgreSQL mutable-truth and outbox-checkpoint seams that S13 reuses for serving-ingest checkpoint state and future application cutover.
affects:
  - M002/S14
  - M002/S15
  - M003
key_files:
  - infra/clickhouse/migrations/V002__serving_warehouse.sql
  - vinted_radar/platform/clickhouse_schema/__init__.py
  - vinted_radar/platform/clickhouse_ingest.py
  - vinted_radar/cli.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/query/explorer_clickhouse.py
  - vinted_radar/query/detail_clickhouse.py
  - vinted_radar/dashboard.py
  - scripts/verify_clickhouse_routes.py
  - tests/clickhouse_product_test_support.py
  - tests/test_clickhouse_schema.py
  - tests/test_clickhouse_ingest.py
  - tests/test_clickhouse_queries.py
  - tests/test_dashboard.py
  - tests/test_clickhouse_parity.py
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D047 — use 730-day raw fact TTL, 3650-day serving rollups, and latest-per-listing serving tables fed by materialized views.
  - D048 — use deterministic row-level fact ids plus source-event lookups so ClickHouse ingest inserts only missing rows on retries and partial replays.
  - D051 — switch dashboard product reads through a repository-shaped ClickHouse adapter so route payload builders stay stable during cutover.
  - D052 — normalize probe presentation at the dashboard serialization and route-proof layer instead of forcing every backend to emit the repository’s flat row shape.
patterns_established:
  - Use deterministic row-level ids plus source-event lookups to make ClickHouse fact ingest replay-safe across outbox retries and partial batch writes.
  - Preserve existing dashboard/explorer/detail payload builders by introducing a repository-shaped ClickHouse adapter instead of rewriting product routes during cutover.
  - Normalize backend-specific row-shape differences at the dashboard serialization boundary and prove parity with a reusable route verifier rather than coupling every backend to one internal row layout.
observability_surfaces:
  - `python3 -m vinted_radar.cli clickhouse-ingest`
  - `python3 -m vinted_radar.cli clickhouse-ingest-status --format json`
  - `python3 scripts/verify_clickhouse_routes.py --db-path <sqlite.db> --listing-id <id> --json`
  - `/api/dashboard` → `request.primary_payload_source`
  - `python3 -m pytest tests/test_clickhouse_parity.py -q`
drill_down_paths:
  - .gsd/milestones/M002/slices/S13/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S13/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S13/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S13/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T11:47:34.383Z
blocker_discovered: false
---

# S13: ClickHouse Serving Warehouse + Rollups

**S13 established the ClickHouse serving warehouse, replay-safe serving ingest, and a repository-shaped analytical read path so overview, explorer, and listing detail can move off SQLite full-history scans without changing dashboard contracts.**

## What Happened

S13 completed the analytical serving boundary that S10 through S12 prepared. T01 introduced ClickHouse schema V002 with append-only `fact_listing_seen_events` and `fact_listing_probe_events`, long-lived hourly/daily/category/brand rollups, latest-per-listing serving tables, monthly partitions, and explicit retention rules (730-day raw TTL and 3650-day rollup retention). That gave the milestone a real serving warehouse shape instead of another SQLite-era historical scan path.

T02 then connected the warehouse to the platform event pipeline. `ClickHouseIngestService` now claims ClickHouse outbox rows, loads manifested parquet batches from the lake, maps discovery and probe batches into ClickHouse facts, and records checkpoint/lag/error state back into PostgreSQL outbox checkpoints. The important cutover pattern here is replay safety: each fact row gets a deterministic row-level event id derived from source batch identity plus row identity, and the ingester queries existing `source_event_id` rows before inserting so partial replays only add missing rows.

T03 moved the heavy product read path behind a repository-shaped ClickHouse adapter instead of rewriting the dashboard layer. `ClickHouseProductQueryAdapter` now exposes overview snapshot, explorer snapshot, listing pages, listing state inputs, listing history, and peer-price lookups over ClickHouse facts/latest-serving tables while delegating runtime and coverage truth to the existing repository boundary. `DashboardApplication` can therefore preserve the same route and payload contracts while surfacing which backend served the request through `request.primary_payload_source`.

T04 closed the slice with parity proof and diagnostic tooling. `scripts/verify_clickhouse_routes.py` starts temporary repository-backed and ClickHouse-backed dashboard servers, verifies representative overview/explorer/detail/health JSON parity after contract normalization, checks ClickHouse HTML routes, and records route latency. The dashboard serialization layer was also hardened to normalize backend-specific probe row shapes so the public product contract stays stable even when the ClickHouse adapter returns nested `latest_probe` evidence instead of the repository’s older flat columns.

After S13, the repo now has the serving warehouse, the replay-safe ingest seam, the product-query adapter, and the parity verifier that S14 can rely on during historical backfill and live application cutover. Downstream slices should treat ClickHouse as the analytical serving boundary and extend these seams rather than adding new SQLite-side full-history shortcuts.

### Operational Readiness (Q8)
- **Health signal:** `python3 -m vinted_radar.cli clickhouse-ingest-status --format json` exposes checkpoint existence, status, lag seconds, last outbox/event/manifest ids, and target-table metadata; `/api/dashboard` exposes `request.primary_payload_source`; and `python3 scripts/verify_clickhouse_routes.py --db-path <sqlite.db> --listing-id <id> --json` returns parity plus route-latency proof.
- **Failure signal:** serving ingest reports `status=failed` or growing `lag_seconds`, `last_error` becomes populated, the route verifier reports a parity mismatch or non-200 route, or dashboard requests stop reporting `clickhouse.overview_snapshot` when the ClickHouse path is expected.
- **Recovery procedure:** fix the failing dependency or malformed batch, rerun `python3 -m vinted_radar.cli clickhouse-ingest` until the checkpoint clears, rerun `python3 scripts/verify_clickhouse_routes.py` against a representative listing/database, and only then enable the live polyglot analytical read path.
- **Monitoring gaps:** current probe/listing-seen manifests still leave some nullable serving dimensions empty, the direct route-proof here uses fixture-backed ClickHouse support rather than a fully backfilled live corpus, and continuous ingest lag alerting still depends on external operator scheduling rather than built-in alert dispatch.

## Verification

Ran every slice-plan verification command with `python3` because this shell does not provide a `python` alias: `python3 -m pytest tests/test_clickhouse_schema.py -q` (2 passed), `python3 -m pytest tests/test_clickhouse_ingest.py -q` (6 passed), `python3 -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q` (18 passed), and `python3 -m pytest tests/test_clickhouse_parity.py -q` (4 passed). Then ran the full slice regression sweep with `python3 -m pytest tests/test_clickhouse_schema.py tests/test_clickhouse_ingest.py tests/test_clickhouse_queries.py tests/test_dashboard.py tests/test_clickhouse_parity.py -q`, which passed with 30 tests green. For observability/diagnostic proof, ran a direct Python route-proof invocation of `verify_clickhouse_routes(...)` on a seeded dashboard fixture, which returned parity matches for `dashboard_api`, `explorer_api`, `detail_api`, and `health`, plus 200 responses for the ClickHouse HTML dashboard/explorer/detail routes with `repository_total_ms=65.59` and `clickhouse_total_ms=25.22`. Also ran a direct CLI smoke for `clickhouse-ingest-status --format json` with the task-test checkpoint fixture injected; it rendered the expected consumer/checkpoint/lag/target-table JSON contract.

## Requirements Advanced

- R008 — Moved the market-summary serving path onto ClickHouse rollups/latest-serving primitives so overview analytics can scale beyond SQLite full-history scans while preserving the existing product contract.
- R009 — Added ClickHouse-backed explorer and listing-detail analytical reads that preserve existing filters, drill-downs, and payload contracts without relying on SQLite full-history scans.
- R016 — Advanced the production-grade platform migration by separating analytical serving and rollups onto ClickHouse with replay-safe ingest, operator checkpoint visibility, and cutover-proof parity tooling.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Used `python3` instead of the plan’s `python` because this shell does not expose a `python` alias. Observability verification used the fixture-backed route verifier and injected-checkpoint CLI smoke rather than a live historical ClickHouse stack because S13’s acceptance contract is the serving seam and parity proof; full historical/live cutover remains S14. No slice-plan invalidation.

## Known Limitations

- Current probe batches do not yet emit the full denormalized category/brand/price context, and current listing-seen batches still omit some nullable listing-card fields, so some ClickHouse fact columns remain null until upstream emitters are enriched.
- The live application still defaults to the legacy SQLite analytical path until S14 backfills history and performs the intentional application cutover.
- The direct route-proof here uses seeded fixture data; real large-corpus/live parity after historical backfill still belongs to S14 acceptance.

## Follow-ups

- S14 should backfill historical SQLite evidence into ClickHouse, then run the reusable route verifier against the backfilled corpus before flipping live analytical reads.
- Upstream discovery/probe batch emitters should enrich the nullable serving dimensions that S13 intentionally left null-safe, so ClickHouse explorer/detail surfaces can rely on fuller fact context.
- S15 should build retention/reconciliation and AI-ready marts on top of the new fact/rollup/latest-serving boundary instead of re-querying raw historical SQLite tables.

## Files Created/Modified

- `infra/clickhouse/migrations/V002__serving_warehouse.sql` — Added the ClickHouse V002 warehouse schema with raw fact tables, serving rollups, latest-per-listing tables, TTL policy, and materialized views.
- `vinted_radar/platform/clickhouse_schema/__init__.py` — Wired the ClickHouse schema contract/versioning so bootstrap and tests treat V002 as the active serving baseline.
- `vinted_radar/platform/clickhouse_ingest.py` — Implemented replay-safe manifested-batch ingestion into ClickHouse facts plus checkpoint/lag/error status reporting.
- `vinted_radar/cli.py` — Added ClickHouse ingest/status operator commands and preserved dashboard/backend entrypoints needed for cutover diagnostics.
- `vinted_radar/query/overview_clickhouse.py` — Added the repository-shaped ClickHouse product adapter and overview-serving assembly over ClickHouse facts/latest tables.
- `vinted_radar/query/explorer_clickhouse.py` — Added ClickHouse-backed explorer snapshot/filter/comparison helpers for the product read path.
- `vinted_radar/query/detail_clickhouse.py` — Added ClickHouse-backed listing state-input, history, and peer-price loaders for detail payloads.
- `vinted_radar/dashboard.py` — Allowed overview/explorer/detail routes to serve through the ClickHouse adapter, exposed `primary_payload_source`, and normalized backend-specific probe presentation.
- `scripts/verify_clickhouse_routes.py` — Added a reusable parity-and-latency verifier for repository-backed versus ClickHouse-backed dashboard/explorer/detail/health routes.
- `tests/clickhouse_product_test_support.py` — Added scripted ClickHouse fixture support for route/query parity tests without requiring a live ClickHouse stack.
- `tests/test_clickhouse_schema.py` — Added schema regression coverage for the V002 serving warehouse objects, retention, and materialized-view wiring.
- `tests/test_clickhouse_ingest.py` — Added ingest replay-safety, failure-state, and CLI status/report regression coverage.
- `tests/test_clickhouse_queries.py` — Added ClickHouse adapter contract coverage for overview, explorer, and detail payload assembly.
- `tests/test_dashboard.py` — Extended dashboard route coverage so ClickHouse-backed payload delivery remains contract-compatible with the existing product shell.
- `tests/test_clickhouse_parity.py` — Added parity coverage and route-verifier proof across representative overview/explorer/detail/health scenarios.
- `.gsd/KNOWLEDGE.md` — Recorded the sink-global manifest replay-safety rule and backend-shape normalization pattern that future platform slices should reuse.
- `.gsd/PROJECT.md` — Updated project state to reflect S13 completion and the new ClickHouse serving-warehouse cutover seam.
