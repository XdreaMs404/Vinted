# S07: Live VPS End-to-End Acceptance Closure — UAT

**Milestone:** M002  
**Slice:** S07  
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S07 is a final-assembly slice. It needs automated mounted-route smoke, realistic large-corpus server proof, and browser proof on desktop + mobile. It still needs one last public-VPS rerun before the roadmap can honestly mark the slice complete.

## Preconditions

- Python dependencies are installed and the project runs from `C:/Users/Alexis/Documents/VintedScrap2`.
- The realistic large proof DB exists and is healthy:

```bash
python -m vinted_radar.cli db-health --db data/m001-closeout.db --integrity
```

- Start the mounted local server from Git Bash / MSYS with path conversion disabled:

```bash
MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard \
  --db data/m001-closeout.db \
  --host 127.0.0.1 \
  --port 8790 \
  --base-path /radar \
  --public-base-url http://127.0.0.1:8790/radar
```

- Use listing id `64882428` for the realistic local proof unless a more representative listing is preferred.

## Smoke Test

Run:

```bash
python -m pytest -q
MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py \
  --base-url http://127.0.0.1:8790/radar \
  --listing-id 64882428
```

Expected quick signal:
- the full test suite passes
- mounted smoke passes for overview, explorer, runtime, detail HTML, detail JSON, and health on the realistic large DB

## Test Cases

### 1. Desktop overview reads as a broad market home on the realistic corpus

1. Open `http://127.0.0.1:8790/radar/` in desktop width.
2. Confirm the hero shows `Ce qui bouge maintenant sur le radar Vinted.`.
3. Confirm the hero pills show `au repos` and `acquisition dégradée`.
4. Confirm the KPI card shows `49759` tracked listings.
5. **Expected:** the mounted overview stays readable and honest on the realistic corpus instead of collapsing into timeouts or blank modules.

### 2. Desktop explorer keeps the large filtered slice usable

1. Open `http://127.0.0.1:8790/radar/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`.
2. Confirm the hero shows `635 annonces` and `acquisition dégradée`.
3. Confirm `Filtres d’exploration` and the filter bar render correctly.
4. **Expected:** the explorer still pages and filters a large realistic slice on the mounted shell without route drift or browser errors.

### 3. Desktop detail keeps the narrative/proof loop intact

1. Open `http://127.0.0.1:8790/radar/listings/64882428?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`.
2. Confirm the title shows `Poncho d'été`.
3. Confirm the context pill shows `Vue active — Racine : Femmes ...`.
4. Confirm the narrative section shows `Lecture radar : encore visible`.
5. **Expected:** detail keeps explorer context, narrative-first reading, and visible proof boundaries on the realistic corpus.

### 4. Desktop runtime keeps scheduler truth and acquisition truth readable

1. Open `http://127.0.0.1:8790/radar/runtime`.
2. Confirm the hero shows `Le contrôleur vivant du radar`.
3. Confirm the page shows `au repos`, `acquisition dégradée`, and `Santé d’acquisition`.
4. **Expected:** runtime remains intelligible on the mounted product shell and keeps degraded acquisition separate from controller truth.

### 5. Mobile overview keeps the shell readable without collapsing the hierarchy

1. Switch to a mobile viewport.
2. Open `http://127.0.0.1:8790/radar/`.
3. Confirm the hero, pills, and stacked navigation buttons remain readable.
4. **Expected:** phone consultation of the overview is viable on the mounted shell.

### 6. Mobile runtime keeps status comprehension intact

1. Stay on mobile viewport.
2. Open `http://127.0.0.1:8790/radar/runtime`.
3. Confirm the hero, status pills, and navigation buttons stay readable without horizontal breakage.
4. **Expected:** a phone user can still understand current runtime + acquisition state without needing the desktop layout.

### 7. Public VPS entrypoint stays reachable and truthful after live DB recovery

1. Run:

```bash
python scripts/verify_vps_serving.py \
  --base-url http://46.225.113.129:8765 \
  --listing-id 8468335111
```

2. Confirm the smoke passes for overview, explorer, runtime, detail HTML, detail JSON, and health.
3. Confirm `http://46.225.113.129:8765/health` returns `status: ok` and a live runtime/acquisition contract.
4. **Expected:** the real operator URL responds to internet-facing traffic after the corrupted 61 GB live DB is archived and services are repointed to the fresh healthy `data/vinted-radar.clean.db`.

## Edge Cases

### Git Bash / MSYS mounted command path rewriting

1. Run the mounted dashboard command without `MSYS_NO_PATHCONV=1` from Git Bash / MSYS.
2. **Expected:** the shell may rewrite `/radar` into a bogus Windows filesystem path before Python sees it. Use `MSYS_NO_PATHCONV=1` for mounted-route commands.

### Realistic-corpus route timing variance

1. Run the mounted smoke verifier against `data/m001-closeout.db` on a cold server.
2. **Expected:** the smoke can take noticeably longer than the seeded slice DBs, which is why `verify_vps_serving.py` now defaults to a 30-second per-request timeout.

## Failure Signals

- Mounted smoke times out or fails on overview/explorer/runtime/detail/health.
- Browser checks show console errors or failed app requests on the mounted shell.
- Overview/explorer/detail/runtime lose their shared `/radar` route contract.
- Large-corpus mounted routes regress back to multi-dozen-second unusable latency.
- Visible HTML reintroduces obvious mojibake such as `VÃªtements` on main user-facing labels.

## Requirements Proved By This UAT

- R009 — overview, explorer, detail, and runtime still form one usable product loop on a realistic corpus.
- R010 — runtime truth remains visible on the assembled product shell.
- R011 — degraded acquisition messaging survives the realistic mounted proof across overview, explorer, detail, and runtime.
- R012 — the richer explorer/detail workflow remains usable at realistic corpus scale on desktop and still consultable on mobile.

## Not Proven By This UAT

- True public VPS / internet-facing proof from the real operator URL — still pending the actual public base URL or read-only VPS access.
- Live current acquisition from this environment against the real VPS process — the realistic DB contains real prior runtime history, but this local mounted proof is still not the same as the public remote entrypoint.

## Notes for Tester

- Browser evidence for this local mounted proof lives under `.artifacts/browser/2026-03-23T16-41-39-152Z-session/`.
- The final browser timeline for the realistic mounted proof is `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json`.
- The trace artifact is `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip`.
- Once the real public VPS URL is provided, rerun the same smoke/browser flow against that URL and only then mark S07 complete in the roadmap/project state.
