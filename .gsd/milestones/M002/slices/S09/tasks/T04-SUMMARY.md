---
id: T04
parent: S09
milestone: M002
provides:
  - Live Webshare-backed verification evidence plus complete S09 roadmap/UAT/task/slice documentation and project-register updates
key_files:
  - .gsd/milestones/M002/M002-ROADMAP.md
  - .gsd/milestones/M002/slices/S09/S09-UAT.md
  - .gsd/milestones/M002/slices/S09/S09-SUMMARY.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
  - data/proxies.txt
key_decisions:
  - Record the proxy-pool transport architecture in the append-only decision register as D032 so future agents do not “simplify” back to retry-only proxy rotation.
patterns_established:
  - Leave live acquisition hardening with both code-level proof and operator-facing artifact proof: roadmap, UAT, task summaries, project state, knowledge, and decision register.
observability_surfaces:
  - python -m pytest -q
  - python -m vinted_radar.cli proxy-preflight --format json
  - python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db ...
  - python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json
duration: 1 session
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T04: Run live Webshare-backed verification and close out S09 artifacts

**Stored the provided pool locally, proved it live through preflight plus a real batch smoke, and closed S09 with full roadmap/UAT/summary/register updates.**

## What Happened

T04 turned the code changes into project truth. I stored the provided 100-route Webshare pool in the agreed gitignored local path (`data/proxies.txt`), ran the live preflight against a 12-route sample, and then ran a real proxy-backed batch smoke against Vinted with `concurrency=8`.

The live results were good. Preflight reported `configured_proxy_count=100`, `sampled_routes=12`, `successful_routes=12`, `failed_routes=0`, `unique_exit_ip_count=12`, and `vinted_success_count=12` after the warm-up alignment fix from T03. The real batch smoke completed in one cycle, persisted `transport_mode=proxy-pool` and `proxy_pool_size=100` in runtime config, discovered 96 listings on the chosen single leaf catalog, and finished with a healthy one-listing state refresh.

After the live proof, I updated the project registers and artifacts so the next agent can continue without replaying the whole session: roadmap, project state, knowledge, decision register, UAT, and the task/slice summaries you are reading now.

## Verification

Ran the full pytest suite for broad regression safety, then verified the live preflight, the real proxy-backed batch smoke, and persisted runtime JSON.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest -q` | 0 | PASS | 3.98s |
| 2 | `python -m vinted_radar.cli proxy-preflight --proxy-file data/proxies.txt --sample-size 12 --timeout-seconds 10 --format json` | 0 | PASS | 4.40s |
| 3 | `python -m vinted_radar.cli batch --db data/vinted-radar-s09-live.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 1 --request-delay 0.2 --timeout-seconds 10 --concurrency 8 --proxy-file data/proxies.txt` | 0 | PASS | 12.00s |
| 4 | `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json` | 0 | PASS | 0.47s |

## Diagnostics

The authoritative live proof bundle for this task is now split across safe on-disk and repo-owned surfaces: `data/proxies.txt` (local pool input, gitignored), `data/vinted-radar-s09-live.db` (live smoke DB), `python -m vinted_radar.cli proxy-preflight --format json` (sampled route truth), and `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s09-live.db --format json` (persisted safe runtime truth).

## Deviations

none beyond the T03 preflight warm-up correction already captured there.

## Known Issues

The live proof is still a smoke-scale run: one leaf catalog, one state probe, and one completed batch cycle. It proves the operator contract and transport work, not long unattended stability across the full 100-route pool.

## Files Created/Modified

- `data/proxies.txt` — stored the provided Webshare pool in the agreed gitignored local path.
- `.gsd/milestones/M002/M002-ROADMAP.md` — added and closed S09 in the milestone roadmap.
- `.gsd/milestones/M002/slices/S09/S09-UAT.md` — documented the live proxy-pool UAT path.
- `.gsd/milestones/M002/slices/S09/S09-SUMMARY.md` — captured the slice closeout story and live proof.
- `.gsd/PROJECT.md` — updated current project state and the verified-today evidence.
- `.gsd/KNOWLEDGE.md` — recorded the new route-local transport pattern and the preflight warm-up lesson.
- `.gsd/DECISIONS.md` — appended D032 for the S09 proxy-pool architecture.