# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and all of their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a credible market read about what is actually selling now.

## Core Value

Turn imperfect public Vinted listing signals into a credible, evidence-backed market read that shows what is really moving now.

## Current State

S01 through S05 are complete. The repository now has a runnable Python batch collector that syncs the public Homme/Femme catalog tree, scans public catalog pages, persists normalized listing cards in SQLite, records one normalized observation per listing per run, derives cautious current listing states with confidence and explanation surfaces, computes explainable demand / premium rankings plus market segment summaries, and serves a local dashboard over the same repository-backed payloads.

Repeated runs against the same database now expose first seen, last seen, observation count, average revisit gap, freshness buckets, ranked revisit candidates, item-page probe diagnostics, state detail, per-listing score breakdowns, performing/rising segment summaries, and a browser-verified dashboard with coverage/freshness/confidence cards, filterable demand / premium ranking tables, JSON diagnostics, and listing-detail drill-down into history, transitions, signals, and inference basis. Continuous mode is still unimplemented.

## Architecture / Key Patterns

Local-first execution with both batch and continuous operation modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, state transitions, and estimated time-to-sell can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by drill-down into the listing-level evidence that justifies them.

S01 acquisition currently uses public server-rendered HTML only: the full Homme/Femme catalog tree is extracted from the embedded `self.__next_f.push(...)` payload on `/catalog`, and listing discovery comes from SSR item cards rather than browser automation or private APIs.

SQLite is the first durable runtime boundary. Discovery runs, per-catalog scans, listings, and listing sightings are persisted so coverage and failures remain inspectable after each batch run.

S02 adds a second history layer: `listing_observations` stores one normalized observation per listing per run for cadence/freshness queries, while `listing_discoveries` remains the per-sighting diagnostic surface for debugging catalog/page behavior.

S03 adds a cautious state layer over that history: optional `item_page_probes` capture direct public evidence from item pages, and the state engine combines probes plus follow-up-miss history into `active`, `sold_observed`, `sold_probable`, `unavailable_non_conclusive`, `deleted`, and `unknown` surfaces with confidence and reasons.

S04 adds an on-demand scoring layer over the state/history surfaces: `demand` ranks sell-through evidence, `premium` stays demand-led with a modest contextual price boost when peer support is strong enough, and market summaries aggregate performing and rising segments from the same evidence base.

S05 adds a local product surface: a server-rendered dashboard plus matching JSON diagnostics built directly from the repository/state/scoring payloads, so filters, ranking tables, and listing detail views stay aligned with the CLI truth surfaces instead of drifting into separate client logic.

Milestone sequencing is deliberate: build a credible listing-level radar first, enrich the market reading next, then add product-level intelligence plus AI, and only then harden for SaaS commercialization.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [ ] M001: Listing-Level Market Radar — Build a credible local radar that discovers, revisits, scores, and explains what is moving now on Vinted Homme/Femme.
- [ ] M002: Enriched Market Intelligence Experience — Deepen market reading, contextual analysis, UX richness, and user-facing utility features.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — Group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — Industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
