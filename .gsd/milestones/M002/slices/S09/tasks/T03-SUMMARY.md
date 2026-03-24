---
id: T03
parent: S09
milestone: M002
provides:
  - A `proxy-preflight` operator command that proves exit-route diversity and Vinted API reachability through the same local proxy contract as the real collector
key_files:
  - vinted_radar/cli.py
  - README.md
  - tests/test_runtime_cli.py
key_decisions:
  - Preflight must mirror the real collector's warm-up posture before judging Vinted reachability, otherwise healthy routes can be misclassified as challenged.
patterns_established:
  - Operator preflight should verify both generic egress diversity and the actual discovery API reachability through warmed routes, not only raw proxy liveness.
observability_surfaces:
  - python -m vinted_radar.cli proxy-preflight --format json
  - tests/test_runtime_cli.py
duration: 1 session
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T03: Add proxy preflight diagnostics and live operator proof hooks

**Added `proxy-preflight` so the operator can verify a sample of routes, count unique exits, and confirm warmed Vinted API reachability before trusting a real run.**

## What Happened

T03 closed the operator loop. A big proxy pool is only useful if the operator can answer three quick questions before starting a longer run: did the pool actually load, do the sampled routes exit from distinct IPs, and can those warmed routes reach the actual Vinted discovery path?

I added `proxy-preflight` to the CLI for exactly that. It reuses the same proxy normalization/loading contract from T01, masks route labels in its output, samples a configurable subset of routes, checks exit IPs, and then probes the real discovery API path through a warmed single-route `VintedHttpClient` instance.

The first version of this command was too pessimistic: it hit the Vinted path on raw proxy sessions without reproducing the collector's homepage warm-up first, which made healthy routes look challenge-shaped. I fixed that inside the same task by aligning preflight with the real transport posture — warm first, then probe the actual discovery API URL. After that change, the live preflight results matched the later batch smoke.

## Verification

Ran the CLI regression suite, then executed the live preflight against the provided Webshare pool.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_runtime_cli.py -q` | 0 | PASS | 0.48s |
| 2 | `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 12 --timeout-seconds 10 --format json` | 0 | PASS | 4.40s |

## Diagnostics

`python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --format json` is now the authoritative pre-run health check for the local proxy pool. It reports safe route labels, sampled/success/failed counts, unique exit IP count, and whether the warmed route could reach the actual Vinted discovery API path.

## Deviations

The task plan said “lightweight Vinted reachability probe,” but the first implementation used an un-warmed raw session and produced a misleading all-challenge result. I corrected the command to reuse the warmed transport posture before closing the task.

## Known Issues

The command samples the first `N` routes, not the entire pool, unless the operator raises `--sample-size`. That keeps it fast, but it is still a sample rather than a full 100-route audit by default.

## Files Created/Modified

- `vinted_radar/cli.py` — added `proxy-preflight`, safe JSON/table output, and warmed Vinted API reachability checks.
- `README.md` — documented the preflight-first operator workflow.
- `tests/test_runtime_cli.py` — covered preflight JSON output and credential-safe route labels.