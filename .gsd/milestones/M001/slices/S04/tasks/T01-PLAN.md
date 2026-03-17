---
estimated_steps: 6
estimated_files: 3
---

# T01: Implement explainable listing scoring and contextual price baselines

**Slice:** S04 — Market Scores + Lightweight Contextualization
**Milestone:** M001

## Description

Build the explainable listing-level scoring layer that ranks demand and premium behavior from the state/history evidence already shipped in S02/S03.

## Steps

1. Define the factor model for demand score using state, confidence, freshness, follow-up misses, and repeat observations.
2. Define the premium score so demand stays primary and price acts as a contextual amplifier instead of the dominant driver.
3. Build peer-context selection with explicit minimum support thresholds.
4. Compute contextual price percentile / price-band information only when the selected context is trustworthy.
5. Return a full explanation payload per listing so later UI work can drill into the score basis.
6. Cover the listing-level scoring rules with direct tests before wiring CLI output.

## Must-Haves

- [x] Demand and premium scores are separate and explained.
- [x] Context selection is explicit and support-threshold based.
- [x] Missing peer support degrades gracefully instead of faking contextual precision.

## Verification

- `python -m pytest tests/test_scoring.py`
- `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693`

## Observability Impact

- Signals added/changed: score factor payloads, context labels, peer sample sizes, price percentile / band surfaces.
- How a future agent inspects this: `score --listing-id <id>` or `rankings --format json`.
- Failure state exposed: unsupported context and missing price data remain explicit in the explanation payload.

## Inputs

- `vinted_radar/state_machine.py` — cautious current-state outputs and confidence surfaces.
- `vinted_radar/repository.py` — history, freshness, and primary-catalog scan context.

## Expected Output

- `vinted_radar/scoring.py` — listing and segment scoring logic.
- `tests/test_scoring.py` — unit coverage for score and context behavior.
