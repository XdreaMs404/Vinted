---
id: T01
parent: S09
milestone: M002
provides:
  - Webshare proxy normalization, gitignored local pool loading, and safe runtime metadata for proxy-aware operator commands
key_files:
  - vinted_radar/proxies.py
  - vinted_radar/cli.py
  - vinted_radar/services/runtime.py
  - README.md
  - tests/test_proxy_config.py
  - tests/test_cli_discover_smoke.py
  - tests/test_runtime_cli.py
key_decisions:
  - Keep the operator contract on a gitignored local proxy file or explicit `--proxy-file` input, not on committed config or manual URL rewriting.
patterns_established:
  - Normalize provider-specific proxy exports once at the CLI/config boundary and persist only safe pool metadata (`transport_mode`, `proxy_pool_size`) downstream.
observability_surfaces:
  - python -m vinted_radar.cli discover --help
  - python -m vinted_radar.cli state-refresh --format json
  - python -m vinted_radar.cli runtime-status --format json
  - tests/test_proxy_config.py
  - tests/test_cli_discover_smoke.py
  - tests/test_runtime_cli.py
duration: 1 session
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T01: Establish the Webshare proxy-pool contract and safe operator inputs

**Added a first-class Webshare proxy contract: raw `host:port:user:pass` input now works, a local gitignored proxy file can auto-load, and runtime-facing config stays credential-safe.**

## What Happened

The first job in S09 was to stop treating the user's proxy list as a copy-paste inconvenience. I added `vinted_radar/proxies.py` as the central normalization boundary, so the codebase now accepts both full proxy URLs and raw Webshare exports without forcing the operator to rewrite 100 lines by hand.

From there I threaded one shared loading contract through the CLI. `discover`, `batch`, `continuous`, and `state-refresh` now accept `--proxy-file`, and when no explicit source is passed they auto-load `data/proxies.txt` if it exists. I also changed the fallback behavior carefully: the local file is only auto-used when there is no explicit proxy source, so inline `--proxy` inputs do not get polluted by the default file.

The last part of T01 was honesty. `RadarRuntimeOptions.as_config()` now records only `transport_mode` and `proxy_pool_size`, never proxy credentials. The CLI JSON/table outputs gained safe transport metadata, and README now documents the local Webshare setup plus the new `proxy-preflight` workflow.

## Verification

Ran the targeted parsing/CLI regression suite for the new proxy contract.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_proxy_config.py tests/test_cli_discover_smoke.py tests/test_runtime_cli.py -q` | 0 | PASS | 0.66s |

## Diagnostics

Use `python -m vinted_radar.cli state-refresh --db <db> --format json` to confirm the live command reports safe `transport.mode` / `proxy_pool_size` metadata. Use `python -m vinted_radar.cli runtime-status --db <db> --format json` to confirm persisted controller/cycle config contains only safe proxy-pool metadata.

## Deviations

none

## Known Issues

T01 only established the input/runtime contract. At this point in the slice, it still did not guarantee that the async transport would exploit the pool for real throughput; that closure happened in T02.

## Files Created/Modified

- `vinted_radar/proxies.py` — added proxy normalization, loading, masking, and fallback resolution helpers.
- `vinted_radar/cli.py` — threaded `--proxy-file`, local fallback loading, and safe transport metadata through the operator commands.
- `vinted_radar/services/runtime.py` — persisted only `transport_mode` and `proxy_pool_size` for runtime-facing config.
- `README.md` — documented the local Webshare proxy-file contract and operator workflow.
- `tests/test_proxy_config.py` — covered raw Webshare parsing, default-file loading, and credential masking.
- `tests/test_cli_discover_smoke.py` — covered discover CLI proxy-file loading and auto-concurrency.
- `tests/test_runtime_cli.py` — covered state-refresh/proxy-file JSON output and preflight-safe route labels.