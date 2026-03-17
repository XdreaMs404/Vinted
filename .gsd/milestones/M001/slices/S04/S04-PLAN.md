# S04: Market Scores + Lightweight Contextualization

**Goal:** Compute explainable “demande pure” and “premium” rankings plus a market summary of performing and rising segments, all grounded in observation history, cautious state outputs, and lightweight contextual price context where sample support is strong enough.
**Demo:** Run `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind demand --limit 10`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind premium --limit 10`, `python -m vinted_radar.cli market-summary --db data/vinted-radar-s02.db --limit 8`, and `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id <id>` to inspect ranking outputs and explanation payloads.

## Must-Haves

- Produce separate explainable listing rankings for `demand` and `premium` rather than collapsing them into one score.
- Base scoring on the existing history/state surfaces, with explicit factor breakdowns and cautious use of inferred signals.
- Apply contextual price comparison only when the peer sample is strong enough, and make the chosen context visible.
- Expose a market-summary surface that highlights performing and rising sub-categories with supporting evidence counts.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind demand --limit 10`
- `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind premium --limit 10`
- `python -m vinted_radar.cli market-summary --db data/vinted-radar-s02.db --limit 8`
- `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693`

## Observability / Diagnostics

- Runtime signals: per-listing score factors, selected context labels, peer sample sizes, segment demand/premium aggregates, and rising-segment deltas.
- Inspection surfaces: `rankings`, `score`, `market-summary`, plus JSON output for machine-readable explanations.
- Failure visibility: missing price/context support, thin peer samples, and low-confidence state inputs remain explicit in score explanations instead of being silently averaged away.
- Redaction constraints: continue using only public normalized fields and derived signals.

## Integration Closure

- Upstream surfaces consumed: `listing_observations`, state evaluations from S03, freshness buckets, follow-up misses, and primary-catalog scan history.
- New wiring introduced in this slice: state evaluation → explainable listing scoring → segment aggregates / rising summary → CLI inspection commands.
- What remains before the milestone is truly usable end-to-end: dashboard surfaces and continuous runtime orchestration.

## Tasks

- [x] **T01: Implement explainable listing scoring and contextual price baselines** `est:1h15m`
  - Why: S04 depends on ranking individual listings by real demand and premium behavior with visible factor breakdowns.
  - Files: `vinted_radar/scoring.py`, `tests/test_scoring.py`, `vinted_radar/state_machine.py`
  - Do: Compute demand and premium scores from state/history evidence, choose the richest supported peer context, and expose explanation payloads including context sample size and factor contributions.
  - Verify: `python -m pytest tests/test_scoring.py`
  - Done when: demand and premium scores are separate, explained, and context-aware only when support thresholds are met.
- [x] **T02: Add market summary and ranking CLI surfaces** `est:1h`
  - Why: The slice only becomes usable when the operator can inspect ranked listings and segment summaries from the real CLI entrypoint.
  - Files: `vinted_radar/cli.py`, `tests/test_scoring_cli.py`, `README.md`
  - Do: Add `rankings`, `score`, and `market-summary` commands with both table and JSON output and safe terminal rendering.
  - Verify: `python -m pytest tests/test_scoring_cli.py`
  - Done when: the CLI exposes listing rankings, per-listing score detail, and segment summaries with explanation data.
- [x] **T03: Verify live scoring outputs and persist slice handoff context** `est:45m`
  - Why: S04 needs proof that the scoring surfaces work against the live repeated-run DB, not just crafted test fixtures.
  - Files: `.gsd/milestones/M001/slices/S04/tasks/T01-PLAN.md`, `.gsd/milestones/M001/slices/S04/S04-PLAN.md`, `.gsd/KNOWLEDGE.md`
  - Do: Run the live ranking and market-summary commands on the current DB, inspect a score detail payload, and record any scoring/context lessons learned that S05 will depend on.
  - Verify: the S04 live verification commands from this plan.
  - Done when: real outputs are generated and the durable handoff explains how S05 should consume them.

## Files Likely Touched

- `vinted_radar/scoring.py`
- `vinted_radar/cli.py`
- `tests/test_scoring.py`
- `tests/test_scoring_cli.py`
- `README.md`
