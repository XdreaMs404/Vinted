---
id: S04
parent: M001
milestone: M001
provides:
  - Explainable listing-level `demand` and `premium` scores
  - Market summary surfaces for performing and rising segments
  - Context-thresholded price baselines with graceful no-context fallback
requires:
  - slice: S02
    provides: listing history, freshness, revisit cadence, and primary-catalog scan history
  - slice: S03
    provides: cautious current-state evaluations, confidence, and probe-backed state evidence
affects:
  - S05
  - S06
key_files:
  - vinted_radar/scoring.py
  - vinted_radar/cli.py
  - tests/test_scoring.py
  - tests/test_scoring_cli.py
key_decisions:
  - D014
patterns_established:
  - Demand and premium remain separate score surfaces.
  - Premium stays demand-led and only gets a contextual price boost when the peer sample clears explicit support thresholds.
observability_surfaces:
  - `python -m vinted_radar.cli rankings --db <path> --kind demand --limit <n>`
  - `python -m vinted_radar.cli rankings --db <path> --kind premium --limit <n>`
  - `python -m vinted_radar.cli market-summary --db <path> --limit <n>`
  - `python -m vinted_radar.cli score --db <path> --listing-id <id>`
drill_down_paths:
  - .gsd/milestones/M001/slices/S04/tasks/T01-PLAN.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-17
---

# S04: Market Scores + Lightweight Contextualization

**Explainable demand and premium rankings plus segment-level market summaries built directly from the history and state surfaces.**

## What Happened

S04 added the first real market-reading layer on top of the history and cautious state work from S02/S03. The new scoring module computes two distinct listing-level scores: `demand`, which is anchored in current state, confidence, freshness, observation depth, and follow-up misses; and `premium`, which starts from demand and applies only a modest contextual price boost when the selected peer group is large enough to support a believable comparison.

Context selection is explicit and opportunistic. The scorer tries progressively broader peer tiers (`catalog_brand_condition`, `catalog_condition`, `catalog_brand`, `catalog`, `root_condition`, `root`) and only uses the first one that clears its support threshold. When no trustworthy peer set exists, the premium score falls back to a demand-led score without pretending to know whether the listing is contextually expensive.

The CLI now exposes `rankings`, `score`, and `market-summary`. Live verification against the repeated-run DB showed a coherent split: `demand` currently pushes one-miss `unavailable_non_conclusive` listings above ordinary active listings, while `premium` surfaces expensive active listings whose contextual price percentile is high enough to matter. Segment summaries also now show performing and rising sub-categories using tracked listing counts, average scores, recent arrivals, and scan deltas from the same evidence base.

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind demand --limit 10`
- `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind premium --limit 10`
- `python -m vinted_radar.cli market-summary --db data/vinted-radar-s02.db --limit 8`
- `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693`

## Requirements Advanced

- R005 — the demand ranking surface now exists and is explicitly grounded in sell-through and caution-aware evidence, not proxy popularity.
- R006 — the premium ranking now exists as a separate score that keeps demand primary and adds only a contextual price boost.
- R007 — lightweight contextualization now applies opportunistically with explicit support thresholds and a no-context fallback.
- R008 — a CLI-level market summary now reports performing and rising segments with supporting aggregates.
- R011 — missing context support remains explicit in score explanations instead of turning into fake precision.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The slice stayed on-demand rather than persisting score snapshots. Given the current CLI-first product surface, deriving scores directly from the latest history/state surfaces was simpler and kept the explanation payloads closer to the underlying evidence.

## Known Limitations

The market summary is still CLI-only, not the eventual dashboard surface. Current live data is also still shallow in some segments, so demand-heavy `unavailable_non_conclusive` listings can dominate rankings until multi-day cadence yields more sold/deleted evidence. Contextual price support is intentionally conservative, which means some listings get no premium boost yet.

## Follow-ups

- Build S05 on the `score_explanation`, `state_explanation`, and market-summary payloads instead of recomputing score logic in the UI.
- Revisit whether score snapshots need to be materialized once the dashboard and continuous loop exist.
- Consider whether rising-segment logic should incorporate longer windows once S06 creates multi-day runtime history.

## Files Created/Modified

- `vinted_radar/scoring.py` — listing scoring, context selection, and segment summary logic.
- `vinted_radar/cli.py` — ranking, score detail, and market-summary commands.
- `tests/test_scoring.py` — score and context behavior coverage.
- `tests/test_scoring_cli.py` — CLI JSON surface coverage.
- `README.md` — updated local entrypoints.

## Forward Intelligence

### What the next slice should know
- `score_explanation` is already shaped for UI drill-down; S05 should render it rather than translating opaque numbers.
- The premium score intentionally goes quiet when peer support is thin. That is a feature, not a missing-data bug.
- Segment summaries are currently catalog-path based and use scan deltas plus recent arrivals; they are adequate for S05, but not yet a long-window market trend model.

### What's fragile
- Context thresholds are heuristic and will likely need retuning once the collector sees more than two runs and more categories.
- On-demand score derivation is cheap enough now, but it may become an operational bottleneck once continuous mode and dashboard polling arrive.

### Authoritative diagnostics
- `python -m vinted_radar.cli score --db <path> --listing-id <id>` — fastest truthful listing-level score explanation.
- `python -m vinted_radar.cli rankings --db <path> --kind demand --limit <n>` — current demand ordering.
- `python -m vinted_radar.cli market-summary --db <path> --limit <n>` — current segment-level market read.

### What assumptions changed
- "Any available price context is better than no context." — false; thin peer groups create misleading premium boosts, so explicit no-context fallback is safer.
