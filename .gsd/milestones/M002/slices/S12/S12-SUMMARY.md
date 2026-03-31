---
id: S12
parent: M002
milestone: M002
provides:
  - A bounded PostgreSQL mutable-truth schema for runtime controller state, runtime cycles, discovery runs, catalogs, listing identity, listing presence summaries, and listing current state.
  - Replay-safe PostgreSQL projector/repository seams that can consume manifested batch evidence without duplicating raw blobs into mutable tables.
  - A PostgreSQL-backed runtime control-plane path for runtime-status, pause/resume, controller heartbeats, and runtime cycle/controller persistence under the polyglot-read cutover.
  - An explicit `postgres-backfill` operator command plus regression coverage that proves current-state/control-plane cutover does not silently fall back to SQLite runtime mutation.
requires:
  - slice: S10
    provides: The PostgreSQL/ClickHouse/S3-compatible platform foundation, versioned migrations, outbox plumbing, and shared health/bootstrap seams that S12 reuses for mutable truth.
  - slice: S11
    provides: The deterministic manifested batch/evidence-lake contract that S12 projectors and future backfills can consume without inventing a second raw-evidence format.
affects:
  - M002/S13
  - M002/S14
  - M002/S15
  - M003
key_files:
  - infra/postgres/migrations/V003__platform_mutable_truth.sql
  - vinted_radar/platform/postgres_repository.py
  - vinted_radar/services/projectors.py
  - vinted_radar/services/discovery.py
  - vinted_radar/services/runtime.py
  - vinted_radar/services/postgres_backfill.py
  - vinted_radar/cli.py
  - tests/test_postgres_schema.py
  - tests/test_runtime_cli.py
  - tests/test_runtime_service.py
  - tests/test_postgres_backfill.py
  - .gsd/KNOWLEDGE.md
  - .gsd/OVERRIDES.md
  - .gsd/PROJECT.md
key_decisions:
  - D043 — use separate PostgreSQL mutable-truth tables for runtime controller state, runtime cycles, discovery runs, catalogs, listing identity, listing current state, listing presence summaries, mutable manifests, and outbox checkpoints with natural keys and projector provenance fields.
  - D044 — project listing identity/presence/current-state from outbox-backed page batches, but never derive follow-up misses from page-scoped listing-seen manifests alone.
  - D045 — provide an explicit `postgres-backfill` CLI command and prove runtime cutover with a service-level smoke test that asserts SQLite runtime tables stay untouched when control-plane writes are redirected.
patterns_established:
  - Separate immutable evidence storage from bounded mutable truth: S11 owns raw proof, while S12 owns current-state/control-plane projection in PostgreSQL via natural-key upserts.
  - Use replay-safe projector contracts for listing identity, presence, current state, and runtime control-plane truth, and keep follow-up misses derived only from catalog-complete inputs.
  - Prove control-plane cutover by asserting the legacy SQLite runtime tables remain empty during the external-control-plane smoke run, not just by observing a green runtime cycle.
observability_surfaces:
  - `python3 -m vinted_radar.cli runtime-status --db <db> --format json`
  - `python3 -m vinted_radar.cli postgres-backfill --db <sqlite.db> --format json`
  - `python3 -m pytest tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_backfill.py -q`
  - Generated auto `execute-task` prompts for this project now inline the Task Summary template and surface the active override instead of relying on an external home-path template read.
drill_down_paths:
  - .gsd/milestones/M002/slices/S12/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S12/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S12/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S12/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T06:18:58.559Z
blocker_discovered: false
---

# S12: PostgreSQL Control Plane + Current-State Projection

**S12 moved mutable runtime/control-plane and current listing truth onto PostgreSQL with replay-safe projectors, operator backfill, and a cutover proof that guards against silent SQLite fallback.**

## What Happened

S12 completed the first real mutable-truth cutover away from the legacy SQLite mutation boundary. T01 added PostgreSQL V003, which created natural-key tables for runtime controller truth, runtime cycles, discovery runs, catalogs, listing identity, listing presence summaries, listing current state, mutable manifests, and outbox checkpoints. That gave the project a bounded current-state/control-plane schema separate from SQLite’s historical evidence tables and separate from the S11 immutable Parquet lake.

T02 then built the replay-safe projection seam on top of that schema. `PostgresMutableTruthRepository` gained projector-facing upserts/read surfaces for discovery, catalogs, listing identity, presence, current state, and runtime truth, while `MutableTruthProjectorService` wired manifested batch consumption, parquet row loading, mutable-manifest status tracking, and outbox-checkpoint observability. The slice also locked in an important correctness rule: page-scoped listing-seen manifests can update presence and current state, but they must not invent follow-up misses that require catalog-complete truth.

T03 cut the operator/runtime control-plane over under the existing polyglot-read flag. Runtime-status, pause/resume, controller heartbeats, and runtime cycle/controller persistence can now resolve through PostgreSQL mutable truth instead of SQLite when the cutover is enabled, while discovery bookkeeping mirrors into the same bounded current-state store. That moved the core runtime-control seam onto PostgreSQL without yet forcing the broader product read path to follow.

T04 finished the missing operational proof and recovery path. The existing SQLite-to-PostgreSQL backfill service was exposed as a real `postgres-backfill` CLI command with JSON/table reporting, and regression coverage now proves that a real `RadarRuntimeService` cycle can run through an injected external control-plane repository while SQLite `runtime_cycles` and `runtime_controller_state` remain empty. That is the key guard against fake cutover success where PostgreSQL appears wired but the runtime silently keeps mutating SQLite underneath.

During closeout I also fixed the project’s auto-mode recovery posture. The original S12/T04 failure happened because the task runner fell back to a stale user-home template path instead of relying on the already available output templates. The repo now carries an active `.gsd/OVERRIDES.md` instruction that tells future auto `execute-task` prompts in this project to trust the inlined Task Summary/Decisions templates, and the local active GSD extension prompt was patched so generated `execute-task` prompts now inline the Task Summary block directly and no longer emit the stale home-path template guidance. That makes this project resumable in auto mode without depending on the exact user-home template path that caused the placeholder summary drift.

The slice’s delivered shape is now: immutable raw evidence in S11 -> replay-safe projectors and bounded mutable truth in PostgreSQL -> explicit runtime/control-plane cutover path plus operator backfill. That is the boundary S13-S15 should extend for ClickHouse serving, historical migration, and application read cutover rather than reaching back into SQLite mutation tables.

## Verification

Ran a focused slice regression pack across schema/config/bootstrap, runtime CLI cutover, runtime external-control-plane smoke, and mutable-truth backfill coverage. `python3 -m py_compile vinted_radar/cli.py vinted_radar/platform/postgres_repository.py vinted_radar/services/projectors.py vinted_radar/services/discovery.py vinted_radar/services/runtime.py vinted_radar/services/postgres_backfill.py tests/test_postgres_schema.py tests/test_platform_config.py tests/test_data_platform_bootstrap.py tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_backfill.py` passed. `python3 -m pytest tests/test_postgres_schema.py tests/test_platform_config.py tests/test_data_platform_bootstrap.py tests/test_runtime_cli.py tests/test_runtime_service.py tests/test_postgres_backfill.py -q` passed with 36 tests green. Then a direct Node smoke against `/home/utilisateur/.gsd/agent/extensions/gsd/auto-prompts.js` proved that future auto `execute-task` prompts for this project now inline the Task Summary template, include the active override, and no longer emit the stale home-path template guidance that caused the T04 placeholder-summary failure.

## Requirements Advanced

- R010 — S12 moved runtime status, pause/resume, controller heartbeats, and cycle/controller persistence onto PostgreSQL mutable truth under the cutover flag while preserving the existing batch/continuous operator contract and CLI/runtime diagnostics.
- R016 — S12 replaced the first live mutable-control-plane/current-state slice of the monolithic SQLite boundary with bounded PostgreSQL truth plus explicit backfill and regression guards, advancing the production-grade platform migration needed before SaaS hardening and commercialization.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Used a service-level external control-plane smoke test in `tests/test_runtime_service.py` instead of provisioning another live PostgreSQL fixture just for S12 closeout, because S10 already proves the real local platform stack. Also added a project-level `.gsd/OVERRIDES.md` mitigation plus a local GSD `execute-task` prompt fix so future auto-mode task units use inlined Task Summary/Decisions templates instead of relying on a stale home-path template read.

## Known Limitations

- Overview, explorer, listing-detail, and broader product-serving reads are still staged on SQLite until S13/S14 complete the analytical and application read cutovers.
- `postgres-backfill` is an explicit operator command, not yet a full historical cutover/runbook flow with ClickHouse/object-store migration bundled in one end-to-end operation.
- The project-level `.gsd/OVERRIDES.md` makes future auto-mode task prompts safe in this repo, but the direct `execute-task` prompt fix currently lives in the local user-level GSD extension and should be preserved across extension refreshes.

## Follow-ups

- S13 should build ClickHouse raw facts and serving rollups from the PostgreSQL mutable-truth + manifested-batch seams now in place, rather than adding another SQLite-side analytical shortcut.
- S14 should run the real historical SQLite-to-PostgreSQL/ClickHouse/object-store migration and then cut runtime/product reads off the legacy SQLite mutation boundary.
- Carry the local GSD `execute-task` prompt inline-template fix into the maintained user-profile extension source if that extension is refreshed or reinstalled, so the project-level override remains a safety net instead of the only guard.

## Files Created/Modified

- `infra/postgres/migrations/V003__platform_mutable_truth.sql` — Added PostgreSQL V003 mutable-truth tables and baseline version wiring for runtime/discovery/catalog/current-state truth.
- `vinted_radar/platform/postgres_repository.py` — Expanded the mutable-truth repository with runtime/discovery/catalog/listing projection and read surfaces for PostgreSQL current-state/control-plane truth.
- `vinted_radar/services/projectors.py` — Added projector orchestration for replay-safe mutable-truth projection from manifested outbox batches.
- `vinted_radar/services/discovery.py` — Mirrored discovery bookkeeping into PostgreSQL mutable truth when the polyglot-read cutover is enabled.
- `vinted_radar/services/runtime.py` — Allowed runtime cycles/controller truth to run through an injected external control-plane repository and added a smoke guard against SQLite fallback.
- `vinted_radar/services/postgres_backfill.py` — Added the explicit SQLite-to-PostgreSQL mutable-truth backfill service and CLI command.
- `vinted_radar/cli.py` — Cut runtime CLI control-plane commands over to PostgreSQL mutable truth and added `postgres-backfill` operator entrypoints.
- `tests/test_postgres_schema.py` — Added schema coverage for the PostgreSQL mutable-truth platform baseline.
- `tests/test_runtime_cli.py` — Added CLI/runtime cutover coverage for PostgreSQL-backed control-plane reads and writes.
- `tests/test_runtime_service.py` — Added external-control-plane runtime smoke coverage and the SQLite-no-fallback assertion.
- `tests/test_postgres_backfill.py` — Added SQLite-to-PostgreSQL mutable-truth backfill and CLI regression coverage.
- `.gsd/KNOWLEDGE.md` — Recorded the external-control-plane no-SQLite-fallback cutover guard as a reusable platform migration pattern.
- `.gsd/OVERRIDES.md` — Pinned future auto-mode execute-task prompts in this project to the inlined templates so stale home-path template guidance does not break recovery again.
- `.gsd/PROJECT.md` — Updated current project state to reflect S12 completion and the PostgreSQL mutable-truth cutover seam.
