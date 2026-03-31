# VPS verification runbook

Run this from the VPS after `git pull` when you want to verify the deployed M002 stack.

This repo now has two useful verification levels:

1. **short checks** — fast smoke checks after deploy, restart, config change, or cutover-flag change
2. **long proof** — a fuller end-to-end M002 cutover proof when you want strong operational confidence

You can run those sequences manually from this document, or use the repo helper script:

```bash
scripts/run_vps_verification.sh --help
```

The remaining M002 validation note came from the fact that the full cutover proof was not rerun in a Docker-capable environment during local closeout. The VPS is the right place to do that.

---

## 0. Assumptions

Adjust these values to your VPS:

```bash
export VINTED_RADAR_REPO=/srv/vinted-radar
export VINTED_RADAR_DB=data/vinted-radar.db
export VINTED_RADAR_BASE_URL=https://your-domain.example/radar
```

If you serve the app without a mounted base path, use:

```bash
export VINTED_RADAR_BASE_URL=http://127.0.0.1:8765
```

Enter the repo and refresh it:

```bash
cd "$VINTED_RADAR_REPO"
git pull --ff-only
```

If the Python package is not already installed in the active environment:

```bash
python3 -m pip install -e .
```

For the helper scripts under `scripts/`, prefer `PYTHONPATH=.` so imports are explicit and stable:

```bash
export PYTHONPATH=.
```

Use the **same environment contract as the running services**:

- same platform env vars
- same cutover flags
- same database path
- same object-store / PostgreSQL / ClickHouse endpoints

If your app is managed by systemd, make sure your shell has the same env as the service before trusting the results.

---

## 1. Short checks

Use this after:

- deploy
- service restart
- reverse-proxy / base-path change
- cutover-flag change
- infra maintenance

### 1A. Fast operator health checks

```bash
python3 -m vinted_radar.cli platform-doctor
python3 -m vinted_radar.cli platform-audit --db "$VINTED_RADAR_DB" --format json
python3 -m vinted_radar.cli runtime-status --db "$VINTED_RADAR_DB" --format json
python3 -m vinted_radar.cli platform-lifecycle --dry-run
```

### 1B. Public-serving smoke check

Pick a real listing id currently present in the deployed product and run:

```bash
python3 scripts/verify_vps_serving.py \
  --base-url "$VINTED_RADAR_BASE_URL" \
  --listing-id <REAL_LISTING_ID> \
  --expected-cutover-mode polyglot-cutover
```

### Short-check success criteria

You want all of this to be true:

- `platform-doctor` is healthy
- `platform-audit` reports:
  - reconciliation `match`
  - current-state path `healthy` or `active`
  - analytical path `healthy` or `active`
  - backfill path `healthy` or `complete`
  - lifecycle posture not `failed`
- `runtime-status` matches reality
- `verify_vps_serving.py` passes on:
  - `/`
  - `/explorer`
  - `/runtime`
  - `/listings/<id>`
  - `/api/runtime`
  - `/api/listings/<id>`
  - `/health`

---

## 2. Long proof — full M002 cutover verification

Use this when you want a stronger acceptance proof than the short smoke.

### 2A. Ensure the platform stack is up

If the VPS uses the repo's Docker stack for PostgreSQL + ClickHouse + object storage:

```bash
docker compose -f infra/docker-compose.data-platform.yml up -d
```

Then bootstrap and verify the platform:

```bash
python3 -m vinted_radar.cli platform-bootstrap
python3 -m vinted_radar.cli platform-doctor
```

### 2B. Check reconciliation and audit posture

```bash
python3 -m vinted_radar.cli platform-reconcile --db "$VINTED_RADAR_DB"
python3 -m vinted_radar.cli platform-audit --db "$VINTED_RADAR_DB" --format json
```

### 2C. Verify the cutover flags

The final M002 proof expects **polyglot cutover**:

```bash
export VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES=true
export VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES=true
export VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES=true
export VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=true
```

If your services are started by systemd, verify these are the values the service really uses before trusting the proof.

### 2D. Run one real but narrow collector cycle

```bash
python3 -m vinted_radar.cli batch \
  --db "$VINTED_RADAR_DB" \
  --page-limit 1 \
  --max-leaf-categories 1 \
  --state-refresh-limit 2
```

This is intentionally narrow. The goal is not a heavy crawl, but a fresh real run that exercises the live cutover path.

### 2E. Run the authoritative end-to-end proof

If you want the script to verify the already served public URL:

```bash
python3 scripts/verify_cutover_stack.py \
  --db-path "$VINTED_RADAR_DB" \
  --base-url "$VINTED_RADAR_BASE_URL" \
  --expected-cutover-mode polyglot-cutover \
  --json
```

If you want the script to start a temporary local dashboard itself instead:

```bash
python3 scripts/verify_cutover_stack.py \
  --db-path "$VINTED_RADAR_DB" \
  --expected-cutover-mode polyglot-cutover \
  --json
```

### Long-proof success criteria

`verify_cutover_stack.py` should prove all of this:

- the stack reports `polyglot-cutover`
- `platform-doctor` is healthy across PostgreSQL, ClickHouse, and object storage
- ClickHouse ingest drains pending outbox work without ending in `failed`
- `platform-audit` is healthy enough for acceptance:
  - reconciliation `match`
  - current-state `healthy` or `active`
  - analytical `healthy` or `active`
  - backfill `healthy` or `complete`
  - lifecycle not `failed`
- PostgreSQL mutable truth exposes real current-state / runtime rows
- ClickHouse feature marts are populated
- change facts are present and fresh
- evidence packs include manifest / event traceability
- object storage contains real non-marker objects
- product HTML + JSON routes still work on the cutover stack
- `/api/dashboard` is really serving the ClickHouse overview path

If this passes on the VPS, you have the missing operational proof that M002 closeout wanted.

---

## 3. Optional targeted pytest runs on the VPS

### Short pytest bundle

```bash
python3 -m pytest \
  tests/test_platform_audit.py \
  tests/test_feature_marts.py \
  tests/test_reconciliation.py \
  tests/test_clickhouse_queries.py \
  -q
```

### Heavier pytest bundle

```bash
python3 -m pytest \
  tests/test_full_backfill.py \
  tests/test_clickhouse_ingest.py \
  tests/test_cutover_smoke.py \
  -q
```

### Closeout-style pytest bundle

```bash
python3 -m pytest \
  tests/test_dashboard.py \
  tests/test_runtime_cli.py \
  tests/test_clickhouse_queries.py \
  tests/test_full_backfill.py \
  tests/test_platform_audit.py \
  tests/test_cutover_smoke.py \
  tests/test_feature_marts.py \
  tests/test_reconciliation.py \
  -q
```

---

## 4. Failure triage

### `verify_vps_serving.py` fails

Check, in this order:

1. reverse proxy / base path
2. dashboard service status
3. `/health`
4. `runtime-status`
5. whether the listing id you passed is still valid on that environment

### `platform-audit` fails

Treat it as a real signal. Look for drift in:

- reconciliation
- ingest lag
- lifecycle posture
- backfill posture

### `verify_cutover_stack.py` fails

Do **not** treat the cutover as clean.

Fix the failing layer first:

- platform doctor
- reconciliation
- audit posture
- ClickHouse ingest
- feature marts / change facts
- route parity
- object storage evidence presence

Then rerun the long proof.

---

## 5. Recommended operator routine

### After each deploy or service restart

```bash
cd "$VINTED_RADAR_REPO"
export PYTHONPATH=.
python3 -m vinted_radar.cli platform-doctor
python3 -m vinted_radar.cli platform-audit --db "$VINTED_RADAR_DB" --format json
python3 scripts/verify_vps_serving.py \
  --base-url "$VINTED_RADAR_BASE_URL" \
  --listing-id <REAL_LISTING_ID> \
  --expected-cutover-mode polyglot-cutover
```

### When you want the full M002 proof

```bash
cd "$VINTED_RADAR_REPO"
export PYTHONPATH=.
python3 -m vinted_radar.cli platform-bootstrap
python3 -m vinted_radar.cli platform-reconcile --db "$VINTED_RADAR_DB"
python3 -m vinted_radar.cli platform-audit --db "$VINTED_RADAR_DB" --format json
python3 -m vinted_radar.cli batch \
  --db "$VINTED_RADAR_DB" \
  --page-limit 1 \
  --max-leaf-categories 1 \
  --state-refresh-limit 2
python3 scripts/verify_cutover_stack.py \
  --db-path "$VINTED_RADAR_DB" \
  --base-url "$VINTED_RADAR_BASE_URL" \
  --expected-cutover-mode polyglot-cutover \
  --json
```

---

## 6. Notes

- Use `python3`, not `python`, unless your VPS shell explicitly provides `python`.
- Use a **real listing id** that exists in the deployed environment for `verify_vps_serving.py`.
- Keep this runbook aligned with the live service env. Testing with the wrong shell env is how you get false confidence.
- If you later automate this, the most useful recurring commands are:
  - `platform-audit`
  - `platform-lifecycle --dry-run` or `platform-lifecycle`
  - `verify_vps_serving.py`
  - `verify_cutover_stack.py` for explicit release-grade proof
