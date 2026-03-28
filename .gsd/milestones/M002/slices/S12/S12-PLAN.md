# S12: PostgreSQL Control Plane + Current-State Projection

**Goal:** Move mutable control-plane and current-state truth onto PostgreSQL while keeping the collector/event path idempotent, so runtime control and operational state are bounded and no longer share a monolithic SQLite history boundary with raw evidence and analytics.
**Demo:** After this: After this: runtime control, discovery runs, catalogs, and current listing truth live in PostgreSQL through projector-backed writes instead of SQLite mutation tables.

## Tasks
- [ ] **T01: PostgreSQL mutable schema** — Design and migrate the PostgreSQL control-plane/current-state schema. Create versioned PostgreSQL tables for runtime controller state, runtime cycles, discovery runs, catalogs, listing identity/current state, recent presence summaries, manifests, and outbox checkpoints, with explicit keys and indexes for idempotent projectors and operational queries.
  - Estimate: 2 sessions
  - Files: infra/postgres/, vinted_radar/platform/migrations.py, vinted_radar/platform/postgres_schema/, tests/test_postgres_schema.py
  - Verify: python -m pytest tests/test_postgres_schema.py -q
- [ ] **T02: Projectors for current-state truth** — Implement PostgreSQL repositories and projectors for current-state truth. Add adapters that consume outbox events and update runtime/controller rows, discovery bookkeeping, catalog rows, listing current-state rows, and presence rollups in PostgreSQL without duplicating raw evidence blobs.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/platform/postgres_repository.py, vinted_radar/services/projectors.py, vinted_radar/services/discovery.py, vinted_radar/services/runtime.py, tests/test_postgres_projectors.py
  - Verify: python -m pytest tests/test_postgres_projectors.py -q
- [ ] **T03: CLI/runtime cutover to PostgreSQL** — Cut the CLI/runtime control surfaces over to PostgreSQL-backed mutable truth. Make runtime-status, pause/resume, controller heartbeats, and discovery bookkeeping resolve through the new PostgreSQL repositories/config while preserving existing JSON/product contracts for later UI slices.
  - Estimate: 2 sessions
  - Files: vinted_radar/cli.py, vinted_radar/services/runtime.py, vinted_radar/platform/postgres_repository.py, tests/test_runtime_cli_postgres.py
  - Verify: python -m pytest tests/test_runtime_cli_postgres.py -q
- [ ] **T04: Backfill + PostgreSQL control-plane smoke** — Backfill and prove one real control-plane run on PostgreSQL. Add a controlled SQLite-to-PostgreSQL backfill for runtime/discovery/catalog/current-state data, then run a narrow batch/continuous smoke against PostgreSQL-backed mutable truth and assert that runtime-status and bookkeeping stay correct without SQLite mutation writes.
  - Estimate: 1-2 sessions
  - Files: vinted_radar/services/postgres_backfill.py, vinted_radar/cli.py, tests/test_postgres_backfill.py, tests/test_runtime_service.py
  - Verify: python -m pytest tests/test_postgres_backfill.py tests/test_runtime_service.py -q
