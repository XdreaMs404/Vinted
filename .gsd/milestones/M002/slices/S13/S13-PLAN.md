# S13: ClickHouse Serving Warehouse + Rollups

**Goal:** Introduce the long-term serving warehouse in ClickHouse so overview, explorer, detail, and future AI-facing analytics read from raw facts and materialized rollups instead of SQLite full-history scans.
**Demo:** After this: After this: overview, explorer, and listing-detail analytics read from ClickHouse raw facts and materialized rollups rather than SQLite full-history scans.

## Tasks
- [x] **T01: Added the ClickHouse warehouse V002 schema with raw facts, rollups, latest-serving primitives, and schema tests.** — Design the ClickHouse analytical schema. Add raw fact tables for listing-seen events, probe events, and derived change events; define partitions/order keys and TTL policy; and create the first materialized views/rollups for listing-hourly/daily, category/brand daily metrics, and other serving primitives the product needs.
  - Estimate: 2 sessions
  - Files: infra/clickhouse/, vinted_radar/platform/clickhouse_schema/, vinted_radar/platform/migrations.py, tests/test_clickhouse_schema.py
  - Verify: python -m pytest tests/test_clickhouse_schema.py -q
- [x] **T02: Added replay-safe ClickHouse batch ingestion with checkpoint status and operator CLI commands.** — Implement the ingestion worker from outbox/manifests into ClickHouse. Consume listing-seen and probe batches, map them into raw fact tables, maintain replay-safe inserts, and expose ingestion lag/error state so S14 cutover can trust whether analytical data is current.
  - Estimate: 2 sessions
  - Files: vinted_radar/platform/clickhouse_ingest.py, vinted_radar/platform/outbox.py, vinted_radar/cli.py, tests/test_clickhouse_ingest.py
  - Verify: python -m pytest tests/test_clickhouse_ingest.py -q
- [x] **T03: Added a repository-shaped ClickHouse query adapter so overview, explorer, and listing detail can read analytical state from ClickHouse while preserving the existing dashboard route contracts.** — Build ClickHouse-backed analytical query adapters for overview, explorer, and detail. Move the heavy read paths out of the SQLite-oriented repository by introducing dedicated ClickHouse query modules and product-facing adapters that preserve existing payload/drill-down contracts while sourcing their aggregates and listing sets from ClickHouse.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/query/overview_clickhouse.py, vinted_radar/query/explorer_clickhouse.py, vinted_radar/query/detail_clickhouse.py, vinted_radar/dashboard.py, vinted_radar/cli.py, tests/test_clickhouse_queries.py, tests/test_dashboard.py
  - Verify: python -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q
- [x] **T04: Added ClickHouse parity tests and a reusable route verifier, and fixed dashboard probe rendering so overview, explorer, and detail stay cutover-consistent.** — Prove analytical correctness and performance on the new boundary. Add parity/reconciliation checks between representative SQLite-era outputs and ClickHouse marts during migration, then run focused dashboard/explorer/detail route verification so the cutover path has both correctness and latency evidence.
  - Estimate: 1-2 sessions
  - Files: tests/test_clickhouse_parity.py, scripts/verify_clickhouse_routes.py, vinted_radar/dashboard.py
  - Verify: python -m pytest tests/test_clickhouse_parity.py -q
