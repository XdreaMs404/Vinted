# Vinted Radar

Local-first batch collector and analysis stack for Vinted Homme/Femme market signals, using Vinted's web catalog API for discovery and public item-page probes for state evidence.

## Quick start

Acquisition now defaults to the bounded API posture: `--min-price 30` and `--max-price 0` on the real acquisition entrypoints (`discover`, `batch`, `continuous`). Use `--min-price 0` only when you explicitly want an unbounded debug or benchmark run.

## Acquisition benchmark CLI

Use the acquisition benchmark commands when you want a reproducible scorecard from persisted SQLite/runtime windows rather than ad hoc SQL or notebooks.

### Compare benchmark specs and write artifacts

```bash
python -m vinted_radar.cli acquisition-benchmark \
  --spec-file specs/baseline-fr-page1.json \
  --spec-file specs/candidate-fr-page2.json
```

When `--json-out` / `--markdown-out` are omitted, the command writes both artifacts under `artifacts/acquisition-benchmarks/` and prints the explicit artifact paths.

Spec file contract (one JSON object per file, or one file containing a JSON array of objects):

```json
{
  "experiment_id": "baseline-fr-page1",
  "profile": "baseline-fr-page1",
  "label": "Baseline FR page_limit=1",
  "db_path": "data/vinted-radar.db",
  "window_started_at": "2026-03-25T09:00:00+00:00",
  "window_finished_at": "2026-03-25T10:30:00+00:00",
  "config": {
    "proxy": "http://user:pass@proxy.example:8080",
    "page_limit": 1
  },
  "storage_snapshots": [
    {"captured_at": "2026-03-25T09:00:00+00:00", "listing_count": 100, "db_size_bytes": 50000, "artifact_size_bytes": 5000},
    {"captured_at": "2026-03-25T10:30:00+00:00", "listing_count": 112, "db_size_bytes": 51800, "artifact_size_bytes": 5600}
  ],
  "resource_snapshots": [
    {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 30.0, "rss_mb": 240.0},
    {"captured_at": "2026-03-25T10:15:00+00:00", "cpu_percent": 34.0, "rss_mb": 252.0}
  ]
}
```

Notes:

- `db_path`, `window_started_at`, `window_finished_at`, and `experiment_id` are required.
- Relative `db_path` values resolve from the spec file directory.
- Proxy URLs, DSNs, tokens, and password-shaped config keys are redacted in both stdout and written artifacts.

### Inspect or re-render an existing benchmark payload

```bash
python -m vinted_radar.cli acquisition-benchmark-report \
  --input artifacts/acquisition-benchmarks/acquisition-benchmark-20260325T103000Z.json
```

`acquisition-benchmark-report` accepts either a full report JSON payload, a VPS runner bundle containing `benchmark_report`, or a raw JSON array / object containing `experiments`, then renders the leaderboard as table/json/markdown and can optionally re-export redacted JSON/Markdown artifacts.

## Polyglot data-platform foundation (M002/S10)

The repo now carries the shared configuration contract for the long-term PostgreSQL + ClickHouse + S3-compatible storage platform in `vinted_radar.platform.config`.

Current posture:

- The platform contract now has three explicit operating modes instead of one vague migration state:
  - `sqlite-primary` — reads stay on SQLite and platform writes stay off.
  - `dual-write-shadow` — SQLite remains the operator/product read path while PostgreSQL + ClickHouse + object storage are written in parallel for shadow validation.
  - `polyglot-cutover` — product reads switch to ClickHouse + PostgreSQL while collector writes continue landing in PostgreSQL + ClickHouse + object storage.
- The platform settings define the durable boundary for bootstrap, migrations, outbox/event delivery, object-storage manifests, and cutover observability.
- All four cutover flags still default to `false`, so adding platform credentials alone does not switch the product. The live mode is determined by these flags:
  - `VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES`
  - `VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES`
  - `VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES`
  - `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS`

Install/base dependency additions in `pyproject.toml`:

- PostgreSQL: `psycopg`
- ClickHouse: `clickhouse-connect`
- Parquet: `pyarrow`
- S3-compatible storage: `boto3`

Shared environment contract loaded by `load_platform_config()`:

| Variable | Default | Purpose |
|---|---|---|
| `VINTED_RADAR_PLATFORM_POSTGRES_DSN` | `postgresql://vinted:vinted@127.0.0.1:5432/vinted_radar` | PostgreSQL control-plane DSN. |
| `VINTED_RADAR_PLATFORM_CLICKHOUSE_URL` | `http://127.0.0.1:8123` | ClickHouse HTTP endpoint. |
| `VINTED_RADAR_PLATFORM_CLICKHOUSE_DATABASE` | `vinted_radar` | ClickHouse database name. |
| `VINTED_RADAR_PLATFORM_CLICKHOUSE_USERNAME` | `default` | ClickHouse username. |
| `VINTED_RADAR_PLATFORM_CLICKHOUSE_PASSWORD` | empty | ClickHouse password. |
| `VINTED_RADAR_PLATFORM_OBJECT_STORE_ENDPOINT` | `http://127.0.0.1:9000` | S3-compatible endpoint (MinIO locally by default). |
| `VINTED_RADAR_PLATFORM_OBJECT_STORE_BUCKET` | `vinted-radar` | Bucket for manifests, Parquet, and raw evidence objects. |
| `VINTED_RADAR_PLATFORM_OBJECT_STORE_REGION` | `us-east-1` | Region value for the S3 client. |
| `VINTED_RADAR_PLATFORM_OBJECT_STORE_ACCESS_KEY` | `minioadmin` | Object-store access key. |
| `VINTED_RADAR_PLATFORM_OBJECT_STORE_SECRET_KEY` | `minioadmin` | Object-store secret key. |
| `VINTED_RADAR_PLATFORM_OBJECT_STORE_PREFIX` | `vinted-radar` | Root object prefix. |
| `VINTED_RADAR_PLATFORM_RAW_EVENTS_PREFIX` | `<root>/events/raw` | Raw event-envelope/object prefix. |
| `VINTED_RADAR_PLATFORM_MANIFESTS_PREFIX` | `<root>/manifests` | Evidence/outbox manifest prefix. |
| `VINTED_RADAR_PLATFORM_PARQUET_PREFIX` | `<root>/parquet` | Parquet/warehouse object prefix. |
| `VINTED_RADAR_PLATFORM_ARCHIVES_PREFIX` | `<root>/archives` | Archive prefix for lifecycle-pruned PostgreSQL transient rows. |
| `VINTED_RADAR_PLATFORM_POSTGRES_SCHEMA_VERSION` | `3` | Expected PostgreSQL migration baseline. |
| `VINTED_RADAR_PLATFORM_CLICKHOUSE_SCHEMA_VERSION` | `2` | Expected ClickHouse migration baseline. |
| `VINTED_RADAR_PLATFORM_EVENT_SCHEMA_VERSION` | `1` | Event-envelope schema version. |
| `VINTED_RADAR_PLATFORM_MANIFEST_SCHEMA_VERSION` | `1` | Manifest schema version. |
| `VINTED_RADAR_PLATFORM_BOOTSTRAP_AUDIT_RETENTION_DAYS` | `30` | How long to keep PostgreSQL bootstrap-audit rows before archiving + pruning. |
| `VINTED_RADAR_PLATFORM_OUTBOX_DELIVERED_RETENTION_DAYS` | `14` | How long to keep delivered PostgreSQL outbox rows before archiving + pruning. |
| `VINTED_RADAR_PLATFORM_OUTBOX_FAILED_RETENTION_DAYS` | `30` | How long to keep failed PostgreSQL outbox rows before archiving + pruning. |
| `VINTED_RADAR_PLATFORM_RUNTIME_CYCLES_RETENTION_DAYS` | `90` | How long to keep completed PostgreSQL runtime-cycle history before archiving + pruning. |
| `VINTED_RADAR_PLATFORM_RAW_EVENTS_RETENTION_CLASS` | `transient-evidence` | Logical retention class reported for raw event objects. |
| `VINTED_RADAR_PLATFORM_RAW_EVENTS_RETENTION_DAYS` | `730` | Object-store expiry window for the raw-events prefix. |
| `VINTED_RADAR_PLATFORM_MANIFESTS_RETENTION_CLASS` | `audit-manifest` | Logical retention class reported for manifest objects. |
| `VINTED_RADAR_PLATFORM_MANIFESTS_RETENTION_DAYS` | `3650` | Object-store expiry window for the manifests prefix. |
| `VINTED_RADAR_PLATFORM_PARQUET_RETENTION_CLASS` | `warehouse` | Logical retention class reported for Parquet warehouse objects. |
| `VINTED_RADAR_PLATFORM_PARQUET_RETENTION_DAYS` | `3650` | Object-store expiry window for the Parquet prefix. |
| `VINTED_RADAR_PLATFORM_ARCHIVES_RETENTION_CLASS` | `archive` | Logical retention class reported for lifecycle archive objects. |
| `VINTED_RADAR_PLATFORM_ARCHIVES_RETENTION_DAYS` | `3650` | Object-store expiry window for the archive prefix. |
| `VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES` | `false` | Future cutover flag for PostgreSQL writes. |
| `VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES` | `false` | Future cutover flag for ClickHouse writes. |
| `VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES` | `false` | Future cutover flag for object-storage writes. |
| `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS` | `false` | Future cutover flag for platform-backed reads. |

Notes:

- Storage prefixes are normalized to forward-slash form and reject `.` / `..` segments.
- `PlatformConfig.as_redacted_dict()` produces a safe observability snapshot that keeps endpoints, versions, and flags visible while masking credentials.
- Targeted verification for this layer: `python -m pytest tests/test_platform_config.py -q`

### Local stack bootstrap + doctor

Bring up the local services first:

```bash
docker compose -f infra/docker-compose.data-platform.yml up -d
```

Then bootstrap schema state, create the object-store bucket if needed, ensure prefix marker objects exist, and verify write access across PostgreSQL, ClickHouse, and MinIO:

```bash
python -m vinted_radar.cli platform-bootstrap
```

Use the read-mostly doctor afterwards whenever you want a redacted health snapshot without reapplying migrations:

```bash
python -m vinted_radar.cli platform-doctor
```

When you want the bounded-storage jobs to actually enforce ClickHouse TTL, prune/archive transient PostgreSQL rows, and publish the current storage posture explicitly, run:

```bash
python -m vinted_radar.cli platform-lifecycle
```

What `platform-bootstrap` wires up:

- PostgreSQL migrations from `infra/postgres/migrations/`, including the event envelope, evidence manifest, and outbox tables
- ClickHouse migrations from `infra/clickhouse/migrations/`
- S3-compatible bucket/prefix bootstrap for `events/raw`, `manifests`, and `parquet`
- write/delete probes under each configured object-store prefix so failures surface before ingestion work starts

Local service defaults exposed by `infra/docker-compose.data-platform.yml`:

- PostgreSQL: `127.0.0.1:5432`
- ClickHouse HTTP: `127.0.0.1:8123`
- MinIO API: `127.0.0.1:9000`
- MinIO console: `http://127.0.0.1:9001`

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

## Live cutover smoke proof

Use this sequence when you want a real acceptance check of the cut-over stack instead of only unit tests.

1. Bootstrap the platform services and verify their health:

```bash
python -m vinted_radar.cli platform-bootstrap
python -m vinted_radar.cli platform-doctor
```

2. Before switching reads, reconcile or backfill the historical corpus so PostgreSQL mutable truth, ClickHouse facts, and object-storage evidence are not empty, then inspect the platform-audit posture that the final proof will rely on:

```bash
python -m vinted_radar.cli platform-reconcile --db data/vinted-radar.db
python -m vinted_radar.cli platform-audit --db data/vinted-radar.db --format json
```

3. Enable the four live cutover flags in the operator environment:

```bash
export VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES=true
export VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES=true
export VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES=true
export VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=true
```

4. Run one narrow but real collector cycle:

```bash
python -m vinted_radar.cli batch \
  --db data/vinted-radar.db \
  --page-limit 1 \
  --max-leaf-categories 1 \
  --state-refresh-limit 2
```

5. Prove the end-to-end cutover surfaces, including PostgreSQL mutable truth, ClickHouse ingest, object-storage evidence, and the served product routes:

```bash
python scripts/verify_cutover_stack.py \
  --db-path data/vinted-radar.db \
  --listing-id <id> \
  --json
```

What `verify_cutover_stack.py` proves:

- cutover mode is really `polyglot-cutover`
- `platform-doctor` is healthy across PostgreSQL, ClickHouse, and object storage
- the ClickHouse ingest consumer can drain pending outbox work without ending in `failed`
- `platform-audit` reports reconciliation `match`, healthy/active current-state + analytical checkpoints, non-failing lifecycle posture, and a closed historical backfill posture (`healthy` or `complete`)
- PostgreSQL mutable truth exposes a latest discovery run, listing current state, runtime controller state, and runtime cycle
- ClickHouse feature marts expose listing-day rows, populated change facts, at least one fresh change fact for the latest discovery run, and evidence-pack drill-down commands (`evidence-inspect`) tied to real manifest/event trace IDs
- the local ClickHouse-backed `/api/dashboard`, `/api/explorer`, `/api/listings/<id>`, and `/health` payloads still match the SQLite-era contract after normalization, so the remaining SQLite read hot path is no longer required for product parity
- object storage contains non-marker raw-event, manifest, and parquet objects
- `/`, `/explorer`, `/runtime`, `/api/runtime`, `/listings/<id>`, `/api/listings/<id>`, and `/health` all work on the cut-over stack
- `/api/dashboard` is really serving `clickhouse.overview_snapshot`

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
- HTML listing detail route: `http://127.0.0.1:8765/listings/<id>`

### Focused diagnostics

- `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6`

`discover`, `batch`, and `continuous` all default to bounded API discovery with `--min-price 30` and `--max-price 0`. Pass `--min-price 0` only for an explicit unbounded override.

- `python -m vinted_radar.cli db-health --db data/vinted-radar.db --integrity`
- `python -m vinted_radar.cli coverage --db data/vinted-radar.db`
- `python -m vinted_radar.cli freshness --db data/vinted-radar.db`
- `python -m vinted_radar.cli revisit-plan --db data/vinted-radar.db --limit 10`
- `python -m vinted_radar.cli history --db data/vinted-radar.db --listing-id <id>`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar.db --limit 10 --format json`
- `python -m vinted_radar.cli state-summary --db data/vinted-radar.db`
- `python -m vinted_radar.cli state --db data/vinted-radar.db --listing-id <id>`
- `python -m vinted_radar.cli rankings --db data/vinted-radar.db --kind demand --limit 10`
- `python -m vinted_radar.cli rankings --db data/vinted-radar.db --kind premium --limit 10`
- `python -m vinted_radar.cli market-summary --db data/vinted-radar.db --limit 8`
- `python -m vinted_radar.cli score --db data/vinted-radar.db --listing-id <id>`
- `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 8 --format json`

## Proxy pool contract

The acquisition commands now understand both proxy URL form and raw Webshare exports:

- URL form: `http://user:pass@host:port`
- Webshare form: `host:port:user:pass`

Supported operator inputs:

- repeatable `--proxy` on `discover`, `batch`, `continuous`, `state-refresh`, and `proxy-preflight`
- `--proxy-file <path>` on those same commands
- implicit local autoload from `data/proxies.txt` when that file exists and no explicit proxy source is passed

Recommended local setup for the provided Webshare pool:

1. Store the pool in `data/proxies.txt` (the `data/` directory is gitignored).
2. Run a preflight before longer collection work:

```bash
python -m vinted_radar.cli proxy-preflight \
  --proxy-file data/proxies.txt \
  --sample-size 8 \
  --format json
```

3. Then run the real operator command, for example:

```bash
python -m vinted_radar.cli batch \
  --db data/vinted-radar.db \
  --page-limit 1 \
  --max-leaf-categories 6 \
  --state-refresh-limit 10 \
  --proxy-file data/proxies.txt
```

When a proxy pool is active and `--concurrency` is omitted, discovery auto-scales from the old direct-mode default of `1` up to `min(proxy_pool_size, 24)` so the pool actually contributes throughput. Explicit `--concurrency` still wins.

Runtime-facing config now keeps only safe transport metadata (`transport_mode`, `proxy_pool_size`) and never persists proxy credentials.

## Overview + diagnostics routes

- French overview home: `http://127.0.0.1:8765/`
- Dedicated runtime page: `http://127.0.0.1:8765/runtime`
- SQL-backed explorer: `http://127.0.0.1:8765/explorer`
- HTML listing detail route: `http://127.0.0.1:8765/listings/<id>`
- JSON overview payload (compat dashboard endpoint): `http://127.0.0.1:8765/api/dashboard`
- JSON explorer payload: `http://127.0.0.1:8765/api/explorer`
- JSON runtime payload: `http://127.0.0.1:8765/api/runtime`
- JSON listing detail payload: `http://127.0.0.1:8765/api/listings/<id>`
- Health check: `http://127.0.0.1:8765/health`

## Explorer workflow

The explorer is now the main browse-and-compare workspace over the tracked corpus.

Supported query parameters:

- `root`
- `catalog_id`
- `brand`
- `condition`
- `state`
- `price_band`
- `q`
- `sort`
- `page`
- `page_size`

Comparison modules on `/explorer` are scoped to the currently filtered slice and keep low-support rows visible with explicit caution badges instead of hiding them.

Opening a listing from `/explorer` preserves the current explorer query state on `/listings/<id>` and `/api/listings/<id>`, so the detail route can offer a direct return to the same analytical view.

Example explorer URLs:

- active high-price women slice: `http://127.0.0.1:8765/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=24`
- drill into one category/brand slice from the current explorer state: `http://127.0.0.1:8765/explorer?root=Femmes&brand=Maje&q=robe&sort=view_desc&page_size=24`

## Listing detail workflow

The HTML detail route is now narrative-first instead of proof-first.

What the route does:

- keeps the explorer query string on `/listings/<id>` and `/api/listings/<id>`
- exposes `Retour aux résultats` so the user can go back to the same filtered explorer slice
- starts with a plain-language reading (`Ce que le radar voit d’abord`) before showing proof
- keeps prudence/provenance visible (`Repères et limites visibles`) so observed facts, inferred state, estimated publication timing, and radar timestamps do not get blurred together
- moves technical proof into disclosures (`Preuve d’état`, `Contexte de score`, `Chronologie radar`) instead of forcing that reasoning above the fold

The JSON detail payload remains the authoritative machine-readable contract. It now includes `narrative` and `provenance` sections on top of the existing `state_explanation`, `score_explanation`, `history`, and `transitions` proof blocks.

Example detail URL from an explorer slice:

- `http://127.0.0.1:8765/listings/<id>?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=24`

## Proxy / VPS serving contract

Use `--base-path` when the product sits behind a reverse-proxy path prefix, and use `--public-base-url` when CLI output and operator docs should advertise the external URL rather than the bind address.

Example: local process bound on localhost, product exposed remotely at `/radar`:

```bash
python -m vinted_radar.cli dashboard \
  --db data/vinted-radar.db \
  --host 127.0.0.1 \
  --port 8782 \
  --base-path /radar \
  --public-base-url https://radar.example.com/radar
```

> On Git Bash / MSYS shells, leading `/radar` arguments can be rewritten into fake Windows filesystem paths before Python sees them. Use `MSYS_NO_PATHCONV=1` for mounted-route commands:
>
> ```bash
> MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard \
>   --db data/vinted-radar.db \
>   --host 127.0.0.1 \
>   --port 8782 \
>   --base-path /radar \
>   --public-base-url http://127.0.0.1:8782/radar
> ```

The same contract applies to `batch --dashboard` and `continuous --dashboard`.

Once the server is up, verify the real product routes through the same base URL the operator will share:

```bash
python scripts/verify_vps_serving.py \
  --base-url https://radar.example.com/radar \
  --listing-id <id> \
  --expected-cutover-mode polyglot-cutover \
  --timeout 30
```

What this contract guarantees:

- generated links point to the mounted product shell instead of assuming `/`
- `/`, `/explorer`, `/runtime`, `/listings/<id>`, and `/health` stay reachable through the advertised base URL
- JSON diagnostics remain available at `/api/dashboard`, `/api/explorer`, `/api/runtime`, and `/api/listings/<id>` behind the same prefix
- `/api/runtime` and `/health` can both prove the expected cutover mode during production smoke checks

If you install the dashboard as a systemd service on the VPS, pass the same values through `install_services.sh` so the service and the CLI advertise the same mounted product shell:

```bash
sudo DASHBOARD_HOST=127.0.0.1 \
  DASHBOARD_PORT=8782 \
  DASHBOARD_BASE_PATH=/radar \
  DASHBOARD_PUBLIC_BASE_URL=https://radar.example.com/radar \
  bash install_services.sh
```

Then run the same smoke check against the public URL prefix before treating the deployment as usable.

### Production cutover + rollback runbook

`install_services.sh` does **not** inject the platform DSNs, object-store credentials, or the four cutover flags by itself. On the VPS, keep those values in a shared systemd drop-in (or an equivalent environment file) that is loaded by the collector and dashboard services.

Recommended cutover sequence:

1. Confirm the current SQLite-backed service is healthy and take a fresh remote SQLite snapshot.
2. Bootstrap the platform services and run `platform-doctor` until PostgreSQL, ClickHouse, and object storage are all healthy.
3. Run the historical backfill / reconciliation steps while reads still remain on SQLite.
4. Install or update the shared service environment with platform credentials plus:
   - `VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES=true`
   - `VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES=true`
   - `VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES=true`
   - `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=false`
5. Restart the collector first and run one narrow shadow cycle.
6. Run `python scripts/verify_cutover_stack.py --base-url https://radar.example.com/radar --listing-id <id> --json` from the same environment contract or from an operator shell with the same platform variables loaded.
7. Only after the shadow proof looks healthy, flip `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=true` and restart the dashboard / public-serving process.
8. Re-run both:
   - `python scripts/verify_cutover_stack.py --base-url https://radar.example.com/radar --listing-id <id> --json`
   - `python scripts/verify_vps_serving.py --base-url https://radar.example.com/radar --listing-id <id> --expected-cutover-mode polyglot-cutover`

Rollback sequence:

1. Set `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=false`.
2. If the platform itself is unhealthy, also set the three platform-write flags back to `false` so the collector returns to `sqlite-primary`.
3. Restart the dashboard first so public reads fall back to SQLite immediately.
4. Restart the collector/runtime service.
5. Re-run `python scripts/verify_vps_serving.py --base-url https://radar.example.com/radar --listing-id <id>` to confirm the public shell is still healthy on the fallback path.
6. Keep the failing PostgreSQL / ClickHouse / object-store evidence for diagnosis; do not overwrite the last healthy SQLite snapshot while investigating.

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

### Consolidated long-run audit

For copied VPS snapshots or any long unattended run, use the consolidated DB-first audit command instead of stitching together `db-health`, `runtime-status`, `coverage`, `freshness`, and `revisit-plan` manually:

```bash
python -m vinted_radar.cli audit-long-run \
  --db data/vinted-radar.db \
  --hours 12 \
  --integrity
```

Useful variants:

- JSON for automation: `python -m vinted_radar.cli audit-long-run --db data/vinted-radar.db --hours 12 --format json`
- Markdown report: `python -m vinted_radar.cli audit-long-run --db data/vinted-radar.db --hours 12 --format markdown`
- deterministic replay against a copied snapshot: `python -m vinted_radar.cli audit-long-run --db data/vinted-radar.db --hours 12 --now 2026-03-24T10:00:00+00:00`

What the audit consolidates:

- DB health and whether the snapshot is safe to trust
- runtime stability across the requested window (`completed` / `failed` / `interrupted`, average cycle duration, failure phases)
- discovery breadth vs repeated-subset risk (including the common `--max-leaf-categories` false-confidence trap)
- acquisition quality across the window (`healthy` / `partial` / `degraded`, anti-bot hits, degraded probes, recent scan failures)
- current freshness mix and top revisit candidates
- an overall verdict plus concrete recommendations for the next VPS run

Keep `scripts/verify_vps_serving.py` as the complementary HTTP/public-entrypoint proof. `audit-long-run` is intentionally DB-first and does not replace the public serving smoke check.

## Degraded acquisition visibility

The product now distinguishes three acquisition-health states across overview, explorer, listing detail, runtime, `/api/runtime`, and `/health`:

- `healthy` — the latest discovery run has no visible scan failures and the latest persisted state-refresh probes were direct enough to trust operationally
- `partial` — probes completed, but one or more of them stayed inconclusive, so the product leans more heavily on the radar history than on a fresh direct page signal
- `degraded` — recent catalog scans failed or the latest state-refresh probes hit anti-bot / challenge pages, transport exceptions, or other explicit degraded HTTP outcomes

Operator inspection flow:

```bash
python -m vinted_radar.cli runtime-status --db data/vinted-radar.db --format json
python -m vinted_radar.cli state-refresh --db data/vinted-radar.db --limit 10 --format json \
  --proxy http://user:pass@proxy.example:8080
```

What to look for:

- `latest_cycle.state_refresh_summary` in `runtime-status` JSON — persisted direct/inconclusive/degraded probe counts for the latest usable cycle
- `acquisition` in `/api/runtime` and `/health` — the cross-surface healthy/partial/degraded contract plus recent failed scans and example degraded probes
- the overview/explorer/detail/runtime HTML routes — French product copy that warns when the radar is reading under degraded acquisition instead of pretending the data is fully healthy

A degraded state-refresh probe does **not** automatically mean the listing is deleted or sold. It means the page-level check failed to provide a clean direct signal, so the product should fall back to the safer historical reading until a later clean probe succeeds.

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

For unattended or auto-mode VPS access on this workstation, use the project helper instead of ad hoc SSH setup. It targets `root@46.225.113.129`, uses the local key at `~/.ssh/id_ed25519`, and loads the passphrase from the gitignored `.env.vps` file:

```bash
bash scripts/vpsctl.sh config
bash scripts/vpsctl.sh exec -- 'hostname && pwd'
bash scripts/vpsctl.sh get /root/Vinted/data/vinted-radar.clean.db data/vps-copy.db
bash scripts/vpsctl.sh put scripts/run_vps_verification.sh /root/Vinted/run_vps_verification.sh
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
5/api/runtime`
765/api/runtime`
