---
id: T02
parent: S03
milestone: M002
provides:
  - A shared French-first SSR shell reused by overview, explorer, runtime, and listing detail
  - Responsive card/grid layouts for explorer, runtime, and detail that remain usable on phone widths without relying on wide desktop tables
  - Product-layer translation of primary labels, filter options, freshness/status wording, and detail copy without changing the repository contract
key_files:
  - vinted_radar/dashboard.py
  - tests/test_dashboard.py
key_decisions:
  - D019: keep the existing SSR architecture and deepen it instead of rewriting the UI stack
patterns_established:
  - Treat route-specific content as panels inside one shared shell (`_render_product_shell`) so navigation, landmarks, palette, and responsive behavior stay aligned across the product
observability_surfaces:
  - `python -m pytest tests/test_dashboard.py`
  - browser verification on `/`, `/explorer`, `/runtime`, and `/listings/<id>`
  - viewport overflow checks via `document.documentElement.scrollWidth <= window.innerWidth`
duration: 1h35m
verification_result: passed
completed_at: 2026-03-23T10:56:26+01:00
blocker_discovered: false
---

# T02: Build the shared French responsive shell across overview, explorer, runtime, and detail

**Rebuilt the four HTML routes onto one French shared shell and replaced the explorer/runtime desktop-heavy layouts with mobile-safe card flows.**

## What Happened

T01 made the routes real; T02 made them read like one product.

In `vinted_radar/dashboard.py`, I introduced three shared UI seams:
- `_render_product_nav(...)`
- `_shared_shell_styles()`
- `_render_product_shell(...)`

Those now own the common shell contract:
- one palette and typography system
- one primary navigation with `aria-current`
- one skip-link / landmark structure
- one responsive button/card/panel vocabulary
- one consistent page chrome across overview, explorer, runtime, and detail

Then I rebuilt each page onto that shell.

### Overview (`/`)
The home page keeps the S01/S02 evidence modules, but now sits inside the shared shell. I preserved the SQL-backed content sections and honesty panels while making the header/navigation consistent with the rest of the product.

### Explorer (`/explorer`)
This is where the biggest UX change landed.

The previous explorer still behaved like a brownfield desktop table. I replaced that primary consumption path with responsive listing cards that expose:
- title / id / brand
- price + freshness chips
- seller visibility
- estimated publication and radar timing
- latest probe
- direct actions to HTML detail, JSON detail, explorer focus, and Vinted

The filter form, stats, and pagination remain, but the page no longer depends on a `min-width: 1320px` table to be useful on mobile.

### Runtime (`/runtime`)
The runtime page now uses the same shell and replaces the cycle table with cycle cards. The controller facts, recent cycles, recent failures, and semantics notes still show the same truth, but the route now reads as part of the product rather than a separate admin screen.

### Detail (`/listings/<id>`)
The detail route now inherits the shared shell and a French-first vocabulary. I translated the visible copy layer around the existing evidence payload:
- primary labels
- seller/public-field wording
- timing / inference / score-context sections
- freshness labels and state/basis/confidence pills
- transition descriptions

I also translated the explorer-facing option labels and freshness wording in the product layer so the shell no longer leaks obvious English UX strings like `All roots`, `Recently seen`, or `first-pass-only`.

The browser pass surfaced one useful design issue after the first cut: hero actions were duplicating the primary navigation and stacking too many buttons on mobile. I removed those redundant CTAs so the shell keeps diagnostics available without fighting itself on small screens.

## Verification

T02 verification passed at two levels:

1. **Route regression tests**
   - `python -m pytest tests/test_dashboard.py`
2. **Live browser verification on the seeded S03 DB**
   - served `data/vinted-radar-s03.db` locally through `python -m vinted_radar.cli dashboard --db data/vinted-radar-s03.db --host 127.0.0.1 --port 8782`
   - desktop checks confirmed shared shell structure and route-level content on `/`, `/explorer`, `/runtime`, and `/listings/9002`
   - mobile checks confirmed no horizontal overflow on `/`, `/explorer`, `/listings/9002`, and `/runtime` (`scrollWidth <= innerWidth`), plus readable stacked nav/actions on phone width
   - browser console and network stayed clean during the checks

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py` | 0 | ✅ pass | 0.39s |

## Diagnostics

For future inspection:
- `python -m pytest tests/test_dashboard.py` is the quickest drift alarm for the shared shell contract.
- Open `/`, `/explorer`, `/runtime`, and `/listings/<id>` at both desktop and mobile widths before touching shell code again.
- The most useful mobile check is `document.documentElement.scrollWidth <= window.innerWidth`; T02 explicitly proved that on overview, explorer, detail, and runtime.
- If the shell starts feeling inconsistent again, inspect `_render_product_shell(...)` and `_shared_shell_styles()` first instead of patching route HTML independently.

## Deviations

I replaced the runtime cycle table with cycle cards during T02. The plan only required responsive shell/layout work, but the browser pass made it clear that keeping the wide runtime table as the primary mobile representation would undermine the same-phone consultability goal that drove the explorer rewrite.

## Known Issues

- Listing titles and some raw market content still come straight from source data, so the shell is French-first but the underlying listing text can remain English or mixed-language when the source listing is.
- The detail route is structurally integrated into the shared shell, but it is not yet narrative-first. S05 still owns the deeper plain-language storytelling and progressive disclosure.
- The comparison/detail evidence copy is now translated, but the underlying scoring/state payloads remain technical by design; T05 can still improve how that proof is narrated.

## Files Created/Modified

- `vinted_radar/dashboard.py` — added the shared shell helpers, rewrote overview/explorer/runtime/detail HTML around them, localized visible labels, translated freshness/status wording, and replaced explorer/runtime table-first layouts with responsive cards.
- `tests/test_dashboard.py` — expanded route assertions for the shared shell, French-first explorer copy, mobile-safe explorer structure, detail-shell integration, and prefixed route preservation.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — T02 marked complete.
