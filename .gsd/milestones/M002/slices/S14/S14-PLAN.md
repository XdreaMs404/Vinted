# S14: Historical Backfill + Application Cutover

**Goal:** Migrate historical continuity, cut reads and writes over to the new platform end to end, and retire the SQLite-heavy live loop from the real product path without losing auditability or product truth.
**Demo:** After this: After this: historical SQLite evidence is backfilled into PostgreSQL, ClickHouse, and the Parquet lake, the product reads the new platform end to end, and the live collector no longer depends on heavyweight SQLite history tables.

## Tasks
- [x] **T01: Added a resumable full backfill command that migrates SQLite history into PostgreSQL mutable truth, ClickHouse facts, and Parquet audit manifests.** — Build the full historical backfill pipeline. Add commands/workers that migrate legacy SQLite discovery, observation, probe, and runtime history into PostgreSQL current-state/control-plane rows, ClickHouse facts/rollups, and Parquet evidence manifests, with resumable checkpoints and dry-run support for large corpora.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/services/full_backfill.py, vinted_radar/cli.py, tests/test_full_backfill.py
  - Verify: python -m pytest tests/test_full_backfill.py -q
- [x] **T02: Added a cross-store reconciliation command and made cutover state explicit in CLI, runtime, and health diagnostics.** — Add reconciliation and cutover controls. Implement row-count/time-window reconciliation across SQLite, PostgreSQL, ClickHouse, and object storage manifests; expose cutover mode in config/health/runtime diagnostics; and make dual-write/read-cutover state explicit so deployment is observable instead of implicit.
  - Estimate: 2 sessions
  - Files: vinted_radar/services/reconciliation.py, vinted_radar/platform/health.py, vinted_radar/cli.py, tests/test_reconciliation.py
  - Verify: python -m pytest tests/test_reconciliation.py -q
- [x] **T03: Cut dashboard, runtime, CLI read paths, and live mutable-truth writes over to the PostgreSQL + ClickHouse platform stack with SQLite kept only as a fallback.** — Cut product and operator reads/writes over to the new platform. Switch dashboard, CLI, runtime status, health, and collector write paths so the live app resolves mutable truth from PostgreSQL, analytics from ClickHouse, and proof from manifests/object storage, while preserving existing user-visible contracts and adding an emergency fallback path only as a temporary migration safety valve.
  - Estimate: 2-3 sessions
  - Files: vinted_radar/dashboard.py, vinted_radar/cli.py, vinted_radar/services/discovery.py, vinted_radar/services/runtime.py, vinted_radar/platform/health.py, tests/test_dashboard.py, tests/test_runtime_service.py
  - Verify: python -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q
- [x] **T04: Added a rerunnable live cutover smoke proof and documented the VPS cutover and rollback runbook.** — Prove the cut-over platform in a real live-cycle acceptance flow. Run a narrow but real collector cycle on PostgreSQL + ClickHouse + object storage, verify dashboard/runtime/health/browser behavior on that stack, and document the exact operational sequence for production cutover and rollback on the VPS.
  - Estimate: 1-2 sessions
  - Files: README.md, scripts/verify_vps_serving.py, scripts/verify_cutover_stack.py, tests/test_cutover_smoke.py
  - Verify: python -m pytest tests/test_cutover_smoke.py -q
