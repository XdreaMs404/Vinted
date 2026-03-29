# S11: Minimal Evidence Contract + Parquet Lake — UAT

**Milestone:** M002
**Written:** 2026-03-29T09:55:18.663Z

# S11: Minimal Evidence Contract + Parquet Lake — UAT

**Milestone:** M002  
**Written:** 2026-03-29

## UAT Type

- UAT mode: local evidence-lake / operator-backend acceptance
- Why this mode is sufficient: S11 is a backend data-platform slice. The acceptance question is whether collector proof shrinks to minimal envelopes, Parquet lake batches are immutable and inspectable, collector services can emit them idempotently, and legacy SQLite evidence can be backfilled plus drilled back down.

## Preconditions

- Repo dependencies from `pyproject.toml` are installed.
- Commands are run from the repo root.
- For direct CLI export/inspect against a real object store, the S10 platform object-store environment is configured and points to a reachable S3-compatible bucket/prefix.
- If you want the real MinIO-backed path, Docker is running locally and the S10 data-platform stack can be booted.
- A writable temporary directory is available for a seeded legacy SQLite smoke database.

## Test Cases

### 1. Re-prove the minimal listing-card evidence contract

1. Run `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q`.
2. **Expected:** the command passes.
3. **Expected details:** API and HTML parsers now emit a shared envelope with `schema_version`, `evidence_source`, and `fragments`, and normalization still accepts legacy flat raw-card payloads so historical observations remain explainable.

### 2. Re-prove immutable manifested Parquet batch writing

1. Run `python -m pytest tests/test_lake_writer.py -q`.
2. **Expected:** deterministic batch event / parquet / manifest keys, ZSTD-compressed parquet, and immutable-key checksum protection.
3. **Expected details:** writing the same batch twice reuses identical objects, and reusing a key for different bytes is rejected. If Docker-backed MinIO is available, the MinIO round-trip case also passes instead of skipping.

### 3. Re-prove collector emission from discovery and state refresh

1. Run `python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q`.
2. **Expected:** the command passes.
3. **Expected details:** discovery emits one deterministic listing-seen batch per accepted catalog page, state refresh emits one deterministic probe batch per refresh invocation, emitted batch refs surface on service reports, and runtime regressions remain green.

### 4. Export legacy SQLite evidence into the Parquet lake

1. Seed a legacy smoke database:

   ```bash
   python - <<'PY'
   from pathlib import Path
   from tests.test_evidence_export import _seed_legacy_evidence_db
   path = Path('tmp/s11-uat-legacy.db')
   path.parent.mkdir(parents=True, exist_ok=True)
   _seed_legacy_evidence_db(path)
   print(path)
   PY
   ```

2. Run `python -m vinted_radar.cli evidence-export --db tmp/s11-uat-legacy.db --format json`.
3. **Expected:** JSON output reports exactly three dataset groups (`discoveries`, `observations`, `probes`), explicit `vinted.backfill.*` event types, manifest/event IDs, row counts, and object keys under the configured lake prefixes.

### 5. Inspect exported evidence back down to a concrete fragment

1. From the previous JSON output, copy one discovery `event_id` and one probe `manifest_id`.
2. Run `python -m vinted_radar.cli evidence-inspect --event-id <discovery-event-id> --listing-id 9001 --field-path row.raw_card.price.amount --format json`.
3. **Expected:** the output resolves the matching event, manifest, parquet object key, selected row, and fragment value `99.00`.
4. Run `python -m vinted_radar.cli evidence-inspect --manifest-id <probe-manifest-id> --probe-id probe-20260328T200500-a1b2c3d4 --field-path row.detail.reason --format json`.
5. **Expected:** the output resolves the probe row and fragment value `anti_bot_challenge`.

## Edge Cases

### 6. Immutable-key protection must reject divergent rewrites

1. Re-run `python -m pytest tests/test_lake_writer.py -q` after modifying the batch payload in the relevant fixture or by calling the object-store helper with a different body under the same key.
2. **Expected:** the write is rejected with a checksum mismatch error rather than silently overwriting an existing object.

### 7. Evidence lookup must fail loudly on ambiguous multi-row batches

1. Run `python -m vinted_radar.cli evidence-inspect --event-id <discovery-event-id> --format json` without `--row-index`, `--listing-id`, or `--probe-id`.
2. **Expected:** the command exits non-zero and tells the operator to narrow the lookup because the batch contains multiple rows.

### 8. Direct CLI round-trip against the local MinIO stack

1. If Docker is available, start the local stack and bootstrap it:
   - `docker compose -f infra/docker-compose.data-platform.yml up -d`
   - `python -m vinted_radar.cli platform-bootstrap`
2. Repeat test cases 4 and 5 against the real local MinIO-backed object store.
3. **Expected:** export and inspect behave the same as the fixture-backed path, proving the operator-facing lake commands work end to end on the real stack.

## Failure Signals

- Parser/normalization tests start persisting heavyweight raw-card payloads again or stop accepting legacy payloads.
- Lake writer tests show non-deterministic object keys, missing manifests, or silent same-key overwrite behavior.
- Discovery/state-refresh tests stop surfacing emitted batch refs or lose idempotence across retries.
- `evidence-export` stops producing explicit `vinted.backfill.*` event types or `evidence-inspect` can no longer resolve `row.raw_card.*` / `row.detail.*` fragments.

## Requirements Proved By This UAT

- R016 — advances the production-style storage/operability posture by moving immutable raw proof onto a Parquet/object-store boundary with deterministic manifests and inspectable export tooling.
- R014 (advanced, not validated) — gives future grounded AI and evidence-linked summary work a stable raw-evidence contract and replayable lookup path instead of SQLite-bound JSON blobs.

## Not Proven By This UAT

- PostgreSQL current-state projection and control-plane cutover.
- ClickHouse serving warehouse and rollups.
- Full historical backfill of the real large SQLite corpus.
- Automated monitoring/alerting around lake-publish lag or failures.

## Cleanup

1. Remove `tmp/s11-uat-legacy.db` if it is no longer needed.
2. If Docker-backed MinIO was used, stop the stack with `docker compose -f infra/docker-compose.data-platform.yml down -v`.

