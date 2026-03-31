# S15: Retention, Reconciliation, and AI-Ready Feature Marts

**Goal:** Close the platform migration with lifecycle discipline, reconciliation/audit surfaces, and AI-ready feature/evidence marts so the new stack stays bounded, trustworthy, and ready for grounded intelligence work without another storage redesign.
**Demo:** After this: After this: TTL, compaction, reconciliation, and AI-ready feature/evidence marts keep the new platform bounded, auditable, and ready for grounded intelligence work.

## Tasks
- [x] **T01: Added a `platform-lifecycle` retention command that enforces ClickHouse TTL, archives/prunes transient PostgreSQL rows, and reports explicit storage posture.** — Implement bounded-storage lifecycle controls. Add ClickHouse TTL policy activation, PostgreSQL pruning/archival jobs for mutable transient data, object-store retention classes/lifecycle config, and reporting that makes current storage posture visible instead of implicit.
  - Estimate: 2 sessions
  - Files: vinted_radar/services/lifecycle.py, vinted_radar/platform/health.py, vinted_radar/cli.py, infra/clickhouse/, README.md, tests/test_lifecycle_jobs.py
  - Verify: python -m pytest tests/test_lifecycle_jobs.py -q
- [x] **T02: Added a unified `platform-audit` surface that wraps reconciliation, ingest lag, lifecycle drift, and backfill posture into CLI and runtime/health payloads.** — Add durable reconciliation and lag audit surfaces. Build commands and health payloads that compare PostgreSQL current-state windows, ClickHouse analytical windows, and Parquet manifest coverage, then expose lag/failure state for ingestion, lifecycle, and backfill paths so operators can trust the platform day to day.
  - Estimate: 1-2 sessions
  - Files: vinted_radar/services/platform_audit.py, vinted_radar/platform/health.py, vinted_radar/cli.py, tests/test_platform_audit.py
  - Verify: python -m pytest tests/test_platform_audit.py -q
- [x] **T03: Documented that S15/T03 is blocked because the current ClickHouse cutover path never populates change facts required for price-change and state-transition marts.** — Build AI-ready feature and evidence marts on top of the cut-over warehouse. Materialize listing/day, segment/day, price-change, state-transition, and evidence-pack style outputs that future grounded AI and product-level intelligence can consume without scanning raw events, while preserving traceability back to manifests and observed windows.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/query/feature_marts.py, infra/clickhouse/, vinted_radar/cli.py, tests/test_feature_marts.py
  - Verify: python -m pytest tests/test_feature_marts.py -q
  - Blocker: The current warehouse can support listing/day and segment/day style marts from existing rollups, but it cannot truthfully support warehouse-materialized price-change and state-transition marts until a populated change-event source exists or the task is explicitly re-scoped.
- [x] **T04: Made ClickHouse replay derive truthful change facts with terminal-chunk-aware backfill manifests.** — Implement the missing change-fact pipeline instead of approximating marts at query time. Extend the live cutover and historical replay paths so listing-seen/state-refresh batches deterministically produce populated change facts for price deltas, state transitions, engagement shifts, and follow-up miss transitions, then land them in the existing ClickHouse change tables with idempotent replay semantics.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/platform/clickhouse_ingest.py, vinted_radar/services/projectors.py, vinted_radar/platform/postgres_repository.py, vinted_radar/services/full_backfill.py, infra/clickhouse/migrations/V002__serving_warehouse.sql, tests/test_clickhouse_ingest.py, tests/test_full_backfill.py
  - Verify: python -m pytest tests/test_clickhouse_ingest.py tests/test_full_backfill.py -q
- [x] **T05: Added ClickHouse-backed feature marts and evidence-pack exports with explicit manifest/window traceability.** — Build the deferred AI-ready marts only after the change-fact source exists. Materialize/export listing-day, segment-day, price-change, state-transition, and evidence-pack outputs from ClickHouse rollups plus populated change facts, and keep manifest/window traceability explicit so downstream grounded-intelligence work does not need raw-event rescans.
  - Estimate: 2 sessions
  - Files: vinted_radar/query/feature_marts.py, vinted_radar/cli.py, vinted_radar/platform/health.py, infra/clickhouse/migrations/V002__serving_warehouse.sql, tests/test_feature_marts.py
  - Verify: python -m pytest tests/test_feature_marts.py -q
- [ ] **T06: Operational closure + final acceptance against the corrected warehouse contract** — Close S15 only after the repaired warehouse contract is proven end to end. Update operator docs and verification so lifecycle posture, reconciliation health, change-fact freshness, feature-mart evidence drill-down, and the remaining SQLite hot-path removal are all exercised by the final acceptance proof.
  - Estimate: 1-2 sessions
  - Files: README.md, scripts/verify_cutover_stack.py, vinted_radar/services/platform_audit.py, vinted_radar/platform/health.py, tests/test_platform_audit.py, tests/test_cutover_smoke.py
  - Verify: python -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q
