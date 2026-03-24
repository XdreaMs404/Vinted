---
estimated_steps: 4
estimated_files: 4
skills_used:
  - code-optimizer
  - test
---

# T03: Add proxy preflight diagnostics and live operator proof hooks

**Slice:** S09 — High-Throughput Proxy Pool + Webshare Acquisition Operator Flow
**Milestone:** M002

## Description

A big proxy pool is only useful if the operator can verify that it is alive and actually varied before trusting a long run. This task adds a first-class preflight command reusing the same proxy resolution and transport contract as the real collector.

## Steps

1. Add a `proxy-preflight` CLI command that loads the same proxy pool contract as the acquisition commands.
2. Sample a configurable subset of routes against a public IP-echo check and a lightweight Vinted reachability probe.
3. Return safe JSON/table output: pool size, sampled route count, successes/failures, unique exit IP count, and masked route labels only.
4. Add CLI regression coverage and README operator guidance.

## Must-Haves

- [ ] One command can prove that multiple configured proxy routes respond before a real batch run starts.
- [ ] Output stays credential-safe while still being operationally useful.
- [ ] The command reuses the real proxy loading contract, not a separate one-off parser.

## Verification

- `python -m pytest tests/test_runtime_cli.py -q`
- `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 8 --format json`

## Observability Impact

- Signals added/changed: proxy preflight success/failure counts, unique-exit-IP count, masked route labels.
- How a future agent inspects this: `python -m vinted_radar.cli proxy-preflight --format json`.
- Failure state exposed: dead or homogeneous proxy pools become visible before longer discovery/runtime work begins.

## Inputs

- `vinted_radar/cli.py` — current operator command surface.
- `vinted_radar/proxies.py` — shared proxy loading contract from T01.
- `vinted_radar/http.py` — transport path from T02.

## Expected Output

- `vinted_radar/cli.py` — `proxy-preflight` command.
- `README.md` — preflight usage docs.
- `tests/test_runtime_cli.py` — CLI coverage for preflight output/contract.
- `vinted_radar/http.py` — any safe transport snapshot/hooks needed for preflight.
