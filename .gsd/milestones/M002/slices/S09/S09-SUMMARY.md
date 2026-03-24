---
id: S09
parent: M002
milestone: M002
provides:
  - A high-throughput, credential-safe Webshare proxy-pool operator path with real multi-route transport and preflight-backed live proof
requires:
  - slice: S06
    provides: acquisition/runtime plumbing and degraded-mode honesty across discovery, state refresh, and runtime surfaces
  - slice: S08
    provides: the API-bound discovery path that the new proxy preflight now probes directly after warm-up
affects:
  - M003
key_files:
  - vinted_radar/proxies.py
  - vinted_radar/http.py
  - vinted_radar/cli.py
  - vinted_radar/services/runtime.py
  - README.md
  - tests/test_proxy_config.py
  - tests/test_http.py
  - tests/test_runtime_cli.py
  - .gsd/milestones/M002/M002-ROADMAP.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D032 — use a gitignored local proxy-file contract plus route-local sync/async transport state and preflight-backed operator proof instead of retry-only proxy rotation
patterns_established:
  - Normalize provider-specific proxy exports once at the config boundary, then treat the pool as route-local transport state with per-route warm-up/throttling/cooldowns and safe runtime metadata only
observability_surfaces:
  - python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --format json
  - python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db ...
  - python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json
  - python -m pytest -q
  - data/vinted-radar-s09-live.db
drill_down_paths:
  - .gsd/milestones/M002/slices/S09/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S09/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S09/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S09/tasks/T04-SUMMARY.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-24
---

# S09: High-Throughput Proxy Pool + Webshare Acquisition Operator Flow

**Turned the provided 100-route Webshare pool into a real operator contract and throughput primitive: raw proxy exports now load cleanly, discovery can use multiple warmed routes instead of one-hot failure rotation, `proxy-preflight` proves live route diversity plus Vinted API reachability, and runtime persistence stays credential-safe.**

## What Happened

S09 started from a practical gap and a transport gap.

The practical gap was the operator contract. The user had a 100-route Webshare export in raw `host:port:user:pass` form, while the repo only understood proxy URLs and expected the operator to pass them manually. I fixed that first by adding `vinted_radar/proxies.py`, centralizing normalization/masking/loading, teaching the CLI to accept `--proxy-file`, and auto-loading a gitignored local `data/proxies.txt` pool when no explicit source is given. Runtime-facing config now records only `transport_mode` and `proxy_pool_size`.

The transport gap was more important. The old `VintedHttpClient` only rotated proxies after retryable failures. In healthy runs, a large pool barely mattered because the async collector still behaved like one active proxy plus backups. I rewrote `vinted_radar/http.py` around route-local state: each lane now owns its own session, warm-up, request-delay timestamps, cooldown/rebuild flags, and masked label. Async route selection now reserves whichever route is ready soonest with the lowest in-flight pressure, so concurrent discovery can really spread across the pool.

Then I closed the operator loop with `proxy-preflight`. The command samples a subset of the configured pool, confirms distinct egress IPs, and checks the actual Vinted discovery API path through warmed single-route clients. The first version was wrong in an interesting way: it probed Vinted directly on raw proxy sessions and misclassified healthy routes as challenged. I corrected that by making preflight warm the route first, just like the real collector. After that fix, the live preflight results lined up with the real batch smoke.

The live proof is solid for smoke-scale acceptance. With the provided local pool in `data/proxies.txt`, `proxy-preflight --sample-size 12 --format json` reported `configured_proxy_count=100`, `sampled_routes=12`, `successful_routes=12`, `failed_routes=0`, `unique_exit_ip_count=12`, and `vinted_success_count=12`. A real proxy-backed batch smoke (`page-limit 1`, `max-leaf-categories 1`, `state-refresh-limit 1`, `concurrency 8`) completed successfully, discovered 96 listings, finished with a healthy state probe, and persisted safe runtime metadata showing `transport_mode=proxy-pool` and `proxy_pool_size=100` without leaking credentials.

## Verification

- `python -m pytest tests/test_proxy_config.py tests/test_http.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_cli_discover_smoke.py -q`
- `python -m pytest -q`
- `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 12 --timeout-seconds 10 --format json`
- `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt`
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json`

## Requirements Advanced

- R001 — the public acquisition path can now operate through the provided 100-route proxy pool with a real local operator contract instead of manual proxy rewriting and retry-only proxy usage.
- R010 — the shared operator entrypoints (`batch`, `continuous`, `state-refresh`) now understand a local proxy pool, safe runtime metadata, and a preflight-first workflow.

## Requirements Validated

- none — S09 hardens and operationalizes already-shipped acquisition/runtime paths rather than changing a requirement's validation status.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The only meaningful deviation was inside T03: the first preflight implementation judged Vinted reachability before reproducing the collector's warm-up posture. That produced a false all-challenge result on healthy routes, so I changed preflight to warm first and probe the actual discovery API path.

## Known Limitations

- The live acceptance is smoke-scale, not a long unattended multi-hour run over the full pool.
- Auto-concurrency now scales to `min(proxy_pool_size, 12)` when a pool is active and `--concurrency` is omitted, but it is still a bounded heuristic rather than adaptive runtime tuning.
- `proxy-preflight` samples the first `N` routes by default; it does not exhaustively audit all 100 unless the operator raises `--sample-size`.

## Follow-ups

- Run a longer continuous-mode experiment with the same pool and compare `concurrency=8`, `12`, and an explicit higher cap to find the best stable throughput point under real anti-bot pressure.
- If future acquisition debugging needs more detail, consider a safe per-route aggregate diagnostics surface (success/failure counts only) without persisting secrets or raw route identifiers.

## Files Created/Modified

- `vinted_radar/proxies.py` — added raw Webshare parsing, proxy-file loading, masking, and safe metadata helpers.
- `vinted_radar/http.py` — replaced retry-only proxy rotation with route-local sync/async transport state, cooldowns, and masked logs.
- `vinted_radar/cli.py` — added `--proxy-file`, local fallback loading, auto-concurrency with proxy pools, safe transport summaries, and the new `proxy-preflight` command.
- `vinted_radar/services/runtime.py` — persisted safe `transport_mode` / `proxy_pool_size` runtime metadata.
- `README.md` — documented the local Webshare proxy contract, preflight-first workflow, and auto-concurrency behavior.
- `tests/test_proxy_config.py` — covered parsing, local fallback loading, and credential masking.
- `tests/test_http.py` — covered async multi-route spread and retry-on-another-route behavior.
- `tests/test_cli_discover_smoke.py` — covered discover proxy-file loading and auto-concurrency.
- `tests/test_runtime_cli.py` — covered state-refresh transport metadata, proxy-file loading, and preflight-safe route labels.
- `.gsd/milestones/M002/M002-ROADMAP.md` — added and closed S09 in the milestone roadmap.
- `.gsd/PROJECT.md` — updated current state and verified-today proof.
- `.gsd/KNOWLEDGE.md` — recorded the new route-local transport pattern plus the preflight warm-up lesson.
- `.gsd/DECISIONS.md` — appended D032 for the S09 proxy-pool architecture.

## Forward Intelligence

### What the next slice should know
- `proxy-preflight` only became trustworthy once it warmed the route first and then hit the actual discovery API path. If future preflight work starts failing unexpectedly, check whether it still mirrors the collector's warm-up sequence.

### What's fragile
- The new transport deliberately optimizes the proxy-pooled path. If someone later “simplifies” `vinted_radar/http.py` back toward one global session and one global request-delay timestamp, they will silently kill most of the throughput gain from the pool.

### Authoritative diagnostics
- `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --format json` — fastest truthful read on pool diversity and warmed Vinted reachability before a run.
- `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json` — authoritative persisted proof that the completed cycle ran in `proxy-pool` mode with safe metadata only.

### What assumptions changed
- “A large proxy list already means the collector is proxy-aware enough.” — false; until S09, the collector mostly used one active proxy and treated the rest as retry-time backups.
- “A raw Vinted reachability GET is a good proxy preflight.” — false; it produced a misleading all-challenge result until the warm-up sequence matched the real collector.