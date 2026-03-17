---
depends_on: [M001, M002]
---

# M003: Product-Level Intelligence + Grounded AI Layer

**Gathered:** 2026-03-17
**Status:** Ready for planning

## Project Description

Turn the radar from a strong listing-level market reader into a grounded market-intelligence layer that can reason at the level of products, article types, recurring market patterns, and evidence-backed analytical interpretation.

This milestone adds cautious product-level grouping across similar listings and an AI layer that helps interpret the collected market data without replacing it as the source of truth. The AI layer should enrich the dashboard with inline insights, generate structured periodic syntheses, and power an analytical copilote that answers real market questions while showing the observations, time windows, confidence, and grouped evidence behind its conclusions.

The product must remain strict about the boundary between observed fact, calculated inference, AI interpretation, and broader hypothesis.

## Why This Milestone

M001 proves the listing-level radar loop. M002 enriches the market reading and overall product experience. M003 changes the nature of the tool itself.

At this point, the user no longer wants only a better list of listings or a better summary of segments. The product should begin to surface the actual market objects that matter: recurring product types, repeated patterns across listings, higher-order segment movement, and evidence-backed interpretations that would be hard to detect manually.

This milestone matters because it is the transition from a useful radar to a true market-intelligence system.

## User-Visible Outcome

### When this milestone is complete, the user can:

- see that multiple listings resolve into cautious product-level groupings that represent real market objects rather than isolated listing wins
- read inline AI insights and weekly syntheses that surface non-trivial product and market patterns with linked evidence and explicit confidence
- ask the copilote real market questions and get answers grounded in observed data, grouped entities, time windows, and justification surfaces

### Entry point / environment

- Entry point: local or hosted product dashboard surfaces plus an analytical copilote interface
- Environment: browser / local dev first, potentially production-like later
- Live dependencies involved: existing radar database and evidence model, product grouping pipeline, AI inference layer, dashboard UI

## Completion Class

- Contract complete means: product grouping, confidence bands, inline insight surfaces, synthesis generation, and copilote answer contracts all exist with substantive implementation and verification surfaces.
- Integration complete means: grouping, AI interpretation, dashboard views, and copilote responses all operate on the real radar data model and can link conclusions back to observed evidence.
- Operational complete means: grouping refreshes and AI outputs remain stable enough to support recurring market reading without producing noisy or unsupported conclusions.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- grouped product views reveal meaningful market winners or patterns that are not obvious from isolated listing-level inspection alone
- weekly syntheses and meaningful-change briefs produce insights that add real analytical value rather than paraphrasing existing tops
- the copilote can answer concrete market questions from radar data, show its support, label interpretation versus observation correctly, and avoid behaving like an oracle

## Risks and Unknowns

- Product grouping may over-merge distinct items — false merges would contaminate the market read more severely than missing some valid merges
- AI outputs may sound useful while drifting away from evidence — unsupported fluency would erode trust quickly
- Weekly syntheses may become decorative restatements of dashboard content — the milestone must produce genuinely higher-order signal, not repetition
- The copilote may blur the boundary between observed data and interpretation — the answer contract must preserve explicit source separation

## Existing Codebase / Prior Art

- `M001` outputs — listing history, cautious states, confidence, and evidence linkage provide the factual substrate for M003
- `M002` outputs — enriched market views, comparisons, exports, and product UX improvements provide the stronger interaction layer M003 builds on

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R013 — introduces product-level grouping across similar listings
- R014 — introduces grounded AI insights and market syntheses
- R015 — introduces the grounded analytical copilote
- R007 — benefits from stronger contextual reasoning when grouping and interpreting products
- R008 — is upgraded from segment summary to higher-order product and pattern interpretation
- R009 — gains deeper drill-down and justification surfaces through grouped product views and AI evidence links

## Scope

### In Scope

- cautious product-level grouping that prefers false splits over false merges
- explicit grouping confidence bands such as grouped with high confidence, probable grouping, and uncertain/not merged
- inline AI insight surfaces inside the dashboard
- structured weekly market synthesis as the primary narrative output
- shorter briefs only when meaningful changes occur
- analytical copilote grounded first in radar data, grouped entities, and linked evidence
- explicit separation between observed fact, calculated inference, AI interpretation, and broader contextual hypothesis

### Out of Scope / Non-Goals

- magical oracles that answer without evidence linkage
- aggressive auto-merging of ambiguous product clusters
- verbose daily commentary with little analytical value
- AI outputs that obscure confidence, grouping quality, or evidence gaps

## Technical Constraints

- False merges are worse than false splits; grouping automation must reflect that risk posture.
- AI outputs must be grounded first in collected radar data and grouped entities.
- Any broader general reasoning or context added by the copilote must be clearly labeled and never presented as radar-observed fact.
- Weekly synthesis is the primary cadence; shorter briefs must be eventful, not filler.
- The product must preserve a clean fact / inference / interpretation / hypothesis boundary.

## Integration Points

- grouped-entity layer built on top of listing observations and evidence linkage
- dashboard insight surfaces that consume grouped entities and AI interpretations
- synthesis generation pipeline tied to time windows, changes, and confidence thresholds
- copilote interface backed by radar data retrieval, grouped evidence, and explicit answer attribution

## Open Questions

- Which grouping approach is best after M001/M002 data quality is known: rule-first with probabilistic fallback, graph clustering, or another hybrid — current thinking: use deterministic matching for strong cases and probabilistic/AI support for ambiguous ones, while preserving confidence thresholds
- How should grouped entities surface survivorship and conflict resolution when listings disagree — current thinking: preserve provenance and avoid pretending the product entity is cleaner than the source evidence
- How much general reasoning should the copilote add beyond radar-grounded answers — current thinking: allow it only as clearly labeled supplemental interpretation, never as the primary answer layer
