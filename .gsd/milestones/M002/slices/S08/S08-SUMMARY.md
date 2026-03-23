---
id: S08
parent: M002
milestone: M002
provides:
  - Native API-side price bounds for discovery plus shared runtime CLI support for `max_price`
requires:
  - slice: S06
    provides: acquisition/runtime plumbing that batch and continuous both share
  - slice: S07
    provides: the post-closeout integrated operator path that S08 extends without introducing a parallel entrypoint
affects:
  - M003
key_files:
  - vinted_radar/services/discovery.py
  - vinted_radar/services/runtime.py
  - vinted_radar/cli.py
  - tests/test_discovery_service.py
  - .gsd/milestones/M002/M002-ROADMAP.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D031 — apply configured price bounds at the API boundary while retaining a local safety net before persistence
patterns_established:
  - Push price windows upstream whenever the API supports them, but keep local persistence guards so acquisition correctness does not depend on upstream behavior being perfect
observability_surfaces:
  - catalog_scans.requested_url
  - runtime_cycles.config.max_price
  - python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q
  - python -m vinted_radar.cli runtime-status --db <db> --format json
drill_down_paths:
  - .gsd/milestones/M002/slices/S08/tasks/T01-SUMMARY.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
---

# S08: Native API Price Bounds for Discovery

**Moved price filtering to the Vinted API boundary for discovery/runtime while preserving the local price safety net and the persisted diagnostics that show what was really requested.**

## What Happened

S08 closes a straightforward but operationally meaningful gap in acquisition efficiency. Discovery already had a minimum-price guard locally, but it still downloaded full catalog pages before discarding off-range cards. That wastes requests and increases ban pressure for no analytical gain.

The slice pushed that filter to the API layer. `DiscoveryOptions` and `RadarRuntimeOptions` now both carry `max_price`, `_build_api_catalog_url()` emits `price_from` / `price_to` when configured, and the shared `batch` / `continuous` CLI path now exposes `--max-price` and persists it into runtime config before discovery runs.

I did not trust the upstream API as the sole correctness boundary. The client-side price guard remains in front of `upsert_listing()`, and now also rejects cards above the configured upper bound. That keeps the repo aligned with the user's explicit safety-net constraint while still gaining the request-volume win from API-side filtering.

The only follow-on breakage was a stale discovery test that pinned the old min-price URL. I updated that expectation rather than silently removing the new request contract.

## Verification

- `python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q`
- direct Python contract check for `_build_api_catalog_url(..., price_from=30.0, price_to=80.0)`, `_build_runtime_options(..., max_price=80.0)`, and `_listing_matches_filters(..., maximum_price_cents=8000)`

## Requirements Advanced

- R001 — the public discovery path now wastes fewer catalog requests by using the upstream API's native price window instead of relying only on post-download filtering.
- R010 — `batch` and `continuous` both gained shared `--max-price` support through the same runtime option path.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none — this slice tightens an existing acquisition path without changing the capability contract.

## Deviations

none

## Known Limitations

This slice proves contract correctness and local safety behavior, not a measured long-run reduction in live challenge rate or bans.

## Follow-ups

- If live acquisition pressure rises again, compare challenge/failure rate by price window to confirm whether the API-side bound materially improves the collector's operational headroom.

## Files Created/Modified

- `vinted_radar/services/discovery.py` — added `max_price`, API-side price bounds, and upper-bound local safety filtering.
- `vinted_radar/services/runtime.py` — forwarded `max_price` into discovery and persisted it in runtime config.
- `vinted_radar/cli.py` — exposed `--max-price` on `batch` and `continuous`.
- `tests/test_discovery_service.py` — updated the stale min-price URL expectation.
- `.gsd/milestones/M002/M002-ROADMAP.md` — added and closed S08 in the milestone roadmap.
- `.gsd/PROJECT.md` — updated current state to include the new discovery/runtime contract.
- `.gsd/KNOWLEDGE.md` — recorded the new acquisition pattern.
- `.gsd/DECISIONS.md` — recorded D031 for API-side price bounds with local safety filtering.

## Forward Intelligence

### What the next slice should know
- `catalog_scans.requested_url` is now the quickest truthful signal for whether discovery really honored the configured price window at the HTTP boundary.

### What's fragile
- The operational benefit is real in theory, but it still depends on Vinted continuing to honor `price_from` / `price_to` on `api/v2/catalog/items`.

### Authoritative diagnostics
- `python -m vinted_radar.cli runtime-status --db <db> --format json` — confirms the runtime config actually carried `max_price` into the run.

### What assumptions changed
- "The local filter is enough." — It was correct but wasteful; the better contract is API-side filtering for throughput plus local filtering for correctness.
