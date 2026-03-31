---
id: T04
parent: S14
milestone: M002
provides:
  - Resume notes for the live cutover smoke proof and runbook task
key_files:
  - .gsd/milestones/M002/slices/S14/tasks/T04-SUMMARY.md
key_decisions:
  - Treat the live cutover proof as a direct verification of PostgreSQL mutable truth, ClickHouse ingest, object-storage evidence, and served polyglot routes instead of relying on runtime-cycle SQLite↔PostgreSQL reconciliation after the runtime control plane moved to PostgreSQL in T03.
patterns_established:
  - Under cutover, the reliable smoke path is: platform doctor -> real narrow live cycle -> ClickHouse ingest -> served route verification against polyglot reads.
observability_surfaces:
  - none
duration: partial session
verification_result: not-run
completed_at: 2026-03-31T13:24:00+02:00
blocker_discovered: false
---

# T04: Live cutover proof + runbook

**Started T04, audited the existing cutover surfaces, and left exact implementation notes for the next unit because context/time budget expired before code landed.**

## Slice Plan Excerpt
Source: `.gsd/milestones/M002/slices/S14/S14-PLAN.md`
**Goal:** Migrate historical continuity, cut reads and writes over to the new platform end to end, and retire the SQLite-heavy live loop from the real product path without losing auditability or product truth.
**Demo:** After this: After this: historical SQLite evidence is backfilled into PostgreSQL, ClickHouse, and the Parquet lake, the product reads the new platform end to end, and the live collector no longer depends on heavyweight SQLite history tables.

## What Happened

I read the T04 plan, the slice plan, `vinted_radar/cli.py`, `vinted_radar/dashboard.py`, `README.md`, the existing smoke/verification scripts, the platform health/cutover code, and the data-platform integration fixtures. I also reviewed T03’s summary to stay aligned with the already-shipped cutover behavior.

The main local reality check I found is important for the next unit: once PostgreSQL writes are enabled, the live runtime control-plane truth moves to PostgreSQL, so a post-cutover live batch cycle no longer naturally leaves matching `runtime_cycles` / `runtime_controller_state` rows in SQLite. That means the T04 live smoke proof should validate the live cutover directly through PostgreSQL mutable-truth rows, ClickHouse ingest status/data, object-storage evidence, and the served dashboard/runtime/health/detail routes, rather than treating `platform-reconcile` as the primary post-live-cycle proof for runtime tables. `platform-reconcile` still makes sense as the historical/backfill proof before or around cutover, but it is not the cleanest acceptance signal for the live runtime-control-plane path after T03.

## Verification

No code changes landed in this unit, so the task verification command was not run.

## Verification Evidence

No verification commands were run in this unit.

## Diagnostics

Relevant files already read and validated for the next unit:

- `.gsd/milestones/M002/slices/S14/S14-PLAN.md`
- `.gsd/milestones/M002/slices/S14/tasks/T04-PLAN.md`
- `.gsd/milestones/M002/slices/S14/tasks/T03-SUMMARY.md`
- `scripts/verify_vps_serving.py`
- `scripts/verify_clickhouse_routes.py`
- `tests/test_data_platform_smoke.py`
- `tests/test_dashboard.py`
- `tests/test_runtime_service.py`
- `tests/test_cli_smoke.py`
- `tests/conftest.py`
- `tests/test_reconciliation.py`
- `tests/test_full_backfill.py`
- `vinted_radar/platform/health.py`
- `vinted_radar/platform/config.py`
- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/services/state_refresh.py`
- `vinted_radar/services/runtime.py`
- `README.md`
- `install_services.sh`

## Deviations

None yet; no implementation landed.

## Known Issues

The non-obvious issue discovered during execution is the runtime reconciliation caveat described above: live runtime controller/cycle truth now lives in PostgreSQL under cutover, so a T04 smoke proof should not depend on SQLite runtime tables mirroring PostgreSQL after a real cutover batch cycle.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S14/tasks/T04-SUMMARY.md` — Partial execution summary plus precise resume notes.

## Precise Resume Notes

The next unit should continue from here without re-research and implement the originally planned T04 deliverables in this order:

1. **Update `scripts/verify_vps_serving.py`**
   - Keep current route smoke checks.
   - Add an optional `--expected-cutover-mode` flag.
   - When provided, verify `/api/runtime` and `/health` both surface that cutover mode.
   - Preserve current behavior for callers that do not pass the new flag.

2. **Create `scripts/verify_cutover_stack.py`**
   - Make it a rerunnable operational smoke proof, not a one-shot script.
   - Preferred proof shape:
     - load platform config and require `polyglot-cutover`
     - run `doctor_data_platform()` and fail if unhealthy
     - run `ClickHouseIngestService.from_environment(...).ingest_available(...)` so pending outbox rows are drained before checking read surfaces
     - inspect `load_clickhouse_ingest_status(...)` and fail on `failed`
     - inspect PostgreSQL mutable-truth surfaces directly via `PostgresMutableTruthRepository.from_dsn(...)`:
       - `latest_discovery_run()` must exist
       - `listing_current_state(listing_id)` must exist
       - `runtime_controller_state(now=...)` must exist
       - `runtime_cycle(latest_cycle_id)` must exist
     - inspect object storage directly and confirm there are non-marker objects under raw-events / manifests / parquet prefixes
     - verify served product routes by calling `verify_vps_serving.verify(..., expected_cutover_mode="polyglot-cutover")`
     - fetch `/api/dashboard` and assert `request.primary_payload_source == "clickhouse.overview_snapshot"`
     - fetch `/api/explorer` and assert it returns at least one tracked listing
   - Make the script support either:
     - `--base-url` to verify an already-running VPS/public deployment, or
     - starting a temporary local dashboard server itself when `--base-url` is omitted.
   - Add `--json` output for the test and for operator evidence capture.

3. **Create `tests/test_cutover_smoke.py`**
   - Reuse the real Docker-backed `data_platform_stack` fixture from `tests/conftest.py`.
   - Apply the stack env plus these four cutover flags as `true`:
     - `VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES`
     - `VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES`
     - `VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES`
     - `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS`
   - Run real `platform-bootstrap` against the Docker stack.
   - Drive a **real narrow live cycle** through the shipped `DiscoveryService` + `StateRefreshService` + `RadarRuntimeService`, but with a deterministic fake transport instead of live Vinted network calls.
     - Use `tests/fixtures/catalog-root.html` for the catalog tree HTML.
     - Build a tiny API catalog JSON payload in-test for one women leaf catalog (`2001`) with at least one listing and preferably two.
     - Return simple item-page HTML strings matching the `parse_item_page_probe()` regex, e.g. active and sold/deleted signals.
   - After the live cycle, invoke `python scripts/verify_cutover_stack.py ... --json` as a subprocess with the same platform env.
   - Assert the script exits 0 and that the proof JSON shows:
     - cutover mode `polyglot-cutover`
     - healthy platform doctor
     - non-failed ClickHouse ingest status
     - dashboard source `clickhouse.overview_snapshot`
     - serving checks include overview / explorer / runtime / runtime-api / listing-detail / listing-detail-api / health

4. **Update `README.md`**
   - Replace the stale “SQLite still remains the live product read path” wording with the current explicit cutover-mode contract:
     - `sqlite-primary`
     - `dual-write-shadow`
     - `polyglot-cutover`
   - Add a “Live cutover smoke proof” section documenting:
     - platform bootstrap / historical reconcile before read cutover
     - enabling the four cutover flags
     - running one narrow real batch cycle
     - running `python scripts/verify_cutover_stack.py ...`
   - Add a production VPS cutover + rollback runbook with exact operator steps.
   - The runbook should explain that the persistent VPS services need shared platform env vars through systemd drop-ins (or equivalent), because `install_services.sh` does not currently inject the platform/cutover env contract by itself.

5. **Then run the task verification**
   - `python -m pytest tests/test_cutover_smoke.py -q`

6. **If the implementation lands successfully in the next unit**
   - replace this partial summary with a proper completion summary
   - then call `gsd_complete_task`

This task is **not complete yet**. No code changes other than this partial summary were written in this unit.
