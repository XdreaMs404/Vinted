# S01: SQL-Backed Overview Home + First Comparative Modules — UAT

**Milestone:** M002  
**Slice:** S01  
**Written:** 2026-03-22

## Preconditions

- Python dependencies are installed and the project runs from `C:\Users\Alexis\Documents\VintedScrap2`.
- Port `8765` is free.
- The seeded demo database `data/vinted-radar-s01.db` exists.
  - If it is missing in a fresh checkout, recreate it from the seeded overview fixture in `tests/test_overview_repository.py` before starting.
- Start the local server in one terminal:

```bash
python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765
```

- Open `http://127.0.0.1:8765/` in a browser.

---

## Test Case 1 — Default route is now the French overview home

### Steps
1. Load `http://127.0.0.1:8765/`.
2. Read the hero copy and main actions at the top of the page.
3. Check the four top metric cards.

### Expected outcomes
- The page title is **`Vinted Radar — aperçu du marché`**.
- The hero is French-first and reads like a market overview, not the old M001 proof dashboard.
- The page visibly contains:
  - `Vue d’ensemble du marché`
  - `Ce qui bouge maintenant sur le radar Vinted.`
  - buttons/links for:
    - `Explorer les annonces`
    - `Ouvrir le JSON aperçu`
    - `Voir le runtime`
    - `Vérifier la santé`
- The top metric cards show the seeded overview facts:
  - **Annonces suivies:** `6`
  - **Signal de vente:** `2`
  - **Confiance:** high count shown as `3` with a visible high / medium / low breakdown
  - **Fraîcheur:** latest successful scan shown as `2026-03-19T10:06:00+00:00`
- The page is visually styled; it must not degrade into raw CSS/text dumped into the page.

---

## Test Case 2 — Coverage, freshness, confidence, and uncertainty stay explicit

### Steps
1. On the home page, scroll to the right-hand context panels.
2. Inspect the **`Niveau d’honnêteté du signal`** section.
3. Inspect the **`Fraîcheur et incidents récents`** section.

### Expected outcomes
- The honesty panel is present and visible.
- The page keeps weak/uncertain evidence visible instead of hiding it.
- The honesty notes include the seeded warning set:
  - low-support rule with threshold `3`
  - inferred states count `1`
  - unknown states count `1`
  - partial-signal count `1`
  - thin-signal count `1`
  - estimated-publication note with count `4`
  - recent acquisition failures count `1`
- The freshness/incidents panel explicitly shows the seeded degraded acquisition example instead of implying perfect coverage.
- The recent acquisition issue references **`Femmes > Jupes`** and the upstream failure (`502` / `upstream unavailable`).

---

## Test Case 3 — First comparison modules are visible and honest about thin support

### Steps
1. On `/`, inspect the comparison modules under **`Comparaisons à lire avec contexte`**.
2. Read the category and brand modules first.
3. Then inspect the price-band, condition, and sold-state modules.

### Expected outcomes
- The home page shows all five first comparison lenses:
  - `Catégories`
  - `Marques`
  - `Tranches de prix`
  - `États`
  - `Statut de vente`
- In the category module:
  - `Femmes > Robes` appears as the strongest row with support `3`
  - `Femmes > Vestes` appears with a fragile-support warning
  - `Femmes > Jupes` remains visible and is marked fragile, with partial/thin/unknown cues instead of disappearing
- In the brand module:
  - `Zara` is the only solid-support row
  - `Maje`, `Sandro`, and `Marque inconnue` remain visible with fragile support
- The low-support modules (`Tranches de prix`, `États`, `Statut de vente`) still render on the page and clearly communicate fragility.
- Thin-support rows are **not** hidden from the UI just because they are weak.

---

## Test Case 4 — Explorer handoff works from the overview and stays SQL-paged

### Steps
1. From `/`, click **`Explorer les annonces`**.
2. Confirm the URL changes to `/explorer`.
3. Inspect the explorer header, filters, and first page of results.
4. Leave the default sort as `Recently seen`.

### Expected outcomes
- The explorer page loads successfully and does not fall back to the old home dashboard.
- The page contains:
  - `Listing explorer separated from the dashboard summary.`
  - `Back to dashboard`
  - filter controls for root, catalog, brand, condition, search, sort, and page size
- The stats strip shows:
  - `6` matching tracked listings
  - current page `1`
  - `6` tracked listings in DB
- Under the default sort, the first rows are the seeded SQL order:
  1. `9104` — `Veste indisponible`
  2. `9101` — `Robe active`
  3. `9105` — `Veste supprimée`
- The explorer proves thin/missing data stays usable:
  - listing `9106` renders with `Unknown brand`, `Seller not exposed`, and `price n/a`
- Latest-probe evidence is visible in the table when present:
  - `9104` shows `unavailable (200)`
  - `9105` shows `deleted (404)`
  - `9103` shows `sold (200)`

---

## Test Case 5 — JSON observability surfaces match the served UI

### Steps
1. Open `http://127.0.0.1:8765/api/dashboard`.
2. Open `http://127.0.0.1:8765/api/explorer`.
3. Open `http://127.0.0.1:8765/api/runtime`.
4. Open `http://127.0.0.1:8765/health`.
5. Open `http://127.0.0.1:8765/api/listings/9101`.

### Expected outcomes
- `/api/dashboard` returns JSON, not HTML.
- `/api/dashboard` includes:
  - `summary.inventory.tracked_listings = 6`
  - `summary.inventory.sold_like_count = 2`
  - `summary.honesty.inferred_state_count = 1`
  - `summary.freshness.latest_runtime_cycle_status = "completed"`
  - `comparisons` with keys: `category`, `brand`, `price_band`, `condition`, `sold_state`
  - `honesty_notes`
  - `featured_listings`
- `/api/explorer` returns JSON with `results.total_listings = 6` and the same default listing order shown by the explorer page.
- `/api/runtime` returns JSON with a `latest_cycle` and the latest status set to `completed`.
- `/health` returns JSON with `status = "ok"` and `tracked_listings = 6`.
- `/api/listings/9101` returns JSON with:
  - `listing_id = 9101`
  - `state_code = "active"`
  - seller login `alice`

---

## Edge Cases to Check Deliberately

### Edge Case A — Thin-support modules remain visible
1. Revisit the overview modules for price band, condition, and sold state.
2. Confirm they are still shown even though no row reaches the support threshold of `3`.
3. **Expected:** the UI marks them as fragile / thin-support instead of removing them.

### Edge Case B — Partial public data still renders without crashing the product
1. In the explorer, locate listing `9106` (`Jupe incertaine`).
2. **Expected:** the row renders with fallback labels (`Unknown brand`, `Seller not exposed`, `price n/a`) and the page remains stable.

### Edge Case C — Degraded acquisition is explicit, not silently absorbed
1. On `/`, inspect the honesty/freshness context again.
2. In `/api/dashboard`, inspect `summary.freshness.recent_acquisition_failures`.
3. **Expected:** the seeded `Femmes > Jupes` scan failure is visible in both the product surface and the JSON payload.

---

## Failure Signals

Treat S01 as failed if any of the following happen:
- `/` still looks like the old M001 proof dashboard rather than the French overview home.
- The home page requires full ranking tables/proof stacks before the user can understand the market overview.
- Comparison modules with thin support disappear instead of staying visible with caution cues.
- `/api/dashboard` no longer exposes `honesty_notes`, comparison module status/reason, or the overview summary blocks behind the home page.
- `/explorer` stops being a separate SQL-paged browse surface.
- `/api/runtime` or `/health` stops working while the dashboard server is up.
- The page produces console errors or failed network requests during normal load on `/` or `/explorer`.

---

## Notes for Tester

- This UAT is intentionally scoped to **S01 only**. It proves the overview-home replacement and the first comparative modules.
- It does **not** close the later M002 work for persisted pause/resume runtime truth, the responsive French shell, full explorer comparative workflows, narrative listing detail, or degraded-mode hardening.
- If the home works but deeper price-band / sold-state explorer filtering is still missing, that is a **known S01 boundary**, not a surprise regression.
