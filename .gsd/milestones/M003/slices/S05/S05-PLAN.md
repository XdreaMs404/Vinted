# S05: Adaptive Frontier Depth + Cross-Market Acquisition Strategies

**Goal:** Exploit the new lane runtime, market partitioning, and transport winners to push beyond fixed page-1 FR scanning into adaptive depth and cross-market frontier allocation.
**Demo:** After this: After this: FR and selected extra markets can run adaptive frontier plans that allocate page depth and lane budget where marginal new-listing yield is actually highest, with benchmark proof that the strategy beats the old fixed page-1 loop.

## Tasks
- [ ] **T01: Add yield-driven frontier planning primitives** — Why: The system needs a planner that decides where extra requests are worth spending, not a blunt global page limit.
Do:
- Add per-page, per-market, and per-lane yield telemetry derived from stored runs and benchmark artifacts.
- Implement a planner that can score frontier candidates using marginal new-listing yield, duplicate pressure, challenge risk, and freshness goals.
- Keep the planner explainable enough for report rendering and debugging.
Done when:
- Planner tests can rank candidate pages/markets from fixture histories and explain the top choices.
  - Estimate: 1.5h
  - Files: vinted_radar/services/frontier_planner.py, vinted_radar/repository.py, tests/test_frontier_planner.py
  - Verify: python -m pytest tests/test_frontier_planner.py tests/test_discovery_service.py -q
- [ ] **T02: Wire adaptive frontier strategies into discovery and runtime** — Why: The planner only matters if runtime and discovery can consume it to decide depth and lane budgets dynamically.
Do:
- Wire adaptive page-budget allocation and lane strategies into discovery/runtime.
- Support distinct frontier, expansion, and optional backfill strategies while preserving per-lane truth.
- Keep a deterministic fallback profile for debugging and baseline comparison.
Done when:
- Runtime/discovery tests prove adaptive and fixed strategies can both execute and remain inspectable.
  - Estimate: 2h
  - Files: vinted_radar/services/discovery.py, vinted_radar/services/runtime.py, vinted_radar/cli.py, tests/test_discovery_service.py, tests/test_runtime_service.py
  - Verify: python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q
- [ ] **T03: Benchmark FR fixed-depth versus adaptive frontier on the VPS** — Why: The first hard proof target is beating the current FR loop, because that baseline is already measured and operationally relevant.
Do:
- Run a VPS benchmark comparing the old FR page-1 loop, one or more fixed deeper profiles, and the adaptive FR planner.
- Persist artifacts that show the winner on net useful yield, not only raw request volume.
- Keep the comparison apples-to-apples on duration and benchmark methodology.
Done when:
- The milestone has a real FR benchmark artifact proving whether adaptive depth beats the current baseline.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile fr-frontier-comparison --duration-minutes 180 --output .gsd/milestones/M003/benchmarks/fr-frontier-comparison.json --markdown .gsd/milestones/M003/benchmarks/fr-frontier-comparison.md
- [ ] **T04: Select the cross-market production-candidate acquisition strategy** — Why: The user wants the best system possible, which may require combining FR optimization with additional markets where the marginal yield is strong.
Do:
- Run a cross-market additive benchmark using the adaptive planner and the transport winners from S04.
- Compare the chosen multi-market candidate against the FR-only winner on discoveries, duplicates, challenge rate, and resource/storage cost.
- Select the production-candidate strategy that later slices must optimize for storage and rollout.
Done when:
- A benchmark artifact names the current best acquisition strategy across FR and extra-market options.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile cross-market-frontier-winner --duration-minutes 180 --output .gsd/milestones/M003/benchmarks/cross-market-frontier-winner.json --markdown .gsd/milestones/M003/benchmarks/cross-market-frontier-winner.md
