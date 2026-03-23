---
estimated_steps: 4
estimated_files: 4
skills_used:
  - frontend-design
  - agent-browser
  - test
  - review
---

# T03: Wire overview drill-down and context-preserving listing navigation

**Slice:** S04 — Full Explorer + Comparative Intelligence
**Milestone:** M002

## Description

Load `frontend-design`, `agent-browser`, `test`, and `review` before coding. The slice only closes when overview, explorer, and detail form one analytical loop. This task makes overview modules open the explorer in the right state and keeps enough context alive when the user drills into a listing and returns.

## Steps

1. Convert overview summary and comparison modules into deep links that map cleanly onto the explorer filter/query contract from T01.
2. Preserve active explorer lens/query/page context when linking from explorer results into `/listings/<id>` and when offering a way back.
3. Surface the current analytical lens inside listing navigation so the user understands why a given listing is being viewed in context.
4. Expand dashboard route tests to cover overview→explorer and explorer→detail transitions without losing context.

## Must-Haves

- [x] Overview modules land on the correct explorer state instead of generic unfiltered browsing.
- [x] Listing drill-down preserves enough explorer context for a truthful “back to results” flow.
- [x] The active analytical lens remains visible when moving between overview, explorer, and detail.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m pytest tests/test_dashboard.py -k explorer`

## Inputs

- `vinted_radar/dashboard.py` — T02 explorer UI that now needs deep-link and context-preserving navigation.
- `vinted_radar/repository.py` — T01 filter/query contract that overview deep links must target correctly.
- `tests/test_dashboard.py` — route coverage that should expand to overview/explorer/detail transitions.
- `tests/test_dashboard_cli.py` — route/output checks that should stay aligned with the navigable product flow.

## Expected Output

- `vinted_radar/dashboard.py` — deep-link and context-preserving navigation across overview, explorer, and detail.
- `vinted_radar/repository.py` — any small contract additions needed for explorer/detail context handoff.
- `tests/test_dashboard.py` — transition coverage for overview→explorer and explorer→detail flow.
- `tests/test_dashboard_cli.py` — any CLI-facing route expectation updates caused by the integrated navigation flow.
