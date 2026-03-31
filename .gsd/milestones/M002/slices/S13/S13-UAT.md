# S13: ClickHouse Serving Warehouse + Rollups — UAT

**Milestone:** M002
**Written:** 2026-03-31T11:47:34.383Z

# S13: ClickHouse Serving Warehouse + Rollups — UAT

**Milestone:** M002

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S13 is primarily a serving-platform slice. The highest-value acceptance proof is focused schema/ingest/query/parity regression plus operator diagnostics and route-proof evidence, not manual browsing against an as-yet-unbackfilled live corpus.

## Preconditions

- Python dependencies from `pyproject.toml` are installed.
- Run from the project root.
- No live ClickHouse stack is required for this UAT because the slice proof uses temporary SQLite fixtures plus scripted ClickHouse support for parity verification.
- Use `python3`, not `python`, in this shell.

## Smoke Test

1. Run `python3 -m pytest tests/test_clickhouse_schema.py tests/test_clickhouse_ingest.py tests/test_clickhouse_queries.py tests/test_dashboard.py tests/test_clickhouse_parity.py -q`.
2. Wait for the command to finish.
3. **Expected:** The suite exits `0` with 30 passing tests, proving the serving schema, replay-safe ingest, ClickHouse product adapter, dashboard contract preservation, and parity verifier together.

## Test Cases

### 1. ClickHouse warehouse schema contract

1. Run `python3 -m pytest tests/test_clickhouse_schema.py -q`.
2. Review the migration/schema assertions.
3. **Expected:** The suite exits `0`, proving V002 raw facts, rollups, latest-serving tables, TTL policy, and materialized-view wiring all exist as expected.

### 2. Replay-safe serving ingest plus checkpoint status

1. Run `python3 -m pytest tests/test_clickhouse_ingest.py -q`.
2. Review the replay, partial-retry, failure-state, and CLI status coverage.
3. **Expected:** The suite exits `0`, and the ingest/status contract proves deterministic row ids, missing-row-only inserts, checkpoint lag/error persistence, and operator-facing CLI output.

### 3. ClickHouse-backed overview/explorer/detail read path

1. Run `python3 -m pytest tests/test_clickhouse_queries.py tests/test_dashboard.py -q`.
2. Confirm the adapter and dashboard route tests pass.
3. **Expected:** The suite exits `0`, and overview/explorer/detail payload builders stay contract-compatible while the analytical read source switches to ClickHouse.

### 4. Route parity verifier and backend-shape normalization

1. Run `python3 -m pytest tests/test_clickhouse_parity.py -q`.
2. Confirm the parity suite passes.
3. **Expected:** The suite exits `0`, and the reusable route verifier proves repository-backed and ClickHouse-backed JSON payloads match after normalization while ClickHouse HTML dashboard/explorer/detail routes still return 200.

## Edge Cases

### Direct diagnostic proof of route parity and latency

1. Run a direct Python invocation of `verify_clickhouse_routes(...)` against a temporary seeded dashboard database using `tests.test_dashboard._seed_dashboard_db(...)` and `tests.clickhouse_product_test_support.make_clickhouse_product_client()`.
2. Inspect the returned proof JSON.
3. **Expected:** `dashboard_api`, `explorer_api`, `detail_api`, and `health` all report `match`, ClickHouse HTML dashboard/explorer/detail routes all return `200`, and both repository and ClickHouse route timings are present.

### Operator-facing ingest checkpoint JSON

1. Run a direct CLI smoke for `python3 -m vinted_radar.cli clickhouse-ingest-status --format json` with the task-test checkpoint fixture injected.
2. Inspect the JSON payload.
3. **Expected:** The payload includes `consumer_name`, `status`, `lag_seconds`, `last_outbox_id`, `last_event_id`, `last_manifest_id`, and `metadata.target_table`.

## Failure Signals

- Any failure in `tests/test_clickhouse_schema.py`, `tests/test_clickhouse_ingest.py`, `tests/test_clickhouse_queries.py`, `tests/test_dashboard.py`, or `tests/test_clickhouse_parity.py`.
- `clickhouse-ingest-status` missing checkpoint metadata or reporting a persistent `failed` status after a retry/recovery attempt.
- `verify_clickhouse_routes(...)` reporting a parity mismatch, a non-200 route, or a dashboard source drift away from the expected repository/ClickHouse payload source markers.

## Requirements Proved By This UAT

- R008 — proves the market-summary serving path can be sourced from ClickHouse rollups/latest-serving primitives while preserving the existing overview contract.
- R009 — proves explorer and listing-detail analytical payloads can be served from ClickHouse without breaking existing route/drill-down contracts.
- R016 — proves the production-grade platform migration now includes a replay-safe, observable analytical serving warehouse rather than relying on SQLite historical scans.

## Not Proven By This UAT

- S14 historical backfill and live application cutover onto the new serving boundary.
- Real large-corpus ClickHouse serving over migrated historical data.
- S15 retention, reconciliation, or AI-ready feature marts.
- VPS/live-environment proof of the ClickHouse read path after backfill.

## Notes for Tester

- Favor the focused regression and diagnostic commands above over ad-hoc manual browsing; this slice is about the serving seam and parity proof.
- If a command fails because `python` is missing, rerun it with `python3`; that is expected in this shell.
- During S14 cutover, reuse `scripts/verify_clickhouse_routes.py` as the first acceptance gate before flipping live analytical reads.
