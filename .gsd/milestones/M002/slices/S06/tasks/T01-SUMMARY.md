---
id: T01
parent: S06
milestone: M002
provides:
  - Proxy-aware state refresh with persisted probe degradation telemetry on runtime cycles
key_files:
  - vinted_radar/parsers/item_page.py
  - vinted_radar/services/state_refresh.py
  - vinted_radar/services/runtime.py
  - vinted_radar/repository.py
  - vinted_radar/db.py
  - vinted_radar/cli.py
key_decisions:
  - Keep degraded item-page probe truth as persisted cycle telemetry instead of recomputing it only at render time.
patterns_established:
  - Treat anti-bot challenge, HTTP degradation, and transport exceptions as explicit probe-health signals distinct from ordinary unknown state outcomes.
observability_surfaces:
  - python -m vinted_radar.cli state-refresh --format json
  - python -m vinted_radar.cli runtime-status --format json
  - runtime_cycles.state_refresh_summary_json
  - tests/test_item_page_parser.py
  - tests/test_runtime_service.py
  - tests/test_runtime_repository.py
  - tests/test_runtime_cli.py
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: Harden state refresh transport and persist probe degradation telemetry

**Made item-page refresh proxy-aware, taught the probe parser to recognize anti-bot/challenge degradation, and persisted a structured `state_refresh_summary` on runtime cycles and CLI surfaces.**

## What Happened

The weak seam at the start of S06 was the item-page probe path. Discovery already had proxy rotation and retry-aware transport, but state refresh still used a direct client and collapsed every bad page into a generic `unknown`. T01 closed that gap in three layers.

First, `vinted_radar/parsers/item_page.py` now distinguishes challenge-shaped pages from normal inconclusive HTML. Retryable 403/429 responses and 200 pages containing Cloudflare/Turnstile-style challenge markers are classified as `anti_bot_challenge` instead of being flattened into a generic missing buy block.

Second, `vinted_radar/services/state_refresh.py` now accepts a proxy pool, threads it into `VintedHttpClient`, and returns a structured `probe_summary` on `StateRefreshReport`. That summary separates direct state signals from inconclusive probes and genuinely degraded probes, with counts for anti-bot challenges, HTTP degradation, transport exceptions, outcome counts, and degraded listing ids.

Third, runtime persistence now keeps this summary on each cycle. `runtime_cycles` gained `state_refresh_summary_json`, `RadarRuntimeService` now passes proxy pools to state refresh just like discovery, and both `runtime-status` and the cycle-report CLI output expose the new summary. The standalone `state-refresh` command also accepts repeatable `--proxy` options and emits the structured summary in JSON/table output.

## Verification

Ran the targeted T01 regression suite covering parser classification, state-refresh proxy wiring, runtime persistence, and CLI output.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_item_page_parser.py tests/test_runtime_service.py tests/test_runtime_repository.py tests/test_runtime_cli.py -q` | 0 | PASS | 1.84s |

## Diagnostics

Use `python -m vinted_radar.cli state-refresh --db <db> --format json` to inspect live `probe_summary` output from the standalone state-refresh path. Use `python -m vinted_radar.cli runtime-status --db <db> --format json` to inspect the persisted `latest_cycle.state_refresh_summary` on the runtime path. When that output looks suspicious, `runtime_cycles.state_refresh_summary_json` is now the durable SQLite truth.

## Deviations

none

## Known Issues

This task only made degraded probe truth measurable and persistent. The broader product surfaces still need to consume and explain that truth coherently in overview, explorer, detail, runtime HTML, and `/health`.

## Files Created/Modified

- `vinted_radar/parsers/item_page.py` — added explicit challenge-marker detection and anti-bot classification for degraded probe responses.
- `vinted_radar/services/state_refresh.py` — added proxy-aware refresh construction and structured `probe_summary` reporting.
- `vinted_radar/services/runtime.py` — passed proxy pools into state refresh and persisted state-refresh summaries on runtime cycles.
- `vinted_radar/repository.py` — persisted and hydrated `state_refresh_summary_json` on runtime cycles.
- `vinted_radar/db.py` — added the runtime-cycle schema/migration support for persisted state-refresh summaries.
- `vinted_radar/cli.py` — exposed proxy-aware `state-refresh` and richer runtime/state-refresh CLI output.
- `tests/test_item_page_parser.py` — covered anti-bot/challenge classification paths.
- `tests/test_runtime_service.py` — covered proxy forwarding into state refresh and persisted runtime summaries.
- `tests/test_runtime_repository.py` — covered persisted runtime-cycle hydration of state-refresh summaries.
- `tests/test_runtime_cli.py` — covered CLI exposure of the new state-refresh health contract.
