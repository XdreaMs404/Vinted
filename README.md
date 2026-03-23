# Vinted Radar

Local-first batch collector and analysis stack for Vinted Homme/Femme market signals, using Vinted's web catalog API for discovery and public item-page probes for state evidence.

## Quick start

### One batch cycle

```bash
python -m vinted_radar.cli batch \
  --db data/vinted-radar.db \
  --page-limit 1 \
  --max-leaf-categories 6 \
  --state-refresh-limit 10
```

This runs one coherent radar cycle:

1. catalog discovery through the Vinted web API
2. listing persistence / observation updates
3. item-page probe refresh for selected listings
4. persisted runtime-cycle diagnostics in SQLite

### Continuous local loop

```bash
python -m vinted_radar.cli continuous \
  --db data/vinted-radar.db \
  --page-limit 1 \
  --max-leaf-categories 4 \
  --state-refresh-limit 6 \
  --interval-seconds 1800 \
  --dashboard \
  --host 127.0.0.1 \
  --port 8765
```

This keeps the radar alive locally and serves the French market overview home from the same DB while cycles continue in the background process.

## Current entrypoints

### Operator workflow

- `python -m vinted_radar.cli batch --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --state-refresh-limit 10`
- `python -m vinted_radar.cli continuous --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --interval-seconds 1800 --dashboard --host 127.0.0.1 --port 8765`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar.db`
- `python -m vinted_radar.cli runtime-pause --db data/vinted-radar.db`
- `python -m vinted_radar.cli runtime-resume --db data/vinted-radar.db`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar.db --host 127.0.0.1 --port 8765`
- French market overview home: `http://127.0.0.1:8765/`
- Dedicated runtime page: `http://127.0.0.1:8765/runtime`
- SQL-backed listing explorer: `http://127.0.0.1:8765/explorer`

### Focused diagnostics

- `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6`
- `python -m vinted_radar.cli db-health --db data/vinted-radar.db --integrity`
- `python -m vinted_radar.cli coverage --db data/vinted-radar.db`
- `python -m vinted_radar.cli freshness --db data/vinted-radar.db`
- `python -m vinted_radar.cli revisit-plan --db data/vinted-radar.db --limit 10`
- `python -m vinted_radar.cli history --db data/vinted-radar.db --listing-id <id>`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar.db --limit 10`
- `python -m vinted_radar.cli state-summary --db data/vinted-radar.db`
- `python -m vinted_radar.cli state --db data/vinted-radar.db --listing-id <id>`
- `python -m vinted_radar.cli rankings --db data/vinted-radar.db --kind demand --limit 10`
- `python -m vinted_radar.cli rankings --db data/vinted-radar.db --kind premium --limit 10`
- `python -m vinted_radar.cli market-summary --db data/vinted-radar.db --limit 8`
- `python -m vinted_radar.cli score --db data/vinted-radar.db --listing-id <id>`

## Overview + diagnostics routes

- French overview home: `http://127.0.0.1:8765/`
- Dedicated runtime page: `http://127.0.0.1:8765/runtime`
- SQL-backed explorer: `http://127.0.0.1:8765/explorer`
- JSON overview payload (compat dashboard endpoint): `http://127.0.0.1:8765/api/dashboard`
- JSON explorer payload: `http://127.0.0.1:8765/api/explorer`
- JSON runtime payload: `http://127.0.0.1:8765/api/runtime`
- JSON listing detail payload: `http://127.0.0.1:8765/api/listings/<id>`
- Health check: `http://127.0.0.1:8765/health`

## Runtime diagnostics

`runtime_cycles` remains the immutable per-cycle history, but current scheduler truth now lives in `runtime_controller_state`.

The controller snapshot can represent:

- current runtime status (`running`, `scheduled`, `paused`, `failed`, `idle`)
- current phase (`waiting`, `paused`, `discovery`, `state_refresh`, etc.)
- `updated_at` heartbeat for staleness detection
- `paused_at` plus elapsed pause time
- `next_resume_at` plus remaining wait time
- the active cycle id and latest linked cycle id
- persisted last error and operator pause/resume requests

Each cycle in `runtime_cycles` still records:

- mode (`batch` or `continuous`)
- cycle status (`running`, `completed`, `failed`, `interrupted`)
- cycle phase (`starting`, `discovery`, `state_refresh`, `summarizing`, `completed`)
- linked discovery run id when available
- state probe limit and actual probed count
- tracked listing count plus freshness snapshot
- last error when a cycle fails

Use these surfaces depending on the question:

- `python -m vinted_radar.cli runtime-status --db data/vinted-radar.db`
- `python -m vinted_radar.cli runtime-pause --db data/vinted-radar.db`
- `python -m vinted_radar.cli runtime-resume --db data/vinted-radar.db`
- runtime page: `http://127.0.0.1:8765/runtime`
- JSON runtime payload: `http://127.0.0.1:8765/api/runtime`

A healthy waiting loop should now appear as `scheduled`, not as a misleadingly "completed" runtime.

## Database safety

Check whether a copied database is actually healthy before trusting dashboard or coverage output:

```bash
python -m vinted_radar.cli db-health --db data/vinted-radar.db --integrity
```

Safely synchronize a VPS database by creating a consistent SQLite snapshot remotely, copying it locally to a temporary file, health-checking it, then promoting it atomically:

```bash
python scripts/sync_db_safe.py \
  --remote-host root@46.225.113.129 \
  --remote-db /root/Vinted/data/vinted-radar.db \
  --destination data/vinted-radar.db \
  --integrity
```

Recover a structurally healthy partial emergency copy when the source database is already corrupted:

```bash
python scripts/recover_partial_db.py \
  --source data/vinted-radar.db \
  --destination data/vinted-radar.recovered.db \
  --report data/vinted-radar.recovered.report.json \
  --force
```

This avoids exposing a half-copied or WAL-incomplete file as the live local database.

## Clean restart after corruption

Use three distinct database roles after a corruption event:

- `data/vinted-radar.db` → keep as the corrupted source artifact; do not trust it for market output.
- `data/vinted-radar.recovered.db` → keep as the healthy partial operator rescue copy.
- `data/vinted-radar.clean.db` → use as the new working database for fresh discovery runs.

Recommended restart sequence:

```bash
python -m vinted_radar.cli db-health --db data/vinted-radar.recovered.db
python -m vinted_radar.cli batch \
  --db data/vinted-radar.clean.db \
  --page-limit 1 \
  --max-leaf-categories 6 \
  --state-refresh-limit 10
python -m vinted_radar.cli db-health --db data/vinted-radar.clean.db
```

For a local always-on loop with the separated explorer surface:

```bash
python -m vinted_radar.cli continuous \
  --db data/vinted-radar.clean.db \
  --page-limit 1 \
  --max-leaf-categories 4 \
  --state-refresh-limit 6 \
  --interval-seconds 1800 \
  --dashboard \
  --host 127.0.0.1 \
  --port 8765
```

Then use:

- overview home → `http://127.0.0.1:8765/`
- explorer → `http://127.0.0.1:8765/explorer`
- runtime page → `http://127.0.0.1:8765/runtime`
- runtime truth JSON → `http://127.0.0.1:8765/api/runtime`
