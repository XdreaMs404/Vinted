# S06: Acquisition Hardening + Degraded-Mode Visibility — UAT

**Milestone:** M002  
**Slice:** S06  
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S06 changes both backend truth and product honesty. The slice therefore needs automated payload/route coverage plus served-browser checks on overview, explorer, detail, runtime, `/api/runtime`, and `/health` against a seeded degraded dataset.

## Preconditions

- Python dependencies are installed and the project runs from `C:/Users/Alexis/Documents/VintedScrap2`.
- Regenerate the seeded S06 demo DB:

```bash
python - <<'PY'
from pathlib import Path
from tests.test_dashboard import _seed_dashboard_db
path = Path('data/vinted-radar-s06.db')
if path.exists():
    path.unlink()
_seed_dashboard_db(path)
print(path)
PY
```

- Start the local server:

```bash
python -m vinted_radar.cli dashboard \
  --db data/vinted-radar-s06.db \
  --host 127.0.0.1 \
  --port 8786
```

- Keep a browser available on desktop width.

## Smoke Test

Run:

```bash
python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_runtime_cli.py
```

Expected quick signal:
- degraded acquisition assertions pass on overview/explorer/detail/runtime/health payloads
- route/UI tests still pass after the new honesty copy and runtime acquisition panel
- CLI coverage still passes for runtime JSON/table output and proxy-aware `state-refresh`

## Test Cases

### 1. Overview home shows degraded acquisition without hiding the market read

1. Open `http://127.0.0.1:8786/`.
2. Confirm the hero pills show `acquisition dégradée` alongside the runtime state.
3. Confirm `Niveau d’honnêteté du signal` still appears on the same page.
4. **Expected:** the home surface keeps the market view readable while explicitly surfacing degraded acquisition instead of implying everything is healthy.

### 2. Explorer keeps corpus browsing usable under degraded acquisition

1. Open `http://127.0.0.1:8786/explorer?root=Femmes&q=robe&page_size=2&sort=view_desc`.
2. Confirm the explorer hero shows `acquisition dégradée`.
3. Scroll until the acquisition warning note under `Filtres d’exploration` is visible.
4. **Expected:** the explorer still serves filters/comparisons/results, but warns in French that one recent state-refresh probe hit anti-bot/challenge conditions.

### 3. Listing detail explains when the latest probe was degraded

1. Open `http://127.0.0.1:8786/listings/9002?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`.
2. Confirm `Repères et limites visibles` contains `Dernière probe dégradée`.
3. Confirm the provenance section exposes `SOURCE HISTORIQUE RADAR APRÈS PROBE DÉGRADÉE`.
4. **Expected:** the detail page does not silently treat the last page probe as neutral; it tells the user that the state read now leans more heavily on radar history because the latest direct probe hit anti-bot friction.

### 4. Runtime page separates scheduler truth from acquisition health

1. Open `http://127.0.0.1:8786/runtime`.
2. Confirm the hero shows both `planifié` and `acquisition dégradée`.
3. Confirm the page contains `Santé d’acquisition`, `Pourquoi ce statut`, and `Challenges anti-bot`.
4. **Expected:** the runtime page shows that the controller is healthy/scheduled while acquisition is degraded, instead of collapsing both concerns into one status.

### 5. Machine-readable routes expose the same degraded truth

1. Open `http://127.0.0.1:8786/api/runtime`.
2. Confirm the JSON contains `"status": "degraded"` under `acquisition` and `"anti_bot_challenge_count": 1`.
3. Open `http://127.0.0.1:8786/health`.
4. Confirm the JSON contains `"current_runtime_status": "scheduled"` and the same degraded acquisition block.
5. **Expected:** `/api/runtime` and `/health` agree with the HTML surfaces on both scheduler truth and acquisition degradation.

## Edge Cases

### Partial but not broken probe path

1. Use a dataset where the latest state-refresh probes are inconclusive but not failed/challenged.
2. Inspect `/api/runtime` and the explorer warning layer.
3. **Expected:** acquisition drops to `partial`, not `degraded`, and the UI explains that history is still the safer signal.

### No recent discovery scan failures

1. Keep the seeded S06 demo DB as-is.
2. Inspect the runtime acquisition panel and `/api/runtime`.
3. **Expected:** `recent_scan_failure_count` stays `0`, proving that S06 distinguishes degraded item-page probing from discovery scan failure instead of merging them into one opaque error bucket.

## Failure Signals

- Overview/explorer/runtime HTML keeps showing only scheduler state with no acquisition-health signal.
- Explorer browsing breaks or hides results just because acquisition is degraded.
- Detail route lacks `Dernière probe dégradée` even when the latest probe was challenged.
- `/api/runtime` or `/health` omits the `acquisition` block or disagrees with the HTML pages.
- Runtime page implies the controller itself is failed when only acquisition is degraded.
- Browser interactions show console errors or failed app requests on the served HTML routes.

## Requirements Proved By This UAT

- R011 — proves the product keeps degraded or partial acquisition visible in both operator and user-facing language instead of smoothing it away.
- R004 — advances the visibility requirement by making degraded acquisition part of the visible evidence boundary on HTML and JSON surfaces.
- R010 — confirms runtime truth and acquisition truth stay separately inspectable on the same local product entrypoint.

## Not Proven By This UAT

- Live VPS acceptance from phone and desktop on the assembled product — that still belongs to S07.
- Long-lived real-world anti-bot behavior under live repeated collection — S06 proves the honesty surfaces and the hardened seams locally, not calendar-time production durability.

## Notes for Tester

- `/api/runtime` and `/health` may show raw English reason strings inside machine-facing JSON while the visible HTML copy stays French-first; that split is intentional.
- The seeded S06 DB models a degraded item-page probe without any failed catalog scan, so the runtime page should show `acquisition dégradée` while `Scans cassés récents` remains `0`.
