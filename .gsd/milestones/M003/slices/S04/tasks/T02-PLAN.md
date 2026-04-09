---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T02: Teach the benchmark harness to compare transport recipes

Why: The benchmark harness needs first-class transport recipe comparisons, not bespoke one-off scripts per knob.
Do:
- Add benchmark recipe definitions for concurrency, warm-up policy, retry/cooldown behavior, and session stickiness.
- Teach the scorecard to rank transport candidates on net useful yield, not raw request count alone.
- Keep recipe definitions explicit and serializable so winners are reproducible.
Done when:
- Benchmark tests can compare multiple transport recipes and identify a deterministic winner from fixture data.

## Inputs

- `vinted_radar/services/acquisition_benchmark.py`
- `tests/test_acquisition_benchmark.py`

## Expected Output

- `transport recipe comparison support`
- `transport winner ranking logic`

## Verification

python -m pytest tests/test_transport_benchmark.py tests/test_acquisition_benchmark.py -q
