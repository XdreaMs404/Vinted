# S10: Polyglot Data Platform Foundation — UAT

**Milestone:** M002
**Written:** 2026-03-28T19:56:16.403Z

# S10: Polyglot Data Platform Foundation — UAT

**Milestone:** M002  
**Written:** 2026-03-28

## UAT Type

- UAT mode: local-platform-bootstrap
- Why this mode is sufficient: S10 is a backend/platform-foundation slice. The acceptance question is whether the repo can boot PostgreSQL + ClickHouse + MinIO locally, expose truthful bootstrap/doctor diagnostics, and prove deterministic event/outbox/manifests plumbing end to end.

## Preconditions

- Docker Desktop or a compatible Docker runtime is running locally.
- The repo dependencies are installed from `pyproject.toml`.
- No conflicting local services are bound to the default platform ports, or the operator has set the env-substituted overrides used by `infra/docker-compose.data-platform.yml` (`VINTED_RADAR_PLATFORM_POSTGRES_PORT`, `VINTED_RADAR_PLATFORM_CLICKHOUSE_HTTP_PORT`, `VINTED_RADAR_PLATFORM_CLICKHOUSE_NATIVE_PORT`, `VINTED_RADAR_PLATFORM_OBJECT_STORE_PORT`, `VINTED_RADAR_PLATFORM_OBJECT_STORE_CONSOLE_PORT`).
- Commands are run from the repo root.

## Test Cases

### 1. Boot the local data-platform stack

1. Run `docker compose -f infra/docker-compose.data-platform.yml up -d`.
2. Wait for the containers to become healthy.
3. **Expected:** PostgreSQL, ClickHouse, and MinIO start successfully; if default ports are unavailable, the stack can still boot with the documented env-substituted port overrides.

### 2. Bootstrap schemas and object-storage prefixes

1. Run `python -m vinted_radar.cli platform-bootstrap`.
2. Review the rendered report.
3. **Expected:** the command exits `0`, prints `Mode: bootstrap`, reports `PostgreSQL: ok`, `ClickHouse: ok`, `Object storage: ok`, and `Healthy: yes`, shows PostgreSQL migrations through `V002`, ClickHouse through `V001`, and confirms bucket/prefix readiness plus object-store write probes for `raw_events`, `manifests`, and `parquet`.

### 3. Verify steady-state platform health

1. Run `python -m vinted_radar.cli platform-doctor`.
2. Review the rendered report.
3. **Expected:** the command exits `0`, prints `Mode: doctor`, keeps all three subsystems `ok`, preserves the same current schema versions (`postgres=2`, `clickhouse=1`), and reports successful write probes instead of pending migrations or bucket errors.

### 4. Verify the deterministic contract tests

1. Run `python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q`.
2. **Expected:** all tests pass.
3. **Expected details:** the tests prove deterministic event IDs, deterministic manifest IDs/checksums, JSON round-trips, idempotent `(event_id, sink)` outbox publishing, leased claim/retry behavior, and delivery completion semantics.

### 5. Run the end-to-end platform smoke proof

1. Run `python -m pytest tests/test_data_platform_smoke.py -q`.
2. **Expected:** the test passes and proves a real end-to-end path: isolated Docker stack startup, `platform-bootstrap`, PostgreSQL V001/V002 application, ClickHouse V001 application, bucket/prefix readiness, a real outbox publish, a real manifest object write/read in MinIO, and a healthy `platform-doctor` result afterward.

## Edge Cases

### 6. Re-running bootstrap must remain idempotent

1. Run `python -m vinted_radar.cli platform-bootstrap` a second time against the same running stack.
2. **Expected:** the command still exits `0` and stays healthy; already-applied migrations are not duplicated, and bucket/prefix checks remain clean.

### 7. Doctor must fail loudly on schema drift

1. Temporarily set an impossible expected version, for example `VINTED_RADAR_PLATFORM_POSTGRES_SCHEMA_VERSION=999` in the shell running the command.
2. Run `python -m vinted_radar.cli platform-doctor`.
3. **Expected:** the command exits non-zero, prints `Healthy: no`, and surfaces PostgreSQL pending-version drift rather than silently reporting success.
4. Remove the override and rerun `python -m vinted_radar.cli platform-doctor`.
5. **Expected:** health returns to green.

## Failure Signals

- `platform-bootstrap` or `platform-doctor` exits non-zero.
- The rendered report shows `pending` migrations, checksum drift, `bucket-missing`, or failed write probes.
- The deterministic contract tests fail, indicating envelope/manifest IDs or outbox leasing semantics are no longer stable.
- The smoke test cannot publish the outbox event, cannot read/write the manifest object, or no longer reports the platform healthy after bootstrap.

## Requirements Proved By This UAT

- R016 — proves the project now has a production-style data-platform bootstrap, schema-versioning, and readiness-check foundation instead of relying only on the monolithic SQLite boundary.
- R014 (foundationally advanced, not validated) — proves the repo now has deterministic, evidence-linkable event and manifest contracts that future grounded AI/evidence slices can build on.

## Not Proven By This UAT

- Real evidence export into Parquet/object storage at production volume.
- PostgreSQL current-state projection or ClickHouse analytical serving.
- Historical SQLite backfill or full product cutover onto the new platform.
- Continuous remote/VPS monitoring or automated alerting.

## Cleanup

1. Run `docker compose -f infra/docker-compose.data-platform.yml down -v` when finished if the stack is no longer needed.
2. **Expected:** the local platform containers and volumes are removed cleanly.

## Notes for Tester

The quickest truthful acceptance loop for this slice is: boot the Docker stack, run `platform-bootstrap`, run `platform-doctor`, then run `python -m pytest tests/test_event_envelope.py tests/test_outbox.py tests/test_data_platform_smoke.py -q` if you want one compact proof of the deterministic contract plus the real stack path.
