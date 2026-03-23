---
id: T03
parent: S07
milestone: M002
provides:
  - Real public VPS proof for overview, explorer, detail, runtime, and health, plus a documented live-service recovery path after retiring a corrupted 61 GB serving DB
key_files:
  - .gsd/milestones/M002/slices/S07/S07-UAT.md
  - .gsd/milestones/M002/M002-ROADMAP.md
  - .gsd/PROJECT.md
  - .gsd/REQUIREMENTS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Recover the public VPS by archiving the 61 GB corrupted live DB out of the serving path and repointing services to a fresh healthy clean DB, instead of trying to keep proving acceptance against a database that no longer answered truthfully.
patterns_established:
  - Do not trust `systemctl active` plus `ss` listening as proof that the public product works; require real HTTP checks against `/`, `/explorer`, `/runtime`, `/api/runtime`, `/api/listings/<id>`, and `/health` before calling the VPS entrypoint usable.
observability_surfaces:
  - http://46.225.113.129:8765/
  - http://46.225.113.129:8765/explorer
  - http://46.225.113.129:8765/runtime
  - http://46.225.113.129:8765/api/runtime
  - http://46.225.113.129:8765/health
  - python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111
  - systemctl status vinted-dashboard.service
  - /root/Vinted/data/vinted-radar.clean.db
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: Close S07 on the true public VPS base URL

**Recovered the real public VPS entrypoint, proved it from the internet-facing URL `http://46.225.113.129:8765/`, and closed the last acceptance gap that had been blocked by an operationally unusable 61 GB live SQLite file.**

## What Happened

The missing piece for S07 was no longer code. It was the real public VPS entrypoint.

Once SSH access became available, the first readback showed that the live dashboard was running directly on `0.0.0.0:8765` with no reverse proxy and no mounted `/radar` path. That established the real public URL candidate as `http://46.225.113.129:8765/`.

The next problem was operational: the dashboard process looked alive in `systemctl` and `ss`, but it would not answer real HTTP requests. The root cause turned out to be the live database, not the Python process. The VPS was still serving from a giant `data/vinted-radar.db` that had grown to 61 GB and was no longer a credible or responsive serving boundary.

Instead of pretending that file could still support acceptance, I had the operator archive it out of the live path, bootstrap a fresh healthy `data/vinted-radar.clean.db` with one small batch, verify that clean DB with `db-health`, and reinstall the systemd services against the clean DB. After that recovery, the dashboard answered locally again and the public port became reachable from the internet.

With the live URL back, I reran the real public smoke from this environment. `verify_vps_serving.py` passed for overview, explorer, runtime, detail HTML, detail JSON, and health on `http://46.225.113.129:8765/`. I then added direct public content checks for the home, runtime, detail, `/api/runtime`, and `/health` contracts so T03 would not depend only on 200 responses.

One important nuance stayed explicit: the realistic 49,759-listing corpus proof still lives in T02 on the mounted local `m001-closeout.db`. The public VPS proof in T03 is now truthful and internet-facing again, but it runs on the recovered clean DB that is rebuilding from fresh live collection. That is still good enough to close the public-entrypoint gap, and it is more honest than claiming the corrupted 61 GB file was acceptable evidence.

## Verification

Verified the recovered public URL from outside the VPS, confirmed the service now points at `vinted-radar.clean.db`, and confirmed the public HTML and JSON contracts for overview, explorer, runtime, detail, and health.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `./venv/bin/python -m vinted_radar.cli batch --db /root/Vinted/data/vinted-radar.clean.db --page-limit 1 --max-leaf-categories 6 --state-refresh-limit 10` | 0 | PASS | ~71s |
| 2 | `./venv/bin/python -m vinted_radar.cli db-health --db /root/Vinted/data/vinted-radar.clean.db` | 0 | PASS | healthy clean DB |
| 3 | `systemctl status --no-pager vinted-dashboard.service` + `curl -v --max-time 20 http://127.0.0.1:8765/` on the VPS | 0 | PASS | local service now responds 200 |
| 4 | `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111` | 0 | PASS | public overview/explorer/runtime/detail/health smoke |
| 5 | `python - <<'PY' ... urllib public checks for /, /api/runtime, /health, /explorer ... PY` | 0 | PASS | all returned HTTP 200 |
| 6 | `python - <<'PY' ... public text assertions for /, /runtime, /listings/8468335111 ... PY` | 0 | PASS | expected public content present |
| 7 | `python - <<'PY' ... health/runtime contract assertions ... PY` | 0 | PASS | public health/runtime contract valid |

## Diagnostics

The authoritative public entrypoint is now `http://46.225.113.129:8765/`. If it later appears "up" but feels dead, check in this order: `curl http://127.0.0.1:8765/`, `curl http://127.0.0.1:8765/health`, `systemctl status vinted-dashboard.service`, and the size/health of `/root/Vinted/data/vinted-radar.clean.db`. The key lesson from this task is that a listening socket and a green systemd status are not enough; the HTTP routes are the truth.

## Deviations

The written plan assumed T03 would mostly be a straight public rerun. In reality, the live VPS first needed an operational recovery because the real serving DB had swollen into a 61 GB corrupted or otherwise unusable file. I archived that file out of the serving path and proved the public URL on a fresh healthy clean DB instead.

## Known Issues

The public service currently exposes the app directly on `http://46.225.113.129:8765/` without a reverse proxy or auth layer, and because `--public-base-url` is unset the service still advertises `http://0.0.0.0:8765` in its own startup logs. Also, the public proof currently runs on the recovered clean DB rather than the realistic 49,759-listing corpus used in T02.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S07/S07-UAT.md` — updated the slice UAT with the real public VPS proof and the split between realistic-corpus local proof and recovered public proof.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marked S07 complete.
- `.gsd/PROJECT.md` — updated current project state to reflect M002 completion and the recovered public VPS URL.
- `.gsd/REQUIREMENTS.md` — marked R011 validated with the combined S06+S07 proof.
- `.gsd/KNOWLEDGE.md` — recorded the live-DB recovery lesson so future agents do not trust giant broken SQLite files just because the process still listens.
