---
id: T02
parent: S09
milestone: M002
provides:
  - Route-local sync/async transport state so discovery can use multiple proxy routes instead of retry-only one-hot rotation
key_files:
  - vinted_radar/http.py
  - tests/test_http.py
  - tests/test_discovery_service.py
key_decisions:
  - Treat the proxy pool as route-local transport state with per-route warm-up, delay tracking, and cooldown instead of a single active session that rotates only on failure.
patterns_established:
  - Large proxy pools only provide throughput when request delay, session warm-up, and route degradation are tracked per route rather than globally.
observability_surfaces:
  - vinted_radar.http logs with masked route labels
  - tests/test_http.py
  - tests/test_discovery_service.py
duration: 1 session
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T02: Rebuild the HTTP transport around real multi-route proxy throughput

**Replaced retry-only proxy rotation with route-local sync/async session state so concurrent discovery can actually spread across the pool.**

## What Happened

The weak technical seam in S09 was `vinted_radar/http.py`. The file already knew how to rotate to a new proxy after a retryable failure, but that meant a large pool barely mattered during healthy runs: the collector still behaved like one active proxy plus a standby list.

I rewrote that transport around route-local state. Each direct/proxy lane now has its own warm-up state, request-delay timestamps, rebuild flags, cooldown timer, and masked label. Async route selection now reserves whichever route is ready soonest with the lowest in-flight pressure, so concurrent discovery requests can spread across multiple warmed routes instead of pinning the full run to one lane. Sync requests keep the same route-local posture, so sequential probe traffic no longer depends on a single hot session either.

I also removed an old observability leak while I was there: warm-up logs no longer print cookie fragments. The transport now logs only masked route labels.

## Verification

Ran focused transport/discovery regressions proving async spread and retry-on-another-route behavior.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_http.py tests/test_discovery_service.py -q` | 0 | PASS | 0.42s |

## Diagnostics

`tests/test_http.py` is now the fastest regression alarm for future transport edits: it proves async requests can land on multiple proxy routes and that retryable failures move to another route. At runtime, `vinted_radar.http` logs masked route labels plus degradation/cooldown events instead of leaking proxy secrets.

## Deviations

none

## Known Issues

T02 gives the pool real throughput, but it does not by itself tell the operator whether the current pool is healthy or diverse enough before a run. That operator proof surface landed in T03.

## Files Created/Modified

- `vinted_radar/http.py` — replaced one-hot proxy rotation with route-local sync/async transport state, cooldowns, and masked logs.
- `tests/test_http.py` — added transport-level coverage for async route spread and retry-on-another-route behavior.
- `tests/test_discovery_service.py` — kept the discovery contract covered while the transport implementation changed underneath.