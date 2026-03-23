# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a cautious market read about what appears to be moving now.

## Core Value

Turn imperfect public Vinted listing signals into an evidence-backed market read that stays explicit about coverage, freshness, confidence, and uncertainty.

## Current State

M001 implementation is complete and integrated across S01 through S06, and its closeout summary now exists at `.gsd/milestones/M001/M001-SUMMARY.md`. That milestone still carries a **needs-attention** closeout result because the historical proof databases are not yet trustworthy enough for final multi-day acceptance.

M002 is now underway. S01 and S02 are complete: the home path is SQL-backed and French-first, and runtime truth now lives in a separate controller snapshot with pause/resume/scheduling surfaced through the CLI, `/runtime`, `/api/runtime`, `/health`, and the overview freshness copy.

What is verified today:
- `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_dashboard_cli.py tests/test_db_recovery.py` passes
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765` serves the SQL-backed overview home plus the dedicated runtime page from the seeded slice DB
- `python -m vinted_radar.cli continuous --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8781` runs a live local loop whose controller truth is visible through `runtime-status`, `runtime-pause`, `runtime-resume`, `/runtime`, `/api/runtime`, `/health`, and `/`
- live smoke verification proved `running` → `paused` → `scheduled` transitions through CLI controls and matching HTTP/browser surfaces on the same SQLite DB
- the home surface now exposes tracked inventory, state mix, confidence, freshness, low-support honesty notes, recent acquisition failures, first comparison modules, and controller-backed runtime wording directly from repository SQL + runtime contracts instead of full-corpus request-time home recomputation

What is still pending on the roadmap:
- M001 still needs trustworthy multi-day closeout evidence from healthy historical databases
- M002 still needs the responsive French product shell / VPS serving path, deeper explorer filters and comparative modules, narrative listing detail, degraded-mode hardening, and final live VPS acceptance

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

Current fragility exposed during M001 closeout: schema/index bootstrap ordering can outrun migrations on older SQLite files, so backward compatibility for pre-existing DBs is weaker than intended.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Listing-Level Market Radar — implementation complete; closeout summary written, verification result `needs-attention` pending healthy multi-day runtime proof.
- [ ] M002: Enriched Market Intelligence Experience — in progress; S01 and S02 complete with the SQL-backed overview home plus controller-backed runtime truth and pause/resume surfaces.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
