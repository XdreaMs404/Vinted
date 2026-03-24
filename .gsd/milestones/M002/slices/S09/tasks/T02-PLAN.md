---
estimated_steps: 5
estimated_files: 5
skills_used:
  - code-optimizer
  - test
---

# T02: Rebuild the HTTP transport around real multi-route proxy throughput

**Slice:** S09 — High-Throughput Proxy Pool + Webshare Acquisition Operator Flow
**Milestone:** M002

## Description

The current transport treats the proxy list as a retry-only fallback. This task turns it into a real throughput primitive with per-route sessions, warm-up, delay tracking, and async route selection across the pool.

## Steps

1. Replace the single active proxy/session model with per-route transport state for sync and async usage.
2. Keep warm-up, retry, and request-delay behavior route-local instead of global.
3. Add cooldown/rebuild handling for degraded routes so challenge or network failures stop poisoning the hot path.
4. Preserve backward compatibility for direct/no-proxy mode and sequential state-refresh probes.
5. Add focused tests proving the async transport can spread concurrent requests across more than one proxy route.

## Must-Haves

- [ ] Async discovery no longer pins all requests to one active proxy until failure.
- [ ] Retryable HTTP/network failures can disable/rebuild only the affected route instead of resetting the whole pool.
- [ ] The non-proxy path still works.

## Verification

- `python -m pytest tests/test_http.py tests/test_discovery_service.py -q`

## Observability Impact

- Signals added/changed: route-local retry/cooldown logging and transport selection behavior.
- How a future agent inspects this: `tests/test_http.py`, transport logs, and `proxy-preflight` once T03 lands.
- Failure state exposed: degraded proxies stop silently dragging the whole async acquisition path and become isolatable as route-level failures.

## Inputs

- `vinted_radar/http.py` — current warm-up/retry transport.
- `vinted_radar/services/discovery.py` — async discovery concurrency contract.
- `vinted_radar/services/state_refresh.py` — sync item-page probe path.

## Expected Output

- `vinted_radar/http.py` — multi-route proxy scheduling and cooldown-aware transport state.
- `vinted_radar/services/discovery.py` — any discovery-side integration needed for the new transport behavior.
- `vinted_radar/services/state_refresh.py` — compatibility with the new route-local sync path.
- `tests/test_http.py` — transport-level concurrency and retry/cooldown regressions.
- `tests/test_discovery_service.py` — discovery compatibility coverage.
