# S09: High-Throughput Proxy Pool + Webshare Acquisition Operator Flow

**Goal:** Turn the provided 100-proxy Webshare pool into a first-class acquisition path by accepting raw `host:port:user:pass` entries, auto-loading a local ignored proxy file, distributing discovery traffic across warmed proxy lanes instead of a single retry-only proxy, and shipping live preflight + runtime-safe diagnostics that prove the pool is really in use.
**Demo:** `python -m pytest tests/test_proxy_config.py tests/test_http.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_cli_discover_smoke.py -q`, then `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 8 --format json`, then `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt`, and finally `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json` prove that the operator path can load the Webshare pool, verify multiple live routes, run a real proxy-backed cycle, and persist only safe proxy-pool metadata.

## Must-Haves

- Raw Webshare proxy entries (`host:port:user:pass`) must be accepted from both repeatable CLI input and a local ignored proxy file.
- Discovery must spread concurrent requests across multiple proxy-backed sessions with per-route warm-up, throttling, and cooldown, instead of pinning the whole async run to one active proxy until failure.
- Operator diagnostics must expose safe proxy-pool activation/count and live preflight results without persisting or rendering credentials.
- A real live verification pass must show that the pool is loaded, multiple routes answer, and a proxy-backed batch cycle succeeds against Vinted.

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `python -m pytest tests/test_proxy_config.py tests/test_http.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_cli_discover_smoke.py -q`
- `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 8 --format json`
- `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json`

## Observability / Diagnostics

- Runtime signals: `runtime_cycles.config.proxy_pool_size`, `runtime_cycles.config.transport_mode`, proxy preflight summary counts, and retry/cooldown-aware transport logs.
- Inspection surfaces: `python -m vinted_radar.cli proxy-preflight --format json`, `python -m vinted_radar.cli runtime-status --format json`, `python -m vinted_radar.cli batch ...`, and the live `catalog_scans` / `runtime_cycles` rows in SQLite.
- Failure visibility: per-route preflight failures, retryable HTTP/network degradation, disabled proxy cooldowns, and persisted runtime config that shows the pool was active without leaking credentials.
- Redaction constraints: never persist or render proxy credentials; only counts, masked labels, and safe route-level diagnostics are allowed.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/http.py`, `vinted_radar/services/discovery.py`, `vinted_radar/services/state_refresh.py`, `vinted_radar/services/runtime.py`, `vinted_radar/cli.py`, `vinted_radar/repository.py`, and existing acquisition/runtime CLI contracts.
- New wiring introduced in this slice: local Webshare proxy file -> proxy normalization/resolution -> multi-route HTTP transport -> `discover` / `batch` / `continuous` / `state-refresh` / `proxy-preflight` operator entrypoints -> safe runtime persistence + diagnostics.
- What remains before the milestone is truly usable end-to-end: nothing inside M002; this slice is a throughput/operability hardening pass on top of the already complete product surface.

## Tasks

- [x] **T01: Establish the Webshare proxy-pool contract and safe operator inputs** `est:1h`
  - Why: the provided proxy list is not in the URL shape the current CLI expects, and the operator path still has no first-class, gitignored local proxy file contract.
  - Files: `vinted_radar/proxies.py`, `vinted_radar/cli.py`, `vinted_radar/services/runtime.py`, `README.md`, `tests/test_proxy_config.py`, `tests/test_cli_discover_smoke.py`, `tests/test_runtime_cli.py`
  - Do: add proxy normalization/loading helpers that accept raw Webshare entries plus URL-form proxies, support `--proxy-file` and auto-discover `data/proxies.txt` when present, surface only safe proxy-pool metadata in runtime config/output, and document the local operator contract.
  - Verify: `python -m pytest tests/test_proxy_config.py tests/test_cli_discover_smoke.py tests/test_runtime_cli.py -q`
  - Done when: the CLI and runtime can consume a local proxy pool without manual URL rewriting, and runtime-facing config/output expose only safe pool metadata.
- [x] **T02: Rebuild the HTTP transport around real multi-route proxy throughput** `est:2h`
  - Why: the current transport only rotates proxies on failure, so a large pool barely helps throughput and discovery still effectively runs through one active route at a time.
  - Files: `vinted_radar/http.py`, `vinted_radar/services/discovery.py`, `vinted_radar/services/state_refresh.py`, `tests/test_http.py`, `tests/test_discovery_service.py`
  - Do: replace the retry-only proxy posture with route-local sync/async session state, per-route warm-up and delay tracking, async route selection across the pool, retry/cooldown handling for degraded routes, and regression coverage that proves concurrent discovery requests spread across more than one proxy route.
  - Verify: `python -m pytest tests/test_http.py tests/test_discovery_service.py -q`
  - Done when: concurrent async discovery can use multiple proxy routes without leaking credentials or regressing the non-proxy path.
- [x] **T03: Add proxy preflight diagnostics and live operator proof hooks** `est:1h30m`
  - Why: the operator needs a trustworthy way to prove the pool is loaded, multiple routes respond, and the real acquisition path is using the pool before trusting longer unattended runs.
  - Files: `vinted_radar/cli.py`, `vinted_radar/http.py`, `tests/test_runtime_cli.py`, `README.md`
  - Do: add a `proxy-preflight` command that samples the configured pool through a public IP echo check plus a lightweight Vinted reachability check, returns safe JSON/table diagnostics, and reuses the same proxy-resolution contract as the real acquisition commands.
  - Verify: `python -m pytest tests/test_runtime_cli.py -q` and `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 8 --format json`
  - Done when: a future agent can confirm pool health and uniqueness of exit routes from one command before running `discover` or `batch`.
- [x] **T04: Run live Webshare-backed verification and close out S09 artifacts** `est:1h30m`
  - Why: this slice only counts if the real provided pool works end to end, the runtime truth stays safe, and the milestone artifacts capture the new operator contract.
  - Files: `.gsd/milestones/M002/M002-ROADMAP.md`, `.gsd/milestones/M002/slices/S09/S09-UAT.md`, `.gsd/milestones/M002/slices/S09/S09-SUMMARY.md`, `.gsd/milestones/M002/slices/S09/tasks/T01-SUMMARY.md`, `.gsd/milestones/M002/slices/S09/tasks/T02-SUMMARY.md`, `.gsd/milestones/M002/slices/S09/tasks/T03-SUMMARY.md`, `.gsd/milestones/M002/slices/S09/tasks/T04-SUMMARY.md`, `.gsd/PROJECT.md`, `.gsd/KNOWLEDGE.md`, `.gsd/DECISIONS.md`
  - Do: write the task/slice/UAT artifacts, update the roadmap/project/knowledge/decision registers, run live preflight plus proxy-backed batch verification against the provided pool, and capture safe evidence and any residual limitations.
  - Verify: `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt` and `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json`
  - Done when: S09 has live proof, complete GSD artifacts, and a clear forward record for future acquisition work.

## Files Likely Touched

- `vinted_radar/proxies.py`
- `vinted_radar/http.py`
- `vinted_radar/cli.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/services/state_refresh.py`
- `tests/test_proxy_config.py`
- `tests/test_http.py`
- `tests/test_runtime_cli.py`
- `tests/test_cli_discover_smoke.py`
- `README.md`
- `.gsd/milestones/M002/M002-ROADMAP.md`
- `.gsd/milestones/M002/slices/S09/S09-SUMMARY.md`
- `.gsd/milestones/M002/slices/S09/S09-UAT.md`
