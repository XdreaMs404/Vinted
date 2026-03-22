# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a cautious market read about what appears to be moving now.

## Core Value

Turn imperfect public Vinted listing signals into an evidence-backed market read that stays explicit about coverage, freshness, confidence, and uncertainty.

## Current State

M001 implementation is complete and integrated across S01 through S06, and its closeout summary now exists at `.gsd/milestones/M001/M001-SUMMARY.md`.

Current closeout verification result: **needs-attention**.

What is verified today:
- the codebase passes `python -m pytest` with 100 passing tests
- a fresh live `batch` cycle still succeeds against public Vinted data
- the resulting SQLite DB supports coverage, state, runtime, and market-summary diagnostics
- the local dashboard still renders market summary, ranking proof, runtime state, and listing detail without console or network errors

What is still blocking a passing M001 closeout:
- the milestone roadmap requires several days of healthy, readable runtime evidence proving that the market read is already useful after multi-day operation
- `data/vinted-radar.db` contains multi-day runtime metadata across three distinct days, but its listing-history tables are malformed and cannot serve as trustworthy closeout proof
- `data/m001-closeout.db` remains a same-day corpus and currently fails to open through the repository bootstrap path because older DB compatibility regressed around `listings.created_at_ts`

So the product is operational, but the milestone is not yet verified as fully complete in the roadmap sense.

## Architecture / Key Patterns

Local-first execution with both batch and continuous operator modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, freshness, and revisit cadence can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by listing-level drill-down.

Discovery currently uses the Vinted web catalog API for throughput, while public item pages remain a separate direct-evidence path for cautious state resolution.

SQLite is the durable runtime boundary. Discovery runs, catalog scans, listings, discoveries, observations, item-page probes, and runtime cycles are all persisted so coverage, failures, and operator state remain inspectable after each run.

The dashboard is server-rendered and shares one repository-backed payload with its JSON diagnostics so the browser surface and debug surface stay truthful.

`runtime_cycles` is the operator truth for batch/continuous phase, counts, and last-error state, surfaced through the CLI, `/api/runtime`, `/health`, and the dashboard runtime card.

Current fragility exposed during M001 closeout: schema/index bootstrap ordering can outrun migrations on older SQLite files, so backward compatibility for pre-existing DBs is weaker than intended.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Listing-Level Market Radar — implementation complete; closeout summary written, verification result `needs-attention` pending healthy multi-day runtime proof.
- [ ] M002: Enriched Market Intelligence Experience — deepen market reading, contextual analysis, UX richness, and user-facing utility features.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
