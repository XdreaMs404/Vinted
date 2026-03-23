---
estimated_steps: 4
estimated_files: 3
skills_used:
  - frontend-design
  - make-interfaces-feel-better
  - accessibility
  - agent-browser
  - test
  - review
---

# T02: Rebuild the HTML listing detail as a narrative-first page with progressive proof

**Slice:** S05 — Listing Detail Narrative + Progressive Proof
**Milestone:** M002

## Description

Load `frontend-design`, `make-interfaces-feel-better`, `accessibility`, `agent-browser`, `test`, and `review` before coding. T01 gives the route a better contract; this task makes the route feel like the product. The page should answer the broad-user question first, then let power users unfold the technical proof on demand without losing the shared shell or the explorer round-trip.

## Steps

1. Rework the detail hero, hierarchy, and primary sections so the page leads with why the listing matters now and what the radar currently believes.
2. Group seller, engagement, price, timing, and market-context cues into readable cards instead of one proof-dense block.
3. Move technical state, score, transition, and observation evidence into accessible progressive-disclosure panels that keep the proof available but secondary.
4. Expand route tests to lock in the new narrative-first detail structure and key progressive-proof affordances.

## Must-Haves

- [x] The first visible detail section explains the listing in French product language rather than debugger vocabulary.
- [x] The route still exposes explorer-context/back-to-results actions and canonical/JSON drill-down links.
- [x] Proof remains accessible through progressive disclosure instead of disappearing behind marketing copy.

## Verification

- `python -m pytest tests/test_dashboard.py`
- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`

## Inputs

- `vinted_radar/dashboard.py` — shared shell plus current proof-first detail page.
- `tests/test_dashboard.py` — detail-route assertions that should expand to structure/progressive-proof coverage.
- `README.md` — current route description that may need wording updates after the new hierarchy lands.

## Expected Output

- `vinted_radar/dashboard.py` — rebuilt narrative-first HTML detail route with progressive-proof sections.
- `tests/test_dashboard.py` — structure assertions for the richer detail UI and preserved route actions.
- `README.md` — any user-facing wording updates needed to describe the richer detail route.
