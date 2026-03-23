# S08: Native API Price Bounds for Discovery

**Goal:** Push the price window into Vinted's catalog API requests so discovery downloads fewer irrelevant cards, while keeping the existing client-side price guard as a safety net and threading the new upper bound through the runtime CLI.
**Demo:** `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` plus `python - <<'PY' ... _build_api_catalog_url(..., price_from=30.0, price_to=80.0) ... PY` proves the URL, runtime wiring, and client-side safety filter all hold.

## Must-Haves

- `_build_api_catalog_url()` adds `price_from` and `price_to` only when the configured bounds are greater than zero.
- `DiscoveryOptions`, runtime options, and the `batch` / `continuous` CLI commands all carry `max_price` end to end.
- The client-side price guard still runs before `upsert_listing`, so unexpected out-of-range cards from the API are still dropped locally.

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q`
- `python - <<'PY'
from vinted_radar.cli import _build_runtime_options
from vinted_radar.models import ListingCard
from vinted_radar.services.discovery import _build_api_catalog_url, _listing_matches_filters

url = _build_api_catalog_url(2001, 2, price_from=30.0, price_to=80.0)
assert "price_from=30.0" in url and "price_to=80.0" in url
options = _build_runtime_options(
    page_limit=1,
    max_leaf_categories=2,
    root_scope="both",
    min_price=30.0,
    max_price=80.0,
    target_catalogs=[2001],
    target_brands=["Dior"],
    state_refresh_limit=1,
    request_delay=0.0,
    timeout_seconds=5.0,
    concurrency=1,
)
assert options.max_price == 80.0
listing = ListingCard(
    listing_id=1,
    source_url="s",
    canonical_url="c",
    title="t",
    brand="Dior",
    size_label=None,
    condition_label=None,
    price_amount_cents=9000,
    price_currency="EUR",
    total_price_amount_cents=9000,
    total_price_currency="EUR",
    image_url=None,
)
assert not _listing_matches_filters(
    listing,
    minimum_price_cents=3000,
    maximum_price_cents=8000,
    target_brands=frozenset(),
)
print("manual-checks: ok")
PY`

## Observability / Diagnostics

- Runtime signals: `runtime_cycles.config.max_price` records the upper bound used by `batch` and `continuous` runs.
- Inspection surfaces: `catalog_scans.requested_url` shows whether `price_from` / `price_to` actually reached the API boundary.
- Failure visibility: a missing query param is visible in the persisted requested URL instead of only through in-memory option wiring.
- Redaction constraints: none.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/services/discovery.py`, `vinted_radar/services/runtime.py`, and `vinted_radar/cli.py`.
- New wiring introduced in this slice: `batch` / `continuous` -> `RadarRuntimeOptions.max_price` -> `DiscoveryOptions.max_price` -> `_build_api_catalog_url(..., price_to=...)`.
- What remains before the milestone is truly usable end-to-end: nothing.

## Tasks

- [x] **T01: Thread native API price bounds through discovery and runtime CLI** `est:45m`
  - Why: discovery was still downloading off-range cards and relying mostly on local filtering, which wastes requests and increases ban pressure.
  - Files: `vinted_radar/services/discovery.py`, `vinted_radar/services/runtime.py`, `vinted_radar/cli.py`, `tests/test_discovery_service.py`
  - Do: add `max_price` to discovery/runtime options, pass `price_from` / `price_to` into the Vinted API URL builder, preserve the client-side guard before `upsert_listing`, and expose `--max-price` on `batch` and `continuous`.
  - Verify: `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q` and the manual Python check from this slice's verification block.
  - Done when: persisted requested URLs carry the API bounds, runtime options preserve `max_price`, and local filtering still rejects out-of-range cards before persistence.

## Files Likely Touched

- `vinted_radar/services/discovery.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/cli.py`
- `tests/test_discovery_service.py`
