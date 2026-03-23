---
id: T01
parent: S08
milestone: M002
provides:
  - Native API price bounds on discovery requests plus runtime CLI forwarding for `max_price`
key_files:
  - vinted_radar/services/discovery.py
  - vinted_radar/services/runtime.py
  - vinted_radar/cli.py
  - tests/test_discovery_service.py
key_decisions:
  - D031 — apply configured price bounds at the API boundary while retaining a local safety net before persistence
patterns_established:
  - Treat Vinted API price bounds as a throughput optimization, not as the only correctness guard
observability_surfaces:
  - catalog_scans.requested_url
  - runtime_cycles.config.max_price
  - python -m vinted_radar.cli runtime-status --db <db> --format json
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: Thread native API price bounds through discovery and runtime CLI

**Extended discovery so `price_from` / `price_to` are sent to Vinted's catalog API, threaded `max_price` through the shared runtime path, and kept the local price guard in front of persistence.**

## What Happened

The old path still built API URLs without any price window, then relied mostly on local filtering after the payload was already downloaded. T01 moved the bound earlier in the flow.

`DiscoveryOptions` now carries `max_price`, `_build_api_catalog_url()` adds `price_from` and `price_to` only when they are configured, and `_scan_catalog()` sends both values on every catalog-page request. I kept the existing client-side price check in place and extended it to reject cards above `max_price` too, so a loose upstream response still cannot slip through to `upsert_listing()`.

That new option then had to reach the real operator path. `RadarRuntimeOptions` now persists `max_price` in runtime config and forwards it into `DiscoveryOptions`, and `batch` / `continuous` both expose `--max-price` through the shared `_build_runtime_options()` seam. One stale discovery test was pinning the old min-price URL contract, so I updated that expectation instead of weakening the feature.

## Verification

Ran the targeted discovery/runtime/CLI regression suite and a direct Python contract check covering the API URL, runtime-option forwarding, and the local upper-bound safety net.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` | 0 | PASS | 1.51s |
| 2 | `python - <<'PY' ... _build_api_catalog_url(..., price_from=30.0, price_to=80.0) ... PY` | 0 | PASS | <1s |

## Diagnostics

Inspect `catalog_scans.requested_url` to confirm the API boundary actually received `price_from` / `price_to`. Inspect `runtime_cycles.config.max_price` or `python -m vinted_radar.cli runtime-status --db <db> --format json` to confirm `batch` / `continuous` preserved the configured upper bound.

## Deviations

none

## Known Issues

This task proves the request contract and local safety net, but it does not yet measure live long-run ban-rate improvement over multiple production cycles.

## Files Created/Modified

- `vinted_radar/services/discovery.py` — added native API price bounds, `max_price` support, and an upper-bound client-side safety check.
- `vinted_radar/services/runtime.py` — threaded `max_price` through runtime config and discovery forwarding.
- `vinted_radar/cli.py` — added `--max-price` to `batch` and `continuous` and passed it through shared runtime option construction.
- `tests/test_discovery_service.py` — updated the stale min-price URL expectation to match the new API-bound contract.
