# S04: Transport Optimizer + Empirical Concurrency/Session Tuning

**Goal:** Turn transport tuning into a measurable subsystem that can select the best proxy/session/concurrency recipe per market on the real VPS.
**Demo:** After this: After this: operators can benchmark proxy/session/concurrency profiles per market on the VPS and the system can explain which transport recipe wins on real useful yield rather than only on request speed.

## Tasks
- [ ] **T01: Add structured transport telemetry to the HTTP client** — Why: Current proxy tuning is partly observable but not rich enough to explain tradeoffs across session and concurrency strategies.
Do:
- Extend the HTTP client with structured telemetry for route selection, warm-up cost, cooldowns, retries, challenge suspects, and session reuse.
- Keep logs secret-safe and bounded; this is a diagnostic contract, not a firehose.
- Expose telemetry in a way the benchmark scorecard can consume directly.
Done when:
- Transport tests can assert on meaningful route/session telemetry without scraping free-form logs.
  - Estimate: 1.5h
  - Files: vinted_radar/http.py, vinted_radar/proxies.py, tests/test_http.py, tests/test_transport_benchmark.py
  - Verify: python -m pytest tests/test_http.py tests/test_proxy_config.py tests/test_transport_benchmark.py -q
- [ ] **T02: Teach the benchmark harness to compare transport recipes** — Why: The benchmark harness needs first-class transport recipe comparisons, not bespoke one-off scripts per knob.
Do:
- Add benchmark recipe definitions for concurrency, warm-up policy, retry/cooldown behavior, and session stickiness.
- Teach the scorecard to rank transport candidates on net useful yield, not raw request count alone.
- Keep recipe definitions explicit and serializable so winners are reproducible.
Done when:
- Benchmark tests can compare multiple transport recipes and identify a deterministic winner from fixture data.
  - Estimate: 1.5h
  - Files: vinted_radar/services/acquisition_benchmark.py, tests/test_transport_benchmark.py, tests/test_acquisition_benchmark.py
  - Verify: python -m pytest tests/test_transport_benchmark.py tests/test_acquisition_benchmark.py -q
- [ ] **T03: Wire benchmark-selected transport profiles into runtime and CLI** — Why: Once a winner exists, runtime commands need a safe way to use it while still allowing explicit overrides during experiments.
Do:
- Add transport profile selection to CLI/runtime configuration and artifact rendering.
- Make the chosen recipe visible in runtime/benchmark outputs and keep overrides explicit for auditability.
- Preserve safe defaults when no winner has been chosen yet.
Done when:
- Runtime tests prove recommended profiles and explicit overrides both work and remain inspectable.
  - Estimate: 1h
  - Files: vinted_radar/cli.py, vinted_radar/services/runtime.py, tests/test_runtime_cli.py, tests/test_runtime_service.py
  - Verify: python -m pytest tests/test_runtime_cli.py tests/test_runtime_service.py -q
- [ ] **T04: Run the VPS transport matrix and record the winner** — Why: The slice is only complete when the measured transport winner comes from the real VPS, not from local fixture tests.
Do:
- Run a VPS matrix across the main candidate transport recipes for FR and any active extra market.
- Persist artifacts comparing at least concurrency and session behavior variants.
- Select and document the winning recipe to be consumed by later slices.
Done when:
- The repo contains a VPS-backed transport winner artifact that later slices can reference mechanically.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile transport-matrix --duration-minutes 120 --output .gsd/milestones/M003/benchmarks/transport-matrix.json --markdown .gsd/milestones/M003/benchmarks/transport-matrix.md
