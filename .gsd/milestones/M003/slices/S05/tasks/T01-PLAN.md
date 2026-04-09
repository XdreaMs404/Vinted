---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T01: Add yield-driven frontier planning primitives

Why: The system needs a planner that decides where extra requests are worth spending, not a blunt global page limit.
Do:
- Add per-page, per-market, and per-lane yield telemetry derived from stored runs and benchmark artifacts.
- Implement a planner that can score frontier candidates using marginal new-listing yield, duplicate pressure, challenge risk, and freshness goals.
- Keep the planner explainable enough for report rendering and debugging.
Done when:
- Planner tests can rank candidate pages/markets from fixture histories and explain the top choices.

## Inputs

- `vinted_radar/repository.py`
- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json`

## Expected Output

- `frontier planner service`
- `tests/test_frontier_planner.py`

## Verification

python -m pytest tests/test_frontier_planner.py tests/test_discovery_service.py -q
