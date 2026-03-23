# S04: Full Explorer + Comparative Intelligence

**Goal:** Turn `/explorer` into the main browsing workspace over the real corpus with SQL-backed filters, sorting, paging, and comparison modules across category, brand, price band, condition, and sold state, while keeping support levels and uncertainty explicit.
**Demo:** Run `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8783`, open `/explorer`, apply filters and paging across root, brand, price band, condition, and sold state, and verify that overview drill-down links land on the expected explorer state with comparison modules and listing links sourced from SQL instead of full-corpus Python recomputation.

## Must-Haves

- Expand the repository/explorer contract to first-class filters for category/root, brand, price band, condition, sold state, query, sort, and server-side paging.
- Add comparison modules that surface category, brand, price band, condition, and sold-state cuts with support counts, honesty notes, and drill-down values.
- Preserve deep-linkable query state from overview into explorer and from explorer into listing detail.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest tests/test_explorer_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8783`
- Browser verification at `http://127.0.0.1:8783/explorer` confirms filterable paging, comparison support counts, overview drill-down links, and context-preserving links into listing detail.

## Observability / Diagnostics

- Runtime signals: active filters, total matches, current page, comparison support counts, low-support notes, and explicit empty-state reasons.
- Inspection surfaces: `/explorer`, `/api/explorer`, overview deep links, listing-detail routes, and repository/dashboard tests for the explorer contract.
- Failure visibility: invalid filters, unsupported low-sample comparisons, or paging drift remain visible in payload assertions and browser-visible empty/support states.
- Redaction constraints: expose only public listing metadata and aggregate comparison evidence; no secrets or operator-only credentials belong in explorer payloads.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/repository.py`, `vinted_radar/dashboard.py`, `vinted_radar/cli.py`, S01 overview modules, and S03 shared navigation/detail routes.
- New wiring introduced in this slice: stronger SQL explorer contract, comparison modules, overview-to-explorer deep links, and context-preserving listing drill-down flow.
- What remains before the milestone is truly usable end-to-end: S05 still needs narrative-first detail reading, S06 still needs degraded acquisition truth across the explorer/detail flow, and S07 still needs live VPS proof.

## Tasks

- [x] **T01: Expand the SQL explorer and comparison contract** `est:1h30m`
  - Why: The explorer only becomes the real corpus workspace if SQL can answer the core browse/compare questions directly, without falling back to full-corpus Python reshaping.
  - Files: `vinted_radar/repository.py`, `tests/test_repository.py`, `tests/test_explorer_repository.py`, `vinted_radar/scoring.py`
  - Do: add server-side filters and paging for brand, price band, condition, sold state, query, and sort; expose comparison aggregates with support metadata and deep-link values; keep low-support honesty explicit in the repository contract.
  - Verify: `python -m pytest tests/test_explorer_repository.py tests/test_repository.py`
  - Done when: the repository alone can answer the explorer's main browse and comparison workflows with explicit support/uncertainty data.
- [x] **T02: Rebuild `/explorer` for scalable browsing on desktop and mobile** `est:1h30m`
  - Why: S04 fails if the query contract exists but the explorer still feels like a debug table instead of a browsing workspace for a large corpus.
  - Files: `vinted_radar/dashboard.py`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`, `README.md`
  - Do: redesign the explorer UI around server-side filters, comparison panels, result summaries, paged listings, and mobile-friendly result patterns that keep honest support counts visible instead of hiding them.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: `/explorer` can browse the real corpus through filters, sorts, paging, and comparisons without relying on oversized desktop tables as the only interaction model.
- [x] **T03: Wire overview drill-down and context-preserving listing navigation** `est:1h`
  - Why: The market overview and listing detail only become one analytical loop if overview modules open the explorer in the right context and detail views let the user return without losing that context.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/repository.py`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`
  - Do: turn overview modules into explorer deep links, preserve active explorer lens/query state in detail links and back navigation, and ensure comparison context stays visible when moving between overview, explorer, and listing detail.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: overview cards land on the right explorer state and listing drill-downs preserve enough context for the user to return to the same analytical lens.

## Files Likely Touched

- `vinted_radar/repository.py`
- `vinted_radar/dashboard.py`
- `vinted_radar/cli.py`
- `vinted_radar/scoring.py`
- `README.md`
- `tests/test_repository.py`
- `tests/test_explorer_repository.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
