# S05: Listing Detail Narrative + Progressive Proof — UAT

**Milestone:** M002  
**Slice:** S05  
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S05 claims a richer HTML detail workflow, not just a payload refactor. The slice therefore needs route-level proof, browser-level reading checks from the explorer context, and one mobile consultability check on the same detail route.

## Preconditions

- Python dependencies are installed and the project runs from `C:\Users\Alexis\Documents\VintedScrap2`.
- `data/vinted-radar-s04.db` exists locally.
- Port `8784` is free.
- Start the local server:

```bash
python -m vinted_radar.cli dashboard \
  --db data/vinted-radar-s04.db \
  --host 127.0.0.1 \
  --port 8784
```

- Keep a browser available for both desktop and mobile viewport checks.

## Smoke Test

Run:

```bash
python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py
```

Expected quick signal:
- detail-route payload and HTML tests pass
- no stale assertions still expect the old proof-first wording
- the local dashboard command still advertises the same route set cleanly

## Test Cases

### 1. Explorer drill-down opens a narrative-first detail page

1. Open `http://127.0.0.1:8784/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`.
2. Open any listing with `Ouvrir la fiche`.
3. Confirm the detail page opens under `/listings/<id>` with the explorer query state still present in the URL.
4. **Expected:** the detail route leads with `Ce que le radar voit d’abord`, a plain-language reading headline, and preserved explorer context rather than opening directly on proof jargon.

### 2. Prudence and provenance stay visible before the proof

1. On the opened detail page, inspect the `Repères et limites visibles` section.
2. Confirm the route distinguishes the three provenance surfaces: `État radar`, `Publication visible`, and `Fenêtre radar`.
3. **Expected:** the page makes it clear what is observed, what is inferred, what is estimated, and what belongs to local radar timestamps before the technical proof is expanded.

### 3. Technical proof stays accessible through disclosure panels

1. On the same detail page, inspect the `Preuves techniques et détails` section.
2. Open `Preuve d’état`.
3. Optionally open `Contexte de score` and `Chronologie radar`.
4. **Expected:** the proof panels expand cleanly, the visible copy is French-facing, and the route still exposes the underlying reasoning instead of hiding it behind vague product copy.

### 4. Return-to-results preserves the analytical lens

1. From the detail page, click `Retour aux résultats`.
2. **Expected:** the browser returns to the same `/explorer` URL, preserving root/state/price-band/sort/page-size context instead of dropping back to a generic explorer page.

## Edge Cases

### Mobile detail stays consultable

1. Switch the browser to a mobile viewport.
2. Re-open the same detail route.
3. Read the narrative cards and the proof-section headers.
4. **Expected:** the route remains vertically readable without horizontal overflow; the narrative/provenance stack still makes sense on phone width.

### Partial public fields remain explicit

1. Inspect a detail page where seller, likes, or views are missing.
2. **Expected:** the route shows an explicit prudence card (`Champs publics incomplets`) instead of silently pretending those fields were never part of the reading.

## Failure Signals

- `/listings/<id>` still leads with raw state/score jargon instead of a plain-language reading.
- Explorer context disappears from the detail URL or the visible `Contexte explorateur` block.
- Provenance collapses observed, inferred, estimated, and radar-timestamp signals into one generic summary.
- `Preuve d’état` expands but shows stale English-first reasoning or raw factor names that leak implementation vocabulary.
- `Retour aux résultats` drops back to an unfiltered explorer route.
- Mobile viewport introduces horizontal overflow or clipped cards/actions.
- Browser load produces console errors or failed requests during the normal explorer → detail flow.

## Requirements Proved By This UAT

- R009 — proves the product detail route now fits the clearer overview/explorer/detail information architecture instead of behaving like a secondary debugger page.
- R012 — proves the product utility surface deepens beyond browsing alone by giving each listing a readable market interpretation plus accessible proof.
- R004 — advances the visibility requirement by keeping provenance boundaries and confidence-related prudence visible in broader-audience language on the detail route.

## Not Proven By This UAT

- Degraded acquisition messaging across overview/explorer/detail/runtime — that still belongs to S06.
- Final mounted VPS acceptance against the fully assembled product — that still belongs to S07.

## Notes for Tester

- The route is French-first, but listing titles, brands, and source-market text still reflect public source data.
- The strongest S05 proof path is the filtered explorer URL above because it exercises context preservation, narrative reading, proof disclosure, and return-to-results in one loop.
