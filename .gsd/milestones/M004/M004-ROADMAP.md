# M004: 

## Vision
Turn the radar from a listing-level reader into a grounded product-intelligence layer that can reason at the level of products, recurring market objects, and evidence-backed AI interpretation without ever hiding the boundary between observed fact, calculated inference, AI interpretation, and broader hypothesis.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Conservative Product Grouping with Confidence + Provenance | high | — | ⬜ | After this: a user can inspect conservative product/group candidates, confidence bands, provenance, and deliberate non-merges on real radar data. |
| S02 | Stable Grouped Reads via PostgreSQL + ClickHouse Parity | high | S01 | ⬜ | After this: grouped leaders, comparisons, and detail reads stay stable across refreshes and backend read paths because they are projection-backed, not recomputed ad hoc. |
| S03 | Grounded Inline Insights on Grouped Markets | high | S01, S02 | ⬜ | After this: grouped market surfaces show inline AI insights with cited evidence windows, confidence, and explicit abstention when support is weak. |
| S04 | Weekly Synthesis + Eventful Change Briefs | medium | S02, S03 | ⬜ | After this: the product can publish weekly grouped-market syntheses and shorter change briefs only when meaningful events occur, with explicit confidence and evidence windows. |
| S05 | Grounded Analytical Copilote | high | S01, S02, S03, S04 | ⬜ | After this: a user can ask concrete market questions through a copilote UI and receive grounded answers with support windows, explicit labels, and graceful abstention. |
