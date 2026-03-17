---
id: S03
parent: M001
milestone: M001
provides:
  - Cautious current-state evaluation over history plus direct public item-page probes
  - Persisted `item_page_probes` diagnostics
  - CLI state refresh, summary, and per-listing inspection surfaces
requires:
  - slice: S02
    provides: `listing_observations`, freshness history, revisit candidates, and repeated-run SQLite state
affects:
  - S04
  - S05
  - S06
key_files:
  - vinted_radar/parsers/item_page.py
  - vinted_radar/state_machine.py
  - vinted_radar/services/state_refresh.py
  - vinted_radar/repository.py
  - vinted_radar/cli.py
key_decisions:
  - D012
  - D013
patterns_established:
  - Direct item-page probe evidence outranks history when it yields a distinct public state signal.
  - Current listing state is derived, not source-of-truth persisted business state.
observability_surfaces:
  - `python -m vinted_radar.cli state-refresh --db <path> --limit <n>`
  - `python -m vinted_radar.cli state-summary --db <path>`
  - `python -m vinted_radar.cli state --db <path> --listing-id <id>`
  - SQLite table: `item_page_probes`
drill_down_paths:
  - .gsd/milestones/M001/slices/S03/tasks/T01-PLAN.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-17
---

# S03: Prudent State Machine + Confidence Surfaces

**A cautious state engine that combines observation history plus public item-page probes into current listing states with confidence, basis, and reasons.**

## What Happened

S03 added the first real current-state layer on top of the observation history built in S02. Public item-page probes are now stored in `item_page_probes`, and the parser extracts direct buy-state flags from escaped script content on live Vinted item pages without needing browser automation.

The state engine combines three evidence classes: latest observation history, follow-up misses from later successful primary-catalog scans, and the latest direct item-page probe. Distinct direct signals take precedence: 404/410 map to `deleted`, open buy-state flags map to observed `active`, closed buy-state flags map to observed `sold`, and reachable-but-ambiguous item pages map to observed `unavailable_non_conclusive`. When direct page evidence is absent or inconclusive, the engine falls back to cautious history-based inference, producing `sold_probable`, `unavailable_non_conclusive`, or `unknown` rather than overclaiming.

The CLI now exposes `state-refresh`, `state-summary`, and `state`. Live verification showed the state layer working on real repeated-run data: aggregate state counts render from the shared SQLite DB, a repeatedly observed listing stays `active` from catalog evidence, and a first-pass-only listing can be upgraded to observed `active` once its item page probe confirms `can_buy=true`.

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --limit 10 --request-delay 0.0`
- `python -m vinted_radar.cli state-summary --db data/vinted-radar-s02.db`
- `python -m vinted_radar.cli state --db data/vinted-radar-s02.db --listing-id 4176710128`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --listing-id 8305280693 --limit 1 --request-delay 0.0`
- `python -m vinted_radar.cli state --db data/vinted-radar-s02.db --listing-id 8305280693`

## Requirements Advanced

- R003 — listings now expose a cautious current state taxonomy with observed versus inferred basis, confidence, and reasons.
- R004 — confidence and basis visibility now exist at the CLI inspection layer through aggregate and listing-detail state surfaces.
- R011 — item-page probe failures and unknown page shapes remain visible instead of collapsing into false certainty.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The live parser had to be broadened beyond the fixture shape because real item pages embed the buy-state block as escaped JSON text. The parser now normalizes escaped quotes before matching while still degrading cleanly to `unknown` when the shape is unsupported.

## Known Limitations

The current state layer is still CLI-only, not part of the eventual dashboard. `sold_observed` and `deleted` are supported by the engine and fixtures, but live proof still depends mainly on active and inconclusive listings because disappearance examples are opportunistic in public data. The engine stores probe diagnostics, but it does not yet persist historical state snapshots over time.

## Follow-ups

- Build S04 directly on `state_code`, `basis_kind`, `confidence_label`, freshness, and history rather than bypassing the state layer.
- Decide whether `item_page_probes` should later feed scheduled revisit policy or remain an on-demand enrichment step.
- Revisit whether state snapshots need their own history table once the dashboard and scoring layers consume them.

## Files Created/Modified

- `vinted_radar/parsers/item_page.py` — public item-page outcome parser.
- `vinted_radar/state_machine.py` — cautious current-state evaluation and aggregate summaries.
- `vinted_radar/services/state_refresh.py` — bounded probe refresh workflow.
- `vinted_radar/repository.py` — probe persistence and state input queries.
- `vinted_radar/db.py` — `item_page_probes` schema.
- `vinted_radar/cli.py` — state refresh, summary, and per-listing detail commands.
- `tests/test_item_page_parser.py` — parser coverage.
- `tests/test_state_machine.py` — all state taxonomy branches.
- `tests/test_state_cli.py` — CLI JSON summary/detail proof.
- `README.md` — updated local entrypoints.

## Forward Intelligence

### What the next slice should know
- `state_code`, `basis_kind`, and `confidence_label` are now cheap to derive on demand from repository state; S04 should consume them rather than rebuilding disappearance logic from raw scans.
- Live item-page probes can materially upgrade first-pass-only listings from inferred ambiguity to observed `active`, which is useful when rankings need stronger evidence weighting.
- The engine is deliberately conservative: repeated misses are required before `sold_probable`, and unsupported probe shapes stay `unknown`.

### What's fragile
- Item-page parsing still depends on the current escaped script layout containing `can_buy`, `is_closed`, `is_hidden`, and `is_reserved` together — if Vinted moves or renames those fields, probe outcomes will fall back to `unknown`.
- State detail is computed live from the latest persisted history and probe rows; there is no frozen per-run state snapshot yet.

### Authoritative diagnostics
- `python -m vinted_radar.cli state-summary --db <path>` — fastest truthful aggregate state surface.
- `python -m vinted_radar.cli state --db <path> --listing-id <id>` — canonical listing-level explanation surface.
- SQLite `item_page_probes` — authoritative direct page-evidence log.

### What assumptions changed
- "Fixture-shaped item-page parsing is enough for live probes." — false; real public item pages escape the signal block, so the parser must normalize the text before matching.
