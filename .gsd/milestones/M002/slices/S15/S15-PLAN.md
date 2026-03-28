# S15: Retention, Reconciliation, and AI-Ready Feature Marts

**Goal:** Close the platform migration with lifecycle discipline, reconciliation/audit surfaces, and AI-ready feature/evidence marts so the new stack stays bounded, trustworthy, and ready for grounded intelligence work without another storage redesign.
**Demo:** After this: After this: TTL, compaction, reconciliation, and AI-ready feature/evidence marts keep the new platform bounded, auditable, and ready for grounded intelligence work.

## Tasks
- [ ] **T01: Retention + bounded-storage jobs** — Implement bounded-storage lifecycle controls. Add ClickHouse TTL policy activation, PostgreSQL pruning/archival jobs for mutable transient data, object-store retention classes/lifecycle config, and reporting that makes current storage posture visible instead of implicit.
  - Estimate: 2 sessions
  - Files: vinted_radar/services/lifecycle.py, vinted_radar/platform/health.py, vinted_radar/cli.py, infra/clickhouse/, README.md, tests/test_lifecycle_jobs.py
  - Verify: python -m pytest tests/test_lifecycle_jobs.py -q
- [ ] **T02: Reconciliation + lag audit surfaces** — Add durable reconciliation and lag audit surfaces. Build commands and health payloads that compare PostgreSQL current-state windows, ClickHouse analytical windows, and Parquet manifest coverage, then expose lag/failure state for ingestion, lifecycle, and backfill paths so operators can trust the platform day to day.
  - Estimate: 1-2 sessions
  - Files: vinted_radar/services/platform_audit.py, vinted_radar/platform/health.py, vinted_radar/cli.py, tests/test_platform_audit.py
  - Verify: python -m pytest tests/test_platform_audit.py -q
- [ ] **T03: AI-ready feature + evidence marts** — Build AI-ready feature and evidence marts on top of the cut-over warehouse. Materialize listing/day, segment/day, price-change, state-transition, and evidence-pack style outputs that future grounded AI and product-level intelligence can consume without scanning raw events, while preserving traceability back to manifests and observed windows.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/query/feature_marts.py, infra/clickhouse/, vinted_radar/cli.py, tests/test_feature_marts.py
  - Verify: python -m pytest tests/test_feature_marts.py -q
- [ ] **T04: Operational closure + final acceptance** — Close the migration operationally. Remove heavyweight SQLite history tables from the live runtime path, document the final operating model, and run one last integrated acceptance proving bounded storage, reconciliation health, dashboard/runtime behavior, and evidence drill-down on the new platform.
  - Estimate: 1-2 sessions
  - Files: README.md, vinted_radar/cli.py, scripts/verify_cutover_stack.py, tests/test_integrated_platform_acceptance.py
  - Verify: python -m pytest tests/test_integrated_platform_acceptance.py -q
