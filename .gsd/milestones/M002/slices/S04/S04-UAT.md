# S04: Full Explorer + Comparative Intelligence — UAT

**Milestone:** M002  
**Slice:** S04  
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S04 claims a real SQL-backed explorer workflow, not just payload changes. The slice therefore needs repository/route proof plus browser-level validation on a richer local database where filters, comparison support counts, and detail round-trips are visible.

## Preconditions

- Python dependencies are installed and the project runs from `C:\Users\Alexis\Documents\VintedScrap2`.
- `data/vinted-radar-s04.db` exists locally.
- Port `8783` is free.
- Start the local server:

```bash
python -m vinted_radar.cli dashboard \
  --db data/vinted-radar-s04.db \
  --host 127.0.0.1 \
  --port 8783
```

- Keep a browser available for the explorer and detail-flow checks.

## Smoke Test

Run:

```bash
python -m pytest tests/test_explorer_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_repository.py
```

Expected quick signal:
- explorer repository and dashboard route tests pass
- no SQL explorer contract or route-regression failures appear
- the proof DB opens successfully even if it comes from an older snapshot lineage

## Test Cases

### 1. Explorer renders as the main browse-and-compare workspace

1. Open `http://127.0.0.1:8783/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`.
2. Confirm the hero, filter block, comparison modules, and result section all render.
3. **Expected:** the route shows active-filter context, result counts, support-aware comparison modules, and listing cards without server errors.

### 2. Filter state remains explicit and honest

1. On the same explorer URL, read the active-filter summary and the comparison panels.
2. Inspect at least one module with strong support and one with thin support.
3. **Expected:** support counts stay visible, low-support rows are still shown with caution wording, and the page does not silently hide thin slices.

### 3. Explorer-to-detail navigation preserves the analytical lens

1. From the filtered explorer URL, open any listing using `Ouvrir la fiche`.
2. Confirm the listing detail URL still includes the explorer query parameters.
3. Confirm the detail page exposes a `Retour aux résultats` link and a `Contexte explorateur` block.
4. **Expected:** the detail page explains which filtered explorer slice led to the listing and offers a truthful way back.

### 4. Return-to-results lands on the same explorer state

1. From the contextualized listing detail page, click `Retour aux résultats`.
2. **Expected:** the browser returns to the same explorer URL, preserving root/state/price-band/sort/page-size context instead of dropping back to an unfiltered explorer.

## Edge Cases

### Legacy proof DB still opens

1. Start the server against `data/vinted-radar-s04.db`.
2. Open `/explorer` and `/listings/<id>`.
3. **Expected:** the server does not fail with `sqlite3.OperationalError: no such column: created_at_ts`; older snapshots migrate before dependent indexes are created.

### Thin support remains visible

1. On a filtered explorer slice with few listings, inspect the comparison modules.
2. **Expected:** the route keeps thin-support rows visible with explicit caution instead of pretending the slice is stronger than it is or hiding the module outright.

## Failure Signals

- `/explorer` returns 500 on a historical snapshot DB.
- Explorer filters render but results/comparison modules disappear or drift from the active-filter summary.
- Comparison rows omit support counts or hide low-support slices without explanation.
- Listing detail opens without the explorer query state.
- `Retour aux résultats` drops back to a generic explorer route.
- Browser load produces console errors or failed requests during the normal explorer/detail flow.

## Requirements Proved By This UAT

- R012 — proves the product now offers richer user-facing utility via a full browse-and-compare explorer workflow, not just the overview market read.
- R011 — advances the honesty requirement by keeping support levels and thin-sample caveats visible inside the explorer workflow rather than burying them in diagnostics alone.

## Not Proven By This UAT

- Narrative-first listing storytelling and deeper progressive disclosure polish — that belongs to S05.
- Degraded acquisition messaging and challenge-aware UX — that belongs to S06.
- Final mounted VPS acceptance against the S04 explorer workflow — that belongs to S07.

## Notes for Tester

- The explorer is French-first, but listing titles and brand labels still reflect source-market content.
- The richest S04 proof path is the explicit filtered URL above because it exercises comparison modules and detail context preservation in one flow.
