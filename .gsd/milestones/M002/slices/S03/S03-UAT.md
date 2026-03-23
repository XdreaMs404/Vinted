# S03: Responsive French Product Shell + VPS Serving Path — UAT

**Milestone:** M002  
**Slice:** S03  
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S03 claims both a real mounted serving contract and a coherent phone/desktop product shell. The slice therefore needs route-level smoke proof plus browser-level consultation checks on the same mounted base URL.

## Preconditions

- Python dependencies are installed and the project runs from `C:\Users\Alexis\Documents\VintedScrap2`.
- `data/vinted-radar-s03.db` exists locally.
- Port `8782` is free.
- Start the mounted local server in one terminal:

```bash
python -m vinted_radar.cli dashboard \
  --db data/vinted-radar-s03.db \
  --host 127.0.0.1 \
  --port 8782 \
  --base-path /radar \
  --public-base-url http://127.0.0.1:8782/radar
```

- Keep a browser available for both desktop and mobile viewport checks.

## Smoke Test

Run:

```bash
python scripts/verify_vps_serving.py \
  --base-url http://127.0.0.1:8782/radar \
  --listing-id 9002
```

Expected quick signal:
- `/radar/`, `/radar/explorer`, `/radar/runtime`, `/radar/listings/9002`, `/radar/api/listings/9002`, and `/radar/health` all return 200
- the verifier prints `VPS serving verification passed`
- `/health.serving.base_path` is `/radar`

## Test Cases

### 1. Shared shell stays coherent across the four HTML routes

1. Open `http://127.0.0.1:8782/radar/`.
2. Confirm the shell shows the same product navigation used on the other routes.
3. Open `http://127.0.0.1:8782/radar/explorer`.
4. Open `http://127.0.0.1:8782/radar/runtime`.
5. Open `http://127.0.0.1:8782/radar/listings/9002`.
6. **Expected:** all four routes share the same French shell vocabulary (`Accueil`, `Explorateur`, `Runtime`, shared page chrome) while each keeps its own page-specific content.

### 2. Explorer remains consultable on phone width

1. Switch the browser to a mobile viewport.
2. Open `http://127.0.0.1:8782/radar/explorer`.
3. Read the filter block and the first listing cards.
4. **Expected:** the explorer renders stacked filter controls plus listing cards, not a horizontally scrolling primary table. The route stays readable without broken links or clipped actions.

### 3. Mounted route generation stays prefix-safe

1. From `http://127.0.0.1:8782/radar/`, use the shared navigation to move to `/radar/explorer` and `/radar/runtime`.
2. From the explorer, open a listing detail route.
3. Inspect `http://127.0.0.1:8782/radar/health`.
4. **Expected:** internal links keep the `/radar` prefix, detail opens under `/radar/listings/<id>`, and `/health` reports the same mounted serving contract.

### 4. Diagnostics remain secondary but accessible

1. On each HTML route, use the visible JSON/health links.
2. Open `/radar/api/dashboard`, `/radar/api/explorer`, `/radar/api/runtime`, and `/radar/api/listings/9002`.
3. **Expected:** diagnostics remain available from the product shell, but the HTML routes read as the primary product experience rather than JSON-first admin screens.

## Edge Cases

### Mounted prefix instead of root

1. Open `http://127.0.0.1:8782/radar/` directly.
2. **Expected:** the app serves normally under the prefix and does not require the root `/` path to render a usable product shell.

### Phone-width no-overflow check

1. On mobile width, inspect `/radar/` and `/radar/explorer`.
2. **Expected:** there is no horizontal overflow requirement for primary consultation; stacked nav/actions and card flows remain usable.

## Failure Signals

- `verify_vps_serving.py` fails on any mounted route.
- An internal shell link drops the `/radar` prefix.
- `/health` has no `serving` block or reports the wrong `base_path` / `public_base_url`.
- Explorer or runtime reverts to a desktop-first layout that requires horizontal scrolling as the main reading path.
- Different HTML routes visibly diverge in navigation, palette, or shell structure.
- Browser load on mounted routes produces console errors or failed requests during normal rendering.

## Requirements Proved By This UAT

- R009 — proves the product now exposes a clearer information architecture across overview, explorer, runtime, and listing detail instead of a single mixed proof screen.
- R010 — proves the runtime surface remains part of the real mounted product, not only a local CLI concern.
- R012 — proves the product utility surface is broader than the old overview-only posture, with one coherent shell across exploration, detail, and runtime.

## Not Proven By This UAT

- Deeper explorer comparison/filter richness — that belongs to S04.
- Narrative-first listing explanation and progressive disclosure polish — that belongs to S05.
- Degraded acquisition messaging and hardening — that belongs to S06.
- Final live VPS/domain acceptance against production data volume — that belongs to S07.

## Notes for Tester

- If you run this from Git Bash on Windows, `--base-path /radar` may be rewritten by MSYS path conversion before Python receives it. Using `--base-path radar`, quoting the value, or disabling path conversion avoids that local-only tooling quirk.
- The shell is French-first, but listing titles still reflect source-market content and may remain English or mixed-language when the underlying listing is.
