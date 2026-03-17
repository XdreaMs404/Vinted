# M001: Listing-Level Market Radar

**Gathered:** 2026-03-17
**Status:** Ready for planning

## Project Description

Build the first usable version of a local-first Vinted market radar focused strictly on the Homme and Femme categories and all of their sub-categories. The milestone must discover public listings, revisit them over time, store their history, infer cautious status transitions, compute the first “demande pure” and “premium” market readings, and expose all of that through a mixed dashboard that keeps market summaries tied to listing-level proof.

The product must not pretend to know more than it really observed. It must show what was observed directly, what was inferred, what remains uncertain, how broad the current coverage is, and how fresh the revisit data is.

## Why This Milestone

This milestone proves that the project is more than a scraper. It establishes the full radar loop in real local conditions: broad public discovery, intelligent revisits, preserved observation history, prudent state inference, explainable scores, and a usable product surface.

This must happen now because every richer market capability depends on whether the basic observation engine is trustworthy. If M001 cannot generate a credible listing-level radar after a few days of real runtime, later enrichment, AI, and SaaS work would sit on sand.

## User-Visible Outcome

### When this milestone is complete, the user can:

- run the radar locally and open a dashboard that shows which Homme/Femme sub-categories and listings appear to perform best right now, with explicit coverage, confidence, and evidence surfaces
- drill from market summaries into listing-level history, observed signals, cautious state transitions, and the basis for each inference

### Entry point / environment

- Entry point: local CLI commands for batch and continuous modes plus a local dashboard URL
- Environment: local dev
- Live dependencies involved: Vinted public web pages, local database/storage, local scheduler/daemon, local web dashboard

## Completion Class

- Contract complete means: discovery, observation history, state inference, score calculation, filters, and listing detail surfaces all exist with substantive implementation and can be verified through tests, fixtures, and artifact checks.
- Integration complete means: the collector, revisit engine, storage, state machine, scoring logic, and dashboard work together against live public Vinted data.
- Operational complete means: batch mode and continuous mode both run locally, persist state correctly, and keep the radar alive across repeated execution over multiple days.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- a local user can run a batch collection, then open the dashboard and see a credible mixed view with coverage, market summaries, listing rankings, and drill-down evidence
- a local continuous run can revisit listings over time, update observation history, and produce cautious state transitions that remain traceable and uncertainty-aware
- the milestone has been exercised against real public Vinted behavior over multiple days; this cannot be reduced to fixtures alone because credibility depends on live observation and time-based change

## Risks and Unknowns

- Broad public coverage may be harder than expected under anti-bot, pacing, and public-site variability constraints — weak coverage would distort every downstream market conclusion
- Public disappearance signals may not cleanly separate sold, unavailable, and deleted states — overconfident state logic would damage trust immediately
- Incomplete or inconsistent public fields may reduce scoring quality — the system must degrade gracefully rather than collapse or fake certainty
- The first market scores may look convincing without actually being defensible — the milestone must preserve explainability and evidence linkage from day one

## Existing Codebase / Prior Art

- `.` — the repository currently contains only scaffolding and planning artifacts; M001 can shape the architecture deliberately instead of conforming to legacy code
- `.gitignore` — local state, environment files, and GSD runtime artifacts are already excluded, which supports local-first development and long-running runtime data

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R001 — establishes broad public Homme/Femme discovery as the radar’s evidence base
- R002 — introduces revisit history so the system can reason over time instead of snapshots
- R003 — defines cautious, traceable listing states
- R004 — makes coverage, freshness, and confidence visible in the actual product
- R005 — delivers the first “demande pure” ranking
- R006 — delivers the first “premium” ranking
- R007 — starts lightweight contextual scoring where support is strong enough
- R008 — provides the first market summary with rising segments and sub-category performance
- R009 — exposes the mixed dashboard, filters, and listing detail history
- R010 — proves both local batch and continuous operation
- R011 — ensures missing public signals degrade gracefully instead of breaking the radar

## Scope

### In Scope

- discovery seeds and entry points for Homme/Femme plus all reachable sub-categories
- normalized ingestion that preserves important raw fields and enough source evidence for debugging and traceability
- revisit strategy, historical observation storage, and freshness surfaces
- cautious status inference with explicit ambiguity and confidence handling
- first “demande pure” and “premium” rankings with lightweight contextualization where robust
- mixed dashboard with filters, listing drill-down, and visible coverage / confidence / freshness surfaces
- local batch mode and local continuous mode

### Out of Scope / Non-Goals

- product-level grouping across similar listings
- AI-generated insights, periodic summaries, or copilote workflows
- rich comparisons, rich exports, alerts, or collaboration features
- commercialization hardening, hosted deployment, or multi-user SaaS concerns
- coverage outside Vinted Homme/Femme and their sub-categories

## Technical Constraints

- No login required.
- Avoid fragile approaches and avoid central dependency on undocumented private APIs.
- Preserve a clean separation between observed data, inferred conclusions, and uncertainty.
- Missing public fields must never break the pipeline.
- The system should be operable locally by one user without excessive complexity.
- Market summaries must always stay tethered to visible listing-level proof.

## Integration Points

- Vinted public listing and category pages — discovery and observation source of truth
- local persistence layer — stores normalized listings, historical observations, raw trace/debug evidence, and derived scores
- local scheduler / daemon — revisits listings and keeps the radar alive over time
- local dashboard — exposes market summaries, rankings, filters, coverage, confidence, and listing-level drill-down

## Open Questions

- Which collection mix is safest and most effective for broad Homme/Femme coverage under real anti-bot pressure — current thinking: design for incremental discovery plus prioritized revisits, with observability on gaps
- What is the minimum raw capture we should retain for debugging and traceability without bloating storage — current thinking: preserve targeted raw evidence for fields and state transitions rather than full-page archives by default
- How aggressive can revisit cadence be before it harms reliability or maintainability — current thinking: freshness tiers and priority queues should shape pacing instead of uniform revisits
