# M003: 

## Vision
Turn the radar from a listing-level reader into a grounded product-intelligence layer by introducing cautious product grouping, evidence-backed AI interpretation, periodic synthesis, and an analytical copilote that always shows what was observed, what was inferred, what was interpreted, and where support is insufficient.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Conservative product grouping with confidence + provenance | high | — | ⬜ | A user opens a real grouped-products surface in the dashboard/explorer and can inspect strong product merges, probable groups, and deliberate non-merges on live radar data, with provenance explaining why listings were grouped and links back to member listings. |
| S02 | Stable grouped reads via Postgres + ClickHouse parity | high | S01 | ⬜ | After refreshes and backend cutover, a user can still browse grouped leaders/comparisons/detail and see the same grouped truth, with grouped reads powered by persisted projection and parity-checked analytical marts rather than request-time fuzzy grouping. |
| S03 | Grounded inline insights on grouped markets | high | S01, S02 | ⬜ | A user viewing grouped market surfaces sees inline AI insight blocks that highlight non-trivial grouped patterns, show evidence links, time windows, and confidence, and explicitly abstain when support is too weak. |
| S04 | Weekly synthesis + eventful change briefs | medium | S02, S03 | ⬜ | A user can open a weekly grouped-market synthesis that surfaces higher-order winners, shifts, and conflicts with explicit evidence windows and confidence, and can also read shorter briefs only when meaningful changes trigger them. |
| S05 | Grounded analytical copilote | high | S01, S02, S03, S04 | ⬜ | Through a real copilote UI, a user asks concrete market questions and receives answers grounded in grouped/listing evidence with cited support windows, explicit observation/inference/interpretation/hypothesis sections, and graceful abstention when support is insufficient. |
