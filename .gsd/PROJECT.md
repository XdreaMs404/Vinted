# Project

## What This Is

A local-first Vinted market intelligence radar focused strictly on the Homme and Femme categories and all of their sub-categories. It tracks public listings over time, separates what was observed from what was inferred, and turns imperfect public signals into a credible market read about what is actually selling now.

## Core Value

Turn imperfect public Vinted listing signals into a credible, evidence-backed market read that shows what is really moving now.

## Current State

The repository is at bootstrap stage. Planning artifacts for the first milestone exist, but no collector, revisit engine, state machine, scoring pipeline, scheduler, or dashboard has been implemented yet.

## Architecture / Key Patterns

Local-first execution with both batch and continuous operation modes.

Evidence-first product logic: preserve observed facts, derive inferences explicitly, and surface uncertainty instead of hiding it.

Historical observation storage rather than last-write-wins snapshots, so listing evolution, state transitions, and estimated time-to-sell can be traced over time.

Mixed market surface: market summaries and rankings must always be backed by drill-down into the listing-level evidence that justifies them.

Milestone sequencing is deliberate: build a credible listing-level radar first, enrich the market reading next, then add product-level intelligence plus AI, and only then harden for SaaS commercialization.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [ ] M001: Listing-Level Market Radar — Build a credible local radar that discovers, revisits, scores, and explains what is moving now on Vinted Homme/Femme.
- [ ] M002: Enriched Market Intelligence Experience — Deepen market reading, contextual analysis, UX richness, and user-facing utility features.
- [ ] M003: Product-Level Intelligence + Grounded AI Layer — Group listings into product-level signals and add grounded AI insights, summaries, and analytical exploration.
- [ ] M004: SaaS Hardening and Commercialization — Industrialize the radar into a durable SaaS product without sacrificing evidence and credibility.
