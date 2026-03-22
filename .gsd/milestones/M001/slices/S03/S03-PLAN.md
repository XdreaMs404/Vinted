# S03: Prudent State Machine + Confidence Surfaces

**Goal:** Derive cautious, traceable listing states from observation history, follow-up misses, and optional item-page probes so each tracked listing exposes a current state, confidence, and explicit evidence basis.
**Demo:** Refresh state evidence on a repeated-run database with `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --limit 10`, then inspect `python -m vinted_radar.cli state-summary --db data/vinted-radar-s02.db` and `python -m vinted_radar.cli state --db data/vinted-radar-s02.db --listing-id <id>` to see active / sold probable / unavailable non-conclusive / deleted / unknown surfaces with confidence and reasons.

## Must-Haves

- Classify listings into a cautious state model covering `active`, `sold_observed`, `sold_probable`, `unavailable_non_conclusive`, `deleted`, and `unknown`.
- Keep observed versus inferred evidence explicit, with human-readable reasons and confidence labels.
- Persist item-page probe diagnostics so distinct deletion or active-page evidence remains inspectable after execution.
- Expose both aggregate and per-listing state surfaces through the CLI.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `python -m pytest`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --limit 10`
- `python -m vinted_radar.cli state-summary --db data/vinted-radar-s02.db`
- `python -m vinted_radar.cli state --db data/vinted-radar-s02.db --listing-id 4176710128`

## Observability / Diagnostics

- Runtime signals: persisted item-page probes, derived current listing state, confidence score/label, basis kind, and explanation payload.
- Inspection surfaces: `state-refresh`, `state-summary`, `state --listing-id <id>`, plus SQLite tables `item_page_probes` and the history tables from S02.
- Failure visibility: probe HTTP failures, page-shape parse failures, and unresolved unknown states stay visible rather than collapsing into false certainty.
- Redaction constraints: continue storing only public page-level diagnostic fragments and normalized public fields.

## Integration Closure

- Upstream surfaces consumed: `listing_observations`, `listing_discoveries`, `catalog_scans`, freshness/history queries, canonical listing URLs.
- New wiring introduced in this slice: history summary → optional item-page probe → cautious state engine → CLI summary/detail surfaces.
- What remains before the milestone is truly usable end-to-end: market scoring, dashboard surfaces, and continuous/runtime orchestration.

## Tasks

- [ ] **T01: Add item-page probe persistence and parser contracts** `est:1h`
  - Why: S03 needs direct public-page evidence for distinct deletion and observed active/sold signals, and those probes must stay inspectable.
  - Files: `vinted_radar/db.py`, `vinted_radar/repository.py`, `vinted_radar/parsers/item_page.py`, `tests/test_item_page_parser.py`
  - Do: Add probe persistence, implement item-page outcome parsing for active/sold/unavailable/deleted/unknown signals, and cover the parser with explicit fixtures.
  - Verify: `python -m pytest tests/test_item_page_parser.py`
  - Done when: probe rows persist and parser contracts cover the supported outcome shapes plus a 404 path.
- [ ] **T02: Implement the cautious state engine on top of history and probes** `est:1h15m`
  - Why: The slice exists to turn history and probe evidence into a prudent current-state surface with confidence and reasons.
  - Files: `vinted_radar/state_machine.py`, `vinted_radar/repository.py`, `tests/test_state_machine.py`
  - Do: Combine latest observations, follow-up misses, freshness, and latest probe evidence into the S03 state taxonomy with explicit basis kind and confidence labels.
  - Verify: `python -m pytest tests/test_state_machine.py`
  - Done when: active, sold observed/probable, unavailable non-conclusive, deleted, and unknown cases are all covered by tests with traceable explanations.
- [ ] **T03: Expose state refresh and inspection CLI surfaces** `est:1h`
  - Why: S03 is only useful once the operator can refresh probes and inspect current state summaries through the real entrypoints.
  - Files: `vinted_radar/services/state_refresh.py`, `vinted_radar/cli.py`, `tests/test_state_cli.py`, `README.md`
  - Do: Add state-refresh, state-summary, and state detail commands; probe a bounded candidate set; and make live CLI output safe on real terminal encodings.
  - Verify: `python -m pytest tests/test_state_cli.py` and the S03 live verification commands from this plan.
  - Done when: a repeated-run DB can be refreshed and then inspected at both aggregate and listing-detail levels.

## Files Likely Touched

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/parsers/item_page.py`
- `vinted_radar/state_machine.py`
- `vinted_radar/services/state_refresh.py`
- `vinted_radar/cli.py`
- `tests/test_item_page_parser.py`
- `tests/test_state_machine.py`
- `tests/test_state_cli.py`
- `README.md`
