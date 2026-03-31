# S14: Historical Backfill + Application Cutover — UAT

**Milestone:** M002
**Written:** 2026-03-31T14:17:42.144Z

# S14 UAT — Historical Backfill + Application Cutover

## Objective
Prove that historical SQLite evidence can be migrated into PostgreSQL, ClickHouse, and Parquet-backed object storage, that cutover state is explicit on operator and product surfaces, and that the application can read the new platform end to end with a documented rollback path.

## Acceptance checks
1. **Historical backfill:** `python3 -m pytest tests/test_full_backfill.py -q`
   - Expected: resumable full-backfill flow passes with checkpoint, dry-run, PostgreSQL projection, ClickHouse replay, and lake-manifest coverage.
2. **Reconciliation + observability:** `python3 -m pytest tests/test_reconciliation.py -q`
   - Expected: SQLite/PostgreSQL/ClickHouse/object-storage reconciliation passes and runtime/health surfaces expose explicit cutover mode, read path, and write targets.
3. **Application/runtime cutover:** `python3 -m pytest tests/test_dashboard.py tests/test_runtime_service.py -q` and `python3 -m pytest tests/test_runtime_cli.py -q`
   - Expected: dashboard/runtime payloads and CLI control-plane behavior pass on the polyglot path, while `dual-write-shadow` still reads runtime status from SQLite.
4. **Cutover smoke proof:** `python3 -m pytest tests/test_cutover_smoke.py -q`
   - Expected: exit 0; in environments without Docker this should skip cleanly rather than fail.
5. **Public-route smoke fallback:** `python3 -m pytest tests/test_cli_smoke.py tests/test_cutover_smoke.py -q`
   - Expected: public-serving smoke remains green and the cutover smoke keeps a clean skip when Docker is unavailable.

## Result
**Pass with environment note.** All slice-level verification checks passed. The only environment constraint was the Docker-backed live cutover smoke, which skipped cleanly because this shell does not provide a `docker` binary.

## Operator notes
- `dual-write-shadow` keeps SQLite as the operator and product read path while platform writes shadow in PostgreSQL, ClickHouse, and object storage.
- `polyglot-cutover` moves product and runtime reads onto PostgreSQL + ClickHouse.
- Before and after a real rollout, operators should run `scripts/verify_cutover_stack.py` and `scripts/verify_vps_serving.py` from the same environment contract used by the services.
- Rollback remains: disable `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS`, disable platform write flags if the platform itself is unhealthy, restart dashboard first, then restart collector/runtime, and rerun the serving smoke.
