---
id: T02
parent: S06
milestone: M002
provides:
  - A shared healthy/partial/degraded acquisition-health contract surfaced across overview, explorer, detail, runtime, `/api/runtime`, and `/health`
key_files:
  - vinted_radar/repository.py
  - vinted_radar/dashboard.py
  - tests/test_overview_repository.py
  - tests/test_dashboard.py
key_decisions:
  - Drive degraded-mode product honesty from one repository/runtime contract instead of page-local heuristics.
patterns_established:
  - Keep acquisition health as a first-class persisted/runtime-backed payload, then translate it in the product layer with page-appropriate copy.
observability_surfaces:
  - repository.runtime_status().acquisition
  - repository.overview_snapshot().summary.freshness
  - /api/runtime
  - /health
  - tests/test_overview_repository.py
  - tests/test_dashboard.py
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: Surface acquisition health honestly across overview, explorer, detail, runtime, and health JSON

**Added a shared `acquisition` / `acquisition_status` truth layer from the repository up through overview, explorer, detail, runtime, `/api/runtime`, and `/health`, with explicit degraded-mode copy instead of silent fallback.**

## What Happened

T02 took the new probe/runtime telemetry from T01 and made it legible across the actual product.

On the repository side, `runtime_status()` now exposes an `acquisition` block built from two persisted sources: failed discovery scans on the relevant run, and the latest persisted `state_refresh_summary` on a runtime cycle. That object distinguishes `healthy`, `partial`, `degraded`, and `unknown`, carries short reasons, and exposes example degraded probes plus recent scan failures. `overview_snapshot()` now threads the key parts of that truth into `summary.freshness`, so the home surface can talk about degraded acquisition without re-deriving it.

On the dashboard side, I wired that truth through all the live surfaces:
- the overview home now shows an acquisition pill and honesty notes for degraded or partial state refresh
- the explorer now carries an acquisition status pill plus a scoped warning when the currently served corpus is being read under degraded collection conditions
- listing detail now emits a `degraded-probe` risk note and provenance text when the latest item-page probe hit anti-bot or other degraded paths, instead of leaving the user to infer that from a raw `unknown (403)`-style trace
- the runtime page now has a dedicated acquisition-health section showing why the current status is healthy/partial/degraded, recent failed scans, and example degraded probes
- `/health` now includes the same acquisition summary so machine-facing checks can see the same degraded-mode truth as the UI

The seeded dashboard/overview fixtures were also upgraded so the tests exercise a real degraded path: one anti-bot-challenged listing probe plus a persisted degraded state-refresh summary on the latest runtime cycle.

## Verification

Ran the repository + route suite against the updated degraded-mode fixtures to prove the same contract across home, explorer, detail, runtime, and health routes.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_item_page_parser.py tests/test_runtime_service.py tests/test_runtime_repository.py tests/test_runtime_cli.py tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py -q` | 0 | PASS | 2.84s |

## Diagnostics

Inspect `repository.runtime_status(limit=..., now=...)['acquisition']` for the authoritative degraded-mode status. On the served app, compare `/api/runtime`, `/health`, and the matching HTML routes (`/`, `/explorer`, `/runtime`, `/listings/<id>`) before trusting any page-specific wording. `tests/test_overview_repository.py` and `tests/test_dashboard.py` are now the quickest alarms if those surfaces drift apart.

## Deviations

The plan did not explicitly call for a dedicated acquisition-health section on the runtime page, but once the shared contract existed it became the clearest way to keep degraded probe examples and failed scans visible without overloading the controller card.

## Known Issues

The explorer cards themselves still show a fairly terse latest-probe display. The surface-level honesty is now present via the explorer status/warning layer, but a future refinement could make per-card degraded probe copy more explicit without bloating the result cards.

## Files Created/Modified

- `vinted_radar/repository.py` — added repository-owned acquisition-health aggregation and threaded it into runtime/overview payloads.
- `vinted_radar/dashboard.py` — surfaced degraded acquisition truth across home, explorer, detail, runtime, and health routes.
- `tests/test_overview_repository.py` — seeded and asserted degraded acquisition fields on overview snapshot output.
- `tests/test_dashboard.py` — seeded and asserted degraded acquisition behavior across HTML and JSON product routes.
