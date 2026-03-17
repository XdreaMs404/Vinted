# Vinted Radar

Local-first batch collector and analysis stack for public Vinted Homme/Femme market signals.

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

1. public catalog discovery
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

This keeps the radar alive locally and serves the dashboard from the same DB while cycles continue in the background process.

## Current entrypoints

### Operator workflow

- `python -m vinted_radar.cli batch --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --state-refresh-limit 10`
- `python -m vinted_radar.cli continuous --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --interval-seconds 1800 --dashboard --host 127.0.0.1 --port 8765`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar.db`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar.db --host 127.0.0.1 --port 8765`

### Focused diagnostics

- `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6`
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

## Dashboard diagnostics

- HTML dashboard: `http://127.0.0.1:8765/`
- JSON dashboard payload: `http://127.0.0.1:8765/api/dashboard`
- JSON runtime payload: `http://127.0.0.1:8765/api/runtime`
- JSON listing detail payload: `http://127.0.0.1:8765/api/listings/<id>`
- Health check: `http://127.0.0.1:8765/health`

## Runtime diagnostics

Each batch or continuous cycle is persisted into `runtime_cycles` inside the SQLite DB with:

- mode (`batch` or `continuous`)
- status (`running`, `completed`, `failed`, `interrupted`)
- current phase (`starting`, `discovery`, `state_refresh`, `summarizing`, `completed`)
- linked discovery run id when available
- state probe limit and actual probed count
- tracked listing count plus freshness snapshot
- last error when a cycle fails

Use `runtime-status --format json` or `/api/runtime` to inspect the current local operator truth without reading raw tables by hand.
