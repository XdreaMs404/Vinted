---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: Add structured transport telemetry to the HTTP client

Why: Current proxy tuning is partly observable but not rich enough to explain tradeoffs across session and concurrency strategies.
Do:
- Extend the HTTP client with structured telemetry for route selection, warm-up cost, cooldowns, retries, challenge suspects, and session reuse.
- Keep logs secret-safe and bounded; this is a diagnostic contract, not a firehose.
- Expose telemetry in a way the benchmark scorecard can consume directly.
Done when:
- Transport tests can assert on meaningful route/session telemetry without scraping free-form logs.

## Inputs

- `vinted_radar/http.py`
- `tests/test_http.py`

## Expected Output

- `route/session telemetry contract`
- `tests/test_transport_benchmark.py`

## Verification

python -m pytest tests/test_http.py tests/test_proxy_config.py tests/test_transport_benchmark.py -q
