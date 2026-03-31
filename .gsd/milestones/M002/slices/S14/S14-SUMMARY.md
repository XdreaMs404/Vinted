---
id: S14
parent: M002
milestone: M002
provides:
  - A resumable full backfill path from legacy SQLite into PostgreSQL mutable truth, ClickHouse replay inputs, and Parquet audit manifests
  - A reconciliation contract and explicit cutover diagnostics for shadow validation and rollback decisions
  - A live application cutover path where dashboard and runtime reads use PostgreSQL + ClickHouse while SQLite remains only a temporary fallback and safety valve
  - A rerunnable cutover smoke verifier and documented VPS cutover and rollback runbook for real operator rollout
requires:
  - slice: S12
    provides: PostgreSQL mutable-truth schema, projector and backfill path, and runtime control-plane repository used for the live cutover.
  - slice: S13
    provides: ClickHouse serving warehouse, ingest worker, and repository-shaped analytics adapter used by overview, explorer, and detail reads.
affects:
  - S15
key_files:
  - vinted_radar/services/full_backfill.py
  - vinted_radar/services/reconciliation.py
  - vinted_radar/cli.py
  - vinted_radar/platform/health.py
  - vinted_radar/dashboard.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/services/discovery.py
  - vinted_radar/services/state_refresh.py
  - scripts/verify_cutover_stack.py
  - scripts/verify_vps_serving.py
  - README.md
  - tests/test_full_backfill.py
  - tests/test_reconciliation.py
  - tests/test_dashboard.py
  - tests/test_runtime_service.py
  - tests/test_runtime_cli.py
  - tests/test_cutover_smoke.py
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - Backfill PostgreSQL mutable truth directly from SQLite state/history, replay only live-compatible discovery/probe batches into ClickHouse, and keep legacy observation/runtime history as Parquet audit evidence.
  - Persist full-backfill progress in a local JSON checkpoint so interrupted migrations can resume idempotently without duplicating ClickHouse facts or lake objects.
  - Derive one shared cutover snapshot and expose the same mode/read-path/write-target contract across CLI, dashboard runtime payloads, and health diagnostics.
  - Keep ClickHouse as the analytics backend while reading runtime/controller truth from PostgreSQL during cutover.
  - Honor the published cutover read path in operator reads: `dual-write-shadow` stays on SQLite, while `polyglot-cutover` switches to the platform path.
patterns_established:
  - Split historical migration by store responsibility: PostgreSQL gets direct mutable-truth projection, ClickHouse gets only live-compatible serving facts, and the lake retains legacy audit evidence.
  - Drive all cutover-facing product and operator surfaces from one shared cutover snapshot instead of re-deriving mode/read-path/write-target logic per route.
  - Treat runtime/control-plane truth and analytical reads as separate dependencies during cutover: PostgreSQL owns controller truth, ClickHouse owns analytical serving, and shadow-mode operator reads must still honor the published SQLite read path.
observability_surfaces:
  - `platform-reconcile` CLI reconciliation report across SQLite, PostgreSQL, ClickHouse, and manifest-backed object storage
  - Shared cutover mode/read-path/write-target exposure in `runtime-status`, dashboard runtime payloads, `/api/runtime`, and `/health`
  - `scripts/verify_cutover_stack.py` for end-to-end cutover smoke proof
  - Expanded `scripts/verify_vps_serving.py` assertions for runtime and health cutover state during rollout and rollback
drill_down_paths:
  - .gsd/milestones/M002/slices/S14/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S14/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S14/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S14/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T14:17:42.144Z
blocker_discovered: false
---

# S14: Historical Backfill + Application Cutover

**Historical SQLite evidence is now backfillable into PostgreSQL, ClickHouse, and the Parquet lake, and the application/runtime stack can cut over to the new platform with explicit shadow and cutover diagnostics plus rollback proof.**

## What Happened

S14 turned the polyglot platform from staged infrastructure into the real migration and application path. T01 added a resumable full-backfill command that projects legacy SQLite mutable truth directly into PostgreSQL, replays live-compatible discovery and probe history through the existing ClickHouse ingest path, and exports observation/runtime history as Parquet-backed audit manifests with checkpointed progress and dry-run safety. T02 added cross-store reconciliation plus a shared cutover snapshot so CLI, dashboard runtime payloads, `/api/runtime`, `/runtime`, and `/health` all disclose the same mode, read path, write targets, and warnings. T03 then cut dashboard, runtime, CLI, and live mutable-truth writes onto the PostgreSQL + ClickHouse stack with SQLite preserved only as a temporary fallback and shadow safety valve. During slice closeout verification I found and fixed one integration regression in that contract: `runtime-status` must continue reading SQLite while the cutover snapshot still says `dual-write-shadow`; only `polyglot-cutover` should route those reads to the new platform. T04 completed the operator proof story with `scripts/verify_cutover_stack.py`, stronger `verify_vps_serving.py` cutover assertions, and a VPS cutover/rollback runbook in `README.md`.

## Operational Readiness (Q8)
- **Health signal:** `platform-doctor` healthy, reconciliation reports match across stores, `/api/runtime` and `/health` expose the expected cutover snapshot, and `verify_cutover_stack.py` can prove PostgreSQL truth, ClickHouse ingest settlement, object-storage evidence, and served routes together.
- **Failure signal:** reconciliation mismatches, failed ClickHouse ingest checkpoints, cutover warnings on runtime/health surfaces, or `verify_cutover_stack.py` / `verify_vps_serving.py` reporting the wrong mode/read path or a missing representative listing.
- **Recovery procedure:** set `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=false`; if the platform itself is unhealthy also disable the three platform-write flags, restart the dashboard first and then the collector/runtime service, and rerun `scripts/verify_vps_serving.py` to confirm the fallback path is healthy.
- **Monitoring gaps:** this shell cannot execute the Docker-backed cutover smoke, and continuous scheduled reconciliation / retention enforcement still belongs to S15.

## Verification

Slice-plan verification passed with the following evidence:
- `python3 -m pytest tests/test_full_backfill.py -q` → 4 passed
- `python3 -m pytest tests/test_reconciliation.py -q` → 4 passed
- `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q` → 24 passed
- `python3 -m pytest tests/test_runtime_cli.py -q` → 14 passed
- `python3 -m pytest tests/test_cutover_smoke.py -q` → exit 0, 1 skipped (Docker unavailable in this shell)
- `python3 -m pytest tests/test_cli_smoke.py tests/test_cutover_smoke.py -q` → 2 passed, 1 skipped

Together these checks prove the resumable backfill path, cross-store reconciliation, explicit cutover observability, application/runtime cutover behavior, the shadow-mode SQLite read-path fix, and the shipped smoke/runbook acceptance path.

## Requirements Advanced

- R002 — Historical observations, current-state truth, and runtime continuity can now be migrated off legacy SQLite without discarding the evidence needed for first/last-seen and revisit history.
- R010 — Batch and runtime control now work against PostgreSQL mutable truth during platform writes, while the product can switch reads onto ClickHouse + PostgreSQL through explicit cutover flags rather than an implicit SQLite dependency.
- R011 — Cutover mode, read path, write targets, and reconciliation status are now explicit across runtime and health diagnostics instead of being hidden behind silent migration state.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Used `python3` instead of `python` because this shell does not expose a `python` executable. Slice closeout also uncovered one integration regression: `runtime-status` incorrectly tried PostgreSQL during `dual-write-shadow` even though shadow-mode reads are supposed to remain on SQLite. I fixed that in `vinted_radar/cli.py` and reran the reconciliation and runtime CLI suites before closing the slice. The Docker-backed cutover smoke remains environment-gated here because the local shell has no Docker binary, so local acceptance relied on the clean skip plus the updated public-route smoke regression.

## Known Limitations

The full container-backed cutover smoke remains unavailable in shells without Docker, so this environment could only prove the shipped harness wiring and the public-route smoke regression rather than the full live stack. Also, the SQLite fallback/shadow path remains intentionally present as a migration safety valve until operators fully commit to `polyglot-cutover`; ongoing retention and automated reconciliation are deferred to S15.

## Follow-ups

S15 should automate scheduled reconciliation and retention so shadow/cutover integrity remains continuously auditable instead of only operator-invoked. The Docker-backed `verify_cutover_stack.py` path should also run in a Docker-capable CI or VPS environment on every real cutover and rollback.

## Files Created/Modified

- `vinted_radar/services/full_backfill.py` — Added resumable orchestration for SQLite → PostgreSQL/ClickHouse/object-storage backfill with checkpointed progress.
- `vinted_radar/cli.py` — Added reconciliation/reporting commands, cutover-aware runtime status behavior, and wired the backfill/cutover operator surface.
- `vinted_radar/platform/health.py` — Centralized cutover mode/read-path/write-target summarization and platform-health rendering.
- `vinted_radar/dashboard.py` — Cut dashboard/runtime payload assembly over to the polyglot query path with shared cutover diagnostics.
- `vinted_radar/query/overview_clickhouse.py` — Provided ClickHouse-backed product reads while delegating runtime/control-plane truth to PostgreSQL.
- `vinted_radar/services/discovery.py` — Projected live discovery mutable truth into PostgreSQL during cutover instead of relying on legacy SQLite-only mutation paths.
- `vinted_radar/services/state_refresh.py` — Projected probe refresh results directly into PostgreSQL mutable truth during cutover.
- `scripts/verify_cutover_stack.py` — Added rerunnable live cutover smoke proof across doctor, ingest, PostgreSQL truth, object storage, and served routes.
- `scripts/verify_vps_serving.py` — Extended public-route verification to assert runtime/health cutover state during rollout and rollback.
- `README.md` — Documented the cutover-mode contract plus VPS cutover and rollback runbook.
- `tests/test_full_backfill.py` — Added focused regression coverage for full backfill.
- `tests/test_reconciliation.py` — Added focused regression coverage for reconciliation and cutover diagnostics.
- `tests/test_dashboard.py` — Added dashboard cutover regression coverage.
- `tests/test_runtime_service.py` — Added runtime cutover regression coverage.
- `tests/test_runtime_cli.py` — Added CLI runtime/control-plane cutover regression coverage.
- `tests/test_cutover_smoke.py` — Added cutover smoke acceptance coverage.
- `.gsd/KNOWLEDGE.md` — Recorded the dual-write-shadow read-path gotcha for future agents.
- `.gsd/PROJECT.md` — Refreshed project state to mark S14 complete and describe the new cutover verification baseline.
