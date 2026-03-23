---
estimated_steps: 4
estimated_files: 4
skills_used:
  - frontend-design
  - make-interfaces-feel-better
  - accessibility
  - agent-browser
  - test
  - review
---

# T02: Rebuild `/explorer` for scalable browsing on desktop and mobile

**Slice:** S04 — Full Explorer + Comparative Intelligence
**Milestone:** M002

## Description

Load `frontend-design`, `make-interfaces-feel-better`, `accessibility`, `agent-browser`, `test`, and `review` before coding. T01 gives the explorer a strong query backbone; this task turns it into a product surface. The explorer should feel like the main workspace for browsing a large tracked corpus, not an oversized table with filters bolted on.

## Steps

1. Refactor the explorer rendering in `vinted_radar/dashboard.py` around the T01 query contract: active-filter summary, comparison panels, paged results, and honest empty/support states.
2. Replace desktop-only result presentation with responsive list/card/table hybrids so the explorer remains usable at mobile widths.
3. Keep filter controls and comparison modules visibly tied to counts/support metadata so the user can tell what the current slice of the corpus actually represents.
4. Expand `tests/test_dashboard.py` and `tests/test_dashboard_cli.py` to assert explorer route behavior, query-state rendering, and comparison module visibility.

## Must-Haves

- [x] `/explorer` becomes a browse-and-compare workspace, not only a debug-shaped listing table.
- [x] Active filters, result counts, and comparison support levels remain visible in the rendered UI.
- [x] Mobile-width explorer interaction remains usable without collapsing into unreadable wide tables.

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8783`

## Observability Impact

- Signals added/changed: explorer route now renders active filter state, total matches, page metadata, comparison support cues, and clearer empty/fallback states.
- How a future agent inspects this: open `/explorer`, compare rendered state against `/api/explorer`, and rerun dashboard route tests.
- Failure state exposed: UI drift from the repository contract, hidden low-support caveats, or mobile-unusable result layouts become visible through route tests and browser verification.

## Inputs

- `vinted_radar/repository.py` — T01 SQL explorer/comparison contract consumed by the UI.
- `vinted_radar/dashboard.py` — current explorer HTML that needs to be rebuilt around the stronger contract.
- `tests/test_explorer_repository.py` — T01 payload expectations that the UI must honor.
- `tests/test_dashboard.py` — route regression harness for explorer rendering.

## Expected Output

- `vinted_radar/dashboard.py` — rebuilt explorer rendering with responsive browsing/comparison UX.
- `tests/test_dashboard.py` — route assertions for explorer filters, support cues, and result rendering.
- `tests/test_dashboard_cli.py` — command/output assertions aligned with the rebuilt explorer route.
- `README.md` — any necessary operator/user documentation updates for the richer explorer flow.
