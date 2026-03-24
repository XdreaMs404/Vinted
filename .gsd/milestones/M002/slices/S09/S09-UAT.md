# S09: High-Throughput Proxy Pool + Webshare Acquisition Operator Flow — UAT

**Milestone:** M002
**Written:** 2026-03-24

## UAT Type

- UAT mode: live-runtime
- Why this mode is sufficient: S09 is an acquisition/operator hardening slice. The truth criterion is not visual polish but whether the provided Webshare pool can be loaded safely, preflighted honestly, and used by the real batch/runtime path without leaking credentials.

## Preconditions

- `data/proxies.txt` exists locally and contains the operator's Webshare pool.
- The machine has outbound network access.
- The Python environment can run `python -m vinted_radar.cli ...` commands from the repo root.

## Smoke Test

Run:

```bash
python -m vinted_radar.cli proxy-preflight \
  --proxy-file data/proxies.txt \
  --sample-size 4 \
  --timeout-seconds 10 \
  --format json
```

The command should report a non-zero `unique_exit_ip_count` and `vinted_success_count` for the sampled routes.

## Test Cases

### 1. Preflight the local Webshare pool

1. Run `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 12 --timeout-seconds 10 --format json`.
2. Inspect the JSON summary.
3. **Expected:** `configured_proxy_count` matches the local pool size, `sampled_routes` is `12`, `successful_routes` is greater than `0`, `unique_exit_ip_count` is greater than `1`, and route labels are masked (`http://***@host:port`).

### 2. Run a real proxy-backed batch smoke

1. Run `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt`.
2. Wait for the cycle report.
3. **Expected:** the cycle completes, the transport line reports `proxy-pool`, discovery reports at least one successful scan, and the state-refresh section reports a structured health status instead of an opaque failure.

### 3. Inspect persisted runtime truth

1. Run `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json`.
2. Inspect `controller.config` and `latest_cycle.config`.
3. **Expected:** `transport_mode` is `proxy-pool`, `proxy_pool_size` matches the configured pool size, no proxy credentials appear anywhere in the JSON, and the latest acquisition status remains inspectable.

## Edge Cases

### Explicit proxy input should override the local fallback

1. Run any proxy-aware command with repeatable `--proxy` values but without `--proxy-file`.
2. **Expected:** the command uses only the explicitly provided proxies; it must not silently append `data/proxies.txt` on top of them.

## Failure Signals

- `proxy-preflight` returns `successful_routes: 0`, `unique_exit_ip_count: 0`, or route-level `error` values for most sampled proxies.
- `batch` reports `Batch cycle failed`, repeated HTTP/transport degradation, or no successful scans.
- `runtime-status --format json` exposes proxy credentials instead of only safe pool metadata.

## Requirements Proved By This UAT

- R001 — proves the collector can still discover public Vinted listings while operating through the provided proxy pool.
- R010 — proves the real operator path (`batch` + `runtime-status`) can run with a local proxy-pool contract instead of only direct mode.

## Not Proven By This UAT

- Long unattended continuous-mode stability over many hours.
- Whether all 100 proxies stay equally healthy over time; the preflight is sampled, not exhaustive by default.
- Public VPS deployment changes; S09 proves the local operator contract and transport, not a new remote serving topology.

## Notes for Tester

The fastest trustworthy operator sequence is now: `proxy-preflight` first, then `batch` or `continuous`. If preflight starts failing broadly, inspect that before blaming the batch/runtime orchestration.