---
id: T02
parent: S04
milestone: M002
provides:
  - A responsive explorer workspace that surfaces active filters, comparison modules, result summaries, and paged listing cards over the SQL explorer contract
key_files:
  - vinted_radar/dashboard.py
  - README.md
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
key_decisions:
  - `/explorer` should read as the main browse-and-compare workspace, not a debug table wrapped in product chrome.
patterns_established:
  - Server-rendered explorer HTML and `/api/explorer` stay coupled through one payload assembly path so UI and diagnostics remain truthful.
observability_surfaces:
  - /explorer, /api/explorer, tests/test_dashboard.py, tests/test_dashboard_cli.py
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: Rebuild `/explorer` for scalable browsing on desktop and mobile

**Rebuilt `/explorer` into a filter-first, support-aware browsing surface with comparison panels, result summaries, and paged listing cards that stay usable without a wide debug table.**

## What Happened

`vinted_radar/dashboard.py` now renders the explorer around the stronger SQL contract from T01. The page shows active-filter state, result/inventory summaries, honesty notes, comparison modules, and paged listing cards with detail/API links instead of relying on a single oversized table as the primary interaction model.

The explorer shell now keeps support counts and low-support language visible in the page itself, so the user can tell whether a slice is broad or thin without opening JSON diagnostics. I also localized the new explorer option labels and documented the richer explorer workflow in `README.md`, including the supported query parameters and example URLs.

Dashboard route tests were expanded to assert the richer explorer payload and HTML behavior instead of the old stateless link contract.

## Verification

Dashboard route and CLI coverage passed on the rebuilt explorer, and the live dashboard command served the richer S04 explorer flow successfully on the demo DB.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | PASS | 1.08s |
| 2 | `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8783` | 0 | PASS | ready in ~6s |

## Diagnostics

Compare `/explorer` against `/api/explorer` when checking UI drift. The fastest regression path is `tests/test_dashboard.py`, while `README.md` now documents the intended public explorer query contract and example browse flows.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/dashboard.py` — rebuilt explorer rendering around active filters, summary cards, comparison modules, and paged listing cards.
- `tests/test_dashboard.py` — added explorer route assertions for richer payloads, context-bearing detail links, and comparison-link behavior.
- `tests/test_dashboard_cli.py` — kept CLI/dashboard route coverage aligned with the rebuilt explorer surface.
- `README.md` — documented the richer explorer workflow, supported query parameters, and example filtered URLs.
