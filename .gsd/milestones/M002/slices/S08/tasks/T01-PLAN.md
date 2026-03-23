---
estimated_steps: 4
estimated_files: 4
skills_used:
  - test
---

# T01: Thread native API price bounds through discovery and runtime CLI

**Slice:** S08 — Native API Price Bounds for Discovery
**Milestone:** M002

## Description

Thread `max_price` through the runtime path, push `price_from` / `price_to` into the API URL builder, and keep the client-side price guard in place so the new server-side filtering reduces HTTP volume without weakening persistence safety.

## Steps

1. Extend discovery options and API URL construction to support `price_from` and `price_to` query params.
2. Preserve local price filtering before `upsert_listing`, including the new upper bound as a safety net.
3. Thread `max_price` through runtime options and the `batch` / `continuous` CLI entrypoints.
4. Refresh the stale discovery expectation that pinned the old URL contract.

## Must-Haves

- [ ] `_build_api_catalog_url()` emits `price_from` / `price_to` only when their values are greater than zero.
- [ ] `batch` and `continuous` accept `--max-price` and persist it through runtime config into discovery.
- [ ] Local filtering still blocks out-of-range cards before persistence even if the API returns them.

## Verification

- `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q`
- `python - <<'PY' ... _build_api_catalog_url(..., price_from=30.0, price_to=80.0) ... PY`

## Observability Impact

- Signals added/changed: `runtime_cycles.config.max_price`, API `requested_url` entries containing `price_from` / `price_to`.
- How a future agent inspects this: inspect `catalog_scans.requested_url` and `python -m vinted_radar.cli runtime-status --db <db> --format json`.
- Failure state exposed: missing API bounds are visible in persisted URLs/config rather than only through runtime behavior.

## Inputs

- `vinted_radar/services/discovery.py` — current API URL builder and client-side listing filter.
- `vinted_radar/services/runtime.py` — runtime option forwarding into discovery.
- `vinted_radar/cli.py` — `batch` / `continuous` option plumbing.
- `tests/test_discovery_service.py` — stale expectation pinned to the pre-`price_from` URL.

## Expected Output

- `vinted_radar/services/discovery.py` — native API price bounds plus preserved client-side safety filter.
- `vinted_radar/services/runtime.py` — `max_price` forwarded into discovery and runtime config.
- `vinted_radar/cli.py` — `--max-price` support for `batch` and `continuous`.
- `tests/test_discovery_service.py` — updated URL expectation for the existing min-price path.
