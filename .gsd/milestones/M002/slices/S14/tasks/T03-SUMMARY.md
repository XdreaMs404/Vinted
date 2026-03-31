---
id: T03
parent: S14
milestone: M002
provides:
  - Precise resume notes for the remaining application-cutover implementation
key_files:
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - vinted_radar/services/discovery.py
  - vinted_radar/services/state_refresh.py
  - vinted_radar/query/overview_clickhouse.py
  - vinted_radar/platform/postgres_repository.py
key_decisions:
  - Do not force partial cutover edits after the context-budget warning; capture concrete findings and a clean resume plan instead.
patterns_established:
  - ClickHouse-backed dashboard reads still inherit runtime/control-plane data from the wrapped SQLite repository unless a PostgreSQL control-plane repository is threaded through the adapter.
observability_surfaces:
  - none
duration: investigation only
verification_result: not-run
completed_at: 2026-03-31T13:46:00+02:00
blocker_discovered: false
---

# T03: End-to-end application cutover

**Stopped before implementation after identifying the concrete cutover gaps and recording exact resume notes.**

## Slice Plan Excerpt
Source: `.gsd/milestones/M002/slices/S14/S14-PLAN.md`
**Goal:** Migrate historical continuity, cut reads and writes over to the new platform end to end, and retire the SQLite-heavy live loop from the real product path without losing auditability or product truth.
**Demo:** After this: After this: historical SQLite evidence is backfilled into PostgreSQL, ClickHouse, and the Parquet lake, the product reads the new platform end to end, and the live collector no longer depends on heavyweight SQLite history tables.

## What Happened

I read the task contract, slice plan, and prior T01/T02 summaries, then inspected the current dashboard, CLI, runtime, discovery, state-refresh, ClickHouse query adapter, and PostgreSQL mutable-truth code paths. I also read the focused dashboard/runtime tests and ran the task verification suite unchanged to establish a baseline before editing.

The investigation isolated the main remaining cutover gaps:

1. `vinted_radar/services/discovery.py` only opens `PostgresMutableTruthRepository` when `config.cutover.enable_polyglot_reads` is true, so a dual-write shadow configuration with PostgreSQL writes enabled still does **not** project live mutable truth into PostgreSQL.
2. `vinted_radar/services/state_refresh.py` emits evidence batches but does **not** directly project probe results into PostgreSQL mutable truth, so live item-page state can remain SQLite-only even when the platform write path is enabled.
3. `vinted_radar/query/overview_clickhouse.py` delegates `runtime_status()` to the wrapped SQLite repository. As a result, once the dashboard switches to ClickHouse-backed product reads, `/runtime`, `/health`, and the home-page runtime summary can still report SQLite control-plane data instead of PostgreSQL control-plane truth.
4. `vinted_radar/cli.py` only builds the PostgreSQL control-plane repository when `enable_polyglot_reads` is true, so `batch`, `continuous`, `runtime-status`, `runtime-pause`, and `runtime-resume` do not automatically use PostgreSQL control-plane truth during dual-write shadow mode.
5. Several CLI read commands (`state-summary`, `state`, `score`, `rankings`, `market-summary`, `history`) still open `RadarRepository` directly and therefore bypass the ClickHouse/PostgreSQL cutover stack entirely.

I stopped at that point because the explicit context-budget wrap-up warning arrived before I could safely implement and verify the full set of linked changes.

## Verification

Ran the task verification suite unchanged as a baseline:

- `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q`
- Result: 23 passed, 0 failed.

This proves the repository was green before T03 cutover edits started; no cutover implementation was shipped in this unit.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q` | 0 | ✅ pass | 1.15s |

## Diagnostics

Resume from these concrete entry points:

- `vinted_radar/query/overview_clickhouse.py` — thread a PostgreSQL control-plane repository into the ClickHouse-backed adapter so runtime/health surfaces stop inheriting SQLite control-plane state.
- `vinted_radar/dashboard.py` — update `_open_query_backend()` so the cutover dashboard opens both the ClickHouse analytics backend and the PostgreSQL control-plane backend together.
- `vinted_radar/cli.py` — broaden the control-plane repository helper so runtime commands and runtime-managed batch/continuous cycles use PostgreSQL whenever the mutable-truth platform path is active.
- `vinted_radar/services/discovery.py` — key live PostgreSQL mutable-truth projection off PostgreSQL write activation, not only the polyglot-read flag.
- `vinted_radar/services/state_refresh.py` — add direct PostgreSQL mutable-truth projection for probe results.
- After implementing, re-run:
  - `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q`
  - likely also the focused adjacent suites: `python3 -m pytest tests/test_runtime_cli.py tests/test_state_refresh_service.py tests/test_discovery_service.py -q`

## Deviations

No code changes were made once the context-budget wrap-up warning fired. I wrote resume notes instead of forcing a partially implemented cutover.

## Known Issues

Task T03 is **not finished**. The live product cutover behavior described above is still pending implementation.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S14/tasks/T03-SUMMARY.md` — Partial execution summary with exact resume notes and the verified baseline.
