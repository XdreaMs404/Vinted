---
id: T02
parent: S01
milestone: M002
provides:
  - French-first `/` overview home backed by `RadarRepository.overview_snapshot()` with explicit honesty notes, comparison modules, and live drill-down links
key_files:
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
  - README.md
  - data/vinted-radar-s01.db
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep `/api/dashboard` as the brownfield-compatible machine endpoint while moving the primary `/` home to the SQL overview contract and using SQL explorer rows for listing drill-down links instead of the old in-page proof stack.
patterns_established:
  - Build the home payload from `overview_snapshot()` and source its example listing links from `listing_explorer_page()` so `/` stays SQL-first even when it exposes `/explorer` and `/api/listings/<id>` drill-downs.
observability_surfaces:
  - /api/dashboard
  - /api/runtime
  - /health
  - data/vinted-radar-s01.db
  - tests/test_dashboard.py
  - tests/test_overview_repository.py
duration: 4h30m
verification_result: passed
completed_at: 2026-03-22T20:44:55+01:00
blocker_discovered: false
---

# T02: Rebuild `/` as a French overview home on top of the SQL contract

**Rebuilt `/` as a French SQL-backed market overview with honesty notes and live drill-down links.**

## What Happened

I replaced the old home-path Python scoring/dashboard assembly in `vinted_radar/dashboard.py` with a payload that takes its primary market overview directly from `RadarRepository.overview_snapshot()`.

The new home now renders as a French-first overview surface instead of the old M001 proof screen. It keeps:
- top-level market cards for tracked inventory, sold-like signal, confidence, and freshness
- visible honesty notes for inferred states, missing/estimated publication timing, low-support rules, and degraded acquisition cases
- first comparison modules for categories, brands, price bands, conditions, and sold-state posture
- working drill-down links to `/explorer`, `/api/dashboard`, `/api/runtime`, `/health`, and listing-detail JSON
- example listing cards sourced from the SQL explorer path instead of the retired in-page ranking/detail stack

I also updated the CLI output in `vinted_radar/cli.py` so the local server prints the overview home, explorer, runtime, and health routes alongside the compatibility `/api/dashboard` endpoint.

In `README.md`, I refreshed the route and entrypoint documentation to describe the new overview home semantics.

In `tests/test_dashboard.py` and `tests/test_dashboard_cli.py`, I rewrote the assertions around the new SQL overview payload, French home copy, honesty cues, featured listing drill-down links, and the updated CLI route messaging.

During live verification I found a real browser-only regression: a malformed favicon tag caused the entire overview stylesheet to be parsed as link text, leaving the page visually unstyled. I fixed that in the home renderer, added a matching favicon to the explorer page to prevent a stray `/favicon.ico` 404 during browser verification, and tightened the HTML route test to assert the `<style>` block is actually present.

Because the slice contract referenced `data/vinted-radar-s01.db` but that file was not present locally, I materialized it from the existing seeded overview fixture before running the real server/browser verification flow.

## Verification

I verified the task and the slice in three layers:

1. Task-level pytest for the rebuilt dashboard route and CLI contract.
2. Slice-level pytest including the repository overview contract, dashboard HTML/JSON route, and dashboard CLI output.
3. Real-server and browser verification against `data/vinted-radar-s01.db`, confirming:
   - the home route shows French overview copy and comparison modules
   - the home page exposes visible honesty/freshness/confidence signals
   - `/explorer`, `/api/dashboard`, `/api/runtime`, and `/health` all load from the live server with no console or failed-request errors
   - `/api/dashboard`, `/api/runtime`, and `/health` parse as the expected machine-readable JSON payloads in-browser

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | ✅ pass | 0.49s |
| 2 | `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | ✅ pass | 0.56s |
| 3 | `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765` | n/a (server reached ready state) | ✅ pass | ready in ~9s |
| 4 | `browser @ http://127.0.0.1:8765/ → /explorer → /api/dashboard → /api/runtime → /health` | n/a | ✅ pass | UAT / live route traversal |

## Diagnostics

Future agents can inspect the shipped behavior through:
- `/api/dashboard` for the SQL overview payload, comparison modules, and top-level honesty notes
- `/api/runtime` for the latest runtime-cycle truth
- `/health` for quick server/db health confirmation
- `data/vinted-radar-s01.db` for the seeded local demo dataset used in slice verification
- `tests/test_dashboard.py` for the WSGI contract and HTML regression expectations
- `tests/test_overview_repository.py` for the underlying SQL overview contract guarantees

## Deviations

- The slice contract referenced `data/vinted-radar-s01.db`, but that database was not present in the checkout. I created it locally from the existing overview test fixture so the required live CLI/browser verification could run against the intended seeded overview dataset.

## Known Issues

- None.

## Files Created/Modified

- `vinted_radar/dashboard.py` — replaced the home payload/rendering with the SQL overview contract, added French overview UI helpers, preserved JSON diagnostics, and fixed the live HTML favicon/style regression.
- `vinted_radar/cli.py` — updated local server output to print overview-home, explorer, runtime, and health routes alongside `/api/dashboard`.
- `tests/test_dashboard.py` — rewrote route assertions for the SQL overview payload, French home HTML, and live drill-down paths.
- `tests/test_dashboard_cli.py` — updated CLI assertions for the new overview-oriented route output.
- `README.md` — refreshed entrypoint and route docs to describe the French overview home and compatibility `/api/dashboard` payload.
- `data/vinted-radar-s01.db` — created the seeded slice-demo SQLite database used for real server/browser verification.
- `.gsd/KNOWLEDGE.md` — recorded that the S01 demo DB must be materialized locally from the seeded overview fixture before running the browser demo flow.
