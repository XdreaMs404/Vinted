# S08: Native API Price Bounds for Discovery — UAT

**Milestone:** M002
**Written:** 2026-03-23

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S08 changes a backend request contract plus CLI/runtime plumbing, not a human-facing UI workflow. Persisted requested URLs, runtime config, and targeted regression commands are the truthful acceptance surface.

## Preconditions

- Python dependencies are installed.
- The project runs from `C:/Users/Alexis/Documents/VintedScrap2`.

## Smoke Test

Run `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q`.

## Test Cases

### 1. API URL includes the configured price window

1. Run a small Python check that calls `_build_api_catalog_url(2001, 2, price_from=30.0, price_to=80.0)`.
2. Confirm the resulting URL contains both `price_from=30.0` and `price_to=80.0`.
3. **Expected:** the API boundary now carries the configured price window instead of relying only on post-download filtering.

### 2. Runtime options preserve the upper bound

1. Build runtime options through `_build_runtime_options(..., min_price=30.0, max_price=80.0, ...)`.
2. Confirm `options.max_price == 80.0`.
3. **Expected:** `batch` and `continuous` can carry `--max-price` into discovery without custom per-command wiring.

### 3. Client-side safety filter still blocks out-of-range cards

1. Create a `ListingCard` with `price_amount_cents=9000`.
2. Call `_listing_matches_filters(..., minimum_price_cents=3000, maximum_price_cents=8000, ...)`.
3. **Expected:** the helper returns `False`, proving the local safety net still rejects an out-of-range card before persistence.

## Edge Cases

### No upper bound configured

1. Call `_build_api_catalog_url(2001, 1, price_from=30.0, price_to=0)`.
2. **Expected:** the URL contains `price_from=30.0` but omits `price_to`, so `0` still means "no upper bound".

## Failure Signals

- `batch --help` / `continuous --help` does not show `--max-price`.
- Persisted `catalog_scans.requested_url` never contains `price_from` / `price_to` even when configured.
- Runtime config JSON loses `max_price` between CLI parsing and discovery.
- Out-of-range cards can still reach `upsert_listing` when `max_price` is set.

## Requirements Proved By This UAT

- R001 — discovery can now constrain the public API boundary more tightly, reducing waste while keeping the ingestion contract intact.
- R010 — `batch` and `continuous` both carry the new acquisition option through the shared runtime path.

## Not Proven By This UAT

- Real ban-rate reduction in live production traffic over time.
- Any new product-surface or dashboard behavior; this slice only changes acquisition/runtime plumbing.

## Notes for Tester

- The authoritative proof surfaces are code-level and persisted-runtime artifacts, not browser behavior.
- `catalog_scans.requested_url` is the fastest way to confirm whether the API boundary actually received the price window.
