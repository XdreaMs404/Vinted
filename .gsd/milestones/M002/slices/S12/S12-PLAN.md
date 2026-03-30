# S12: PostgreSQL Control Plane + Current-State Projection

**Goal:** Move mutable control-plane and current-state truth onto PostgreSQL while keeping the collector/event path idempotent, so runtime control and operational state are bounded and no longer share a monolithic SQLite history boundary with raw evidence and analytics.
**Demo:** After this: After this: runtime control, discovery runs, catalogs, and current listing truth live in PostgreSQL through projector-backed writes instead of SQLite mutation tables.

## Tasks
- [x] **T01: Added PostgreSQL V003 mutable-truth schema for runtime, discovery, catalogs, listing state, manifests, and projector checkpoints.** — Design and migrate the PostgreSQL control-plane/current-state schema. Create versioned PostgreSQL tables for runtime controller state, runtime cycles, discovery runs, catalogs, listing identity/current state, recent presence summaries, manifests, and outbox checkpoints, with explicit keys and indexes for idempotent projectors and operational queries.
  - Estimate: 2 sessions
  - Files: infra/postgres/, vinted_radar/platform/migrations.py, vinted_radar/platform/postgres_schema/, tests/test_postgres_schema.py
  - Verify: python -m pytest tests/test_postgres_schema.py -q
- [x] **T02: Scaffolded the PostgreSQL mutable-truth projector service and replay-safe listing batch projection, but discovery/runtime wiring and tests remain unfinished.** — Implement PostgreSQL repositories and projectors for current-state truth. Add adapters that consume outbox events and update runtime/controller rows, discovery bookkeeping, catalog rows, listing current-state rows, and presence rollups in PostgreSQL without duplicating raw evidence blobs.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/platform/postgres_repository.py, vinted_radar/services/projectors.py, vinted_radar/services/discovery.py, vinted_radar/services/runtime.py
  - Verify: python3 -m py_compile vinted_radar/platform/postgres_repository.py
- [x] **T03: Routed runtime CLI control-plane commands and runtime cycle/controller persistence through PostgreSQL mutable truth when polyglot reads are enabled.** — Cut the CLI/runtime control surfaces over to PostgreSQL-backed mutable truth. Make runtime-status, pause/resume, controller heartbeats, and discovery bookkeeping resolve through the new PostgreSQL repositories/config while preserving existing JSON/product contracts for later UI slices.
  - Estimate: 2 sessions
  - Files: vinted_radar/cli.py, vinted_radar/services/runtime.py, vinted_radar/platform/postgres_repository.py, tests/test_runtime_cli.py
  - Verify: python3 -m pytest tests/test_runtime_cli.py -q
- [ ] **T04: Started a PostgreSQL mutable-truth backfill service and runtime control-plane repository APIs, but CLI wiring, tests, and the PostgreSQL smoke proof remain unfinished.** — Backfill and prove one real control-plane run on PostgreSQL. Add a controlled SQLite-to-PostgreSQL backfill for runtime/discovery/catalog/current-state data, then run a narrow batch/continuous smoke against PostgreSQL-backed mutable truth and assert that runtime-status and bookkeeping stay correct without SQLite mutation writes.
  - Estimate: 1-2 sessions
  - Files: vinted_radar/services/postgres_backfill.py, vinted_radar/cli.py, tests/test_runtime_service.py
  - Verify: python3 -m py_compile vinted_radar/platform/postgres_repository.py vinted_radar/services/postgres_backfill.py vinted_radar/services/runtime.py
