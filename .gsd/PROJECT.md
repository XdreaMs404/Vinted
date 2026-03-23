# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a cautious market read about what appears to be moving now.

## Core Value

Turn imperfect public Vinted listing signals into an evidence-backed market read that stays explicit about coverage, freshness, confidence, and uncertainty.

## Current State

M001 implementation is complete and integrated across S01 through S06, and its closeout summary now exists at `.gsd/milestones/M001/M001-SUMMARY.md`. That milestone still carries a **needs-attention** closeout result because the historical proof databases are not yet trustworthy enough for final multi-day acceptance.

M002 is now underway. S01 through S04 are complete: the home path is SQL-backed and French-first, runtime truth now lives in a separate controller snapshot with pause/resume/scheduling surfaced through the CLI, `/runtime`, `/api/runtime`, `/health`, and the overview freshness copy, the product ships with a shared responsive shell plus a mounted VPS-serving contract across overview, explorer, runtime, and HTML listing detail, and `/explorer` is now the main browse-and-compare workspace with SQL-backed filters, comparison modules, paging, and context-preserving detail drill-down.

What is verified today:
- `python -m pytest` passes
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8783` serves the richer explorer workflow locally across `/`, `/explorer`, `/runtime`, `/listings/<id>`, and the paired JSON/health routes
- browser verification at `http://127.0.0.1:8783/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12` confirmed filterable explorer browsing, scoped comparison support counts, explorer-to-detail context preservation, and a truthful return-to-results path on the S04 demo DB
- the explorer route now exposes root/catalog/brand/condition/state/price-band/query/sort/page/page-size filters, SQL-backed comparison modules, explicit low-support honesty cues, and listing links that preserve the active analytical lens into detail
- legacy SQLite snapshots missing late-added listing metadata columns now reopen successfully because migrations run before dependent indexes are created, with regression coverage in `tests/test_repository.py`

What is still pending on the roadmap:
- M001 still needs trustworthy multi-day closeout evidence from healthy historical databases
- M002 still needs narrative listing detail, degraded-mode hardening, and final live VPS acceptance

## Architecture / Key Patterns

Local-first execution with both batch and continuous operator modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, freshness, and revisit cadence can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by listing-level drill-down.

Discovery currently uses the Vinted web catalog API for throughput, while public item pages remain a separate direct-evidence path for cautious state resolution.

SQLite is the durable runtime boundary. Discovery runs, catalog scans, listings, discoveries, observations, item-page probes, and runtime cycles are all persisted so coverage, failures, and operator state remain inspectable after each run.

The dashboard is server-rendered and shares one repository-backed payload with its JSON diagnostics so the browser surface and debug surface stay truthful.

M002/S01 begins retiring request-time Python recomputation on primary user paths by moving the overview home and explorer browse path onto repository-owned SQL aggregates/pages, while `/api/dashboard` remains the brownfield compatibility seam for diagnostics and existing callers.

M002/S02 adds a separate `runtime_controller_state` snapshot for current scheduler truth while keeping `runtime_cycles` as immutable history, so `/runtime`, `/api/runtime`, `/health`, and the overview home can distinguish running, scheduled, paused, failed, and recent-cycle outcomes honestly.

Legacy SQLite snapshots can still lag the current schema, but bootstrap now migrates late-added listing metadata columns before creating dependent indexes; `tests/test_repository.py::test_repository_migrates_legacy_listing_columns_before_creating_dependent_indexes` is the guardrail for that path.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Listing-Level Market Radar — implementation complete; closeout summary written, verification result `needs-attention` pending healthy multi-day runtime proof.
- [ ] M002: Enriched Market Intelligence Experience — in progress; S01 through S04 complete with the SQL-backed overview home, controller-backed runtime truth, shared French product shell, mounted VPS-serving contract, and the new SQL-first explorer workspace.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
