---
title: M002 VPS Shadow Rollout Handoff
updated_at: 2026-04-09T07:50:40+00:00
status: active
scope: vps-shadow-rollout
---

# M002 VPS Shadow Rollout Handoff

## Why this file exists

This file keeps the current VPS deployment/debug state for the post-M002 shadow rollout so future discussions can resume from the real operational position instead of re-reading the full milestone history.

## Current validated state

### 2026-04-09 remediation follow-up
- Deployed a bounded embedded-audit fix to the VPS and restarted the affected services safely:
  - uploaded updated `vinted_radar/services/platform_audit.py`, `vinted_radar/dashboard.py`, and `vinted_radar/cli.py`
  - normalized both systemd cutover drop-ins so they now contain only the intended `Environment=...` lines
  - reloaded systemd
  - restarted `vinted-dashboard.service`, then restarted `vinted-scraper.service` after the shadow control-plane fix landed
- Public dashboard responsiveness is restored:
  - `curl http://127.0.0.1:8765/health` now returns JSON immediately on the VPS
  - `curl http://127.0.0.1:8765/api/runtime` now returns JSON immediately on the VPS
  - external `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8602288517 --expected-cutover-mode dual-write-shadow` now passes again for overview, explorer, runtime, listing detail, runtime API, detail API, and health
- Root cause/fix split that is now live on the VPS:
  1. `/health`, `/runtime`, `/api/runtime`, and CLI `runtime-status` no longer run the full cross-store reconciliation inline. They now use an **embedded bounded audit snapshot** that keeps current-state/analytical/lifecycle/backfill checkpoint visibility but defers the expensive reconciliation scan to the explicit `platform-audit` command.
  2. Shadow-mode runtime control-plane writes were corrected back to SQLite. In `dual-write-shadow`, batch/continuous/runtime-status now keep runtime cycles and controller truth in SQLite instead of silently switching that control plane to PostgreSQL just because PostgreSQL writes are enabled.
- The runtime truth surface is now live again in SQLite after the scraper restart:
  - `runtime-status` with the shadow env vars set now reports `status: running`, `phase: discovery`, and a live `controller` / `latest_cycle` row in SQLite
  - `/health` now reports `current_runtime_status: running` and a non-null `latest_runtime_cycle`
  - `/api/runtime` now reports `status: running` instead of `null`
- Post-fix health signals:
  - `vinted-dashboard.service` active/running with start time **`2026-04-09 07:41:19 UTC`**
  - `vinted-scraper.service` active/running with start time **`2026-04-09 07:48:37 UTC`**
  - no new `ForeignKeyViolation`, `cannot adapt type 'dict'`, traceback, or runtime FK signatures were found in the last 10 minutes of scraper/dashboard journal output after the redeploy
- Current operator interpretation:
  - the **shadow soak is healthy again**
  - the **public product routes are healthy again**
  - the embedded audit on runtime/health is intentionally lighter than the authoritative `platform-audit` CLI; full reconciliation/backfill parity is still a separate explicit operator check, not an on-request web-path responsibility

### 2026-04-09 internal follow-up
- SSH access from this workstation was restored and VPS-side checks were rerun directly.
- `systemd` still reports both services as active since **`2026-04-08 21:53:50 UTC`**:
  - `vinted-dashboard.service` → PID `297198`
  - `vinted-scraper.service` → PID `297199`
- The scraper is still doing real work. `journalctl -u vinted-scraper.service` showed a completed cycle at **`2026-04-09 07:12:35 UTC`** with:
  - `38845 sightings, 38271 unique IDs`
  - `405 successful scans, all scans clean`
  - `State probes: 6 / 6`
  - `State refresh health: healthy | direct 6 | inconclusive 0 | degraded 0`
  - `Tracked listings: 65993`
- The live SQLite DB is healthy and readable:
  - `./venv/bin/python -m vinted_radar.cli db-health --db data/vinted-radar.clean.db --integrity` passed
  - DB size at check time: **`940081152` bytes**
  - `runtime_cycles` and `runtime_controller_state` are still empty in SQLite, which matches the already-known shadow-mode control-plane wiring caveat.
- The dashboard hang is real on the VPS itself, not just from outside:
  - `curl -sS -m 15 http://127.0.0.1:8765/health` timed out with **0 bytes received**
  - `timeout 20s ./venv/bin/python -m vinted_radar.cli runtime-status --db data/vinted-radar.clean.db --format json` also timed out
- Isolation checks narrowed the hang to the platform-audit path rather than to SQLite health or the scraper:
  - `platform-doctor --format json` returns quickly and reports PostgreSQL/ClickHouse/object storage healthy.
  - `clickhouse-ingest-status --format json` returns quickly (`never-run`, as expected).
  - `platform-lifecycle --dry-run --format json` returns quickly.
  - `platform-reconcile --db data/vinted-radar.clean.db --format json` times out after 20 seconds.
  - `platform-audit --db data/vinted-radar.clean.db --format json` times out after 20 seconds.
- Code-level diagnosis from the repo matches the observed runtime behavior:
  - `dashboard.py` serves via single-threaded `wsgiref.simple_server` and calls `load_platform_audit_snapshot(...)` synchronously on `/runtime` and `/health`.
  - `load_platform_audit_snapshot(...)` calls `run_platform_audit(...)`, which calls `run_reconciliation(...)`.
  - `run_reconciliation(...)` currently scans object-storage manifests and reads Parquet rows batch-by-batch in `_object_storage_dataset_snapshot(...)`; on this VPS the lifecycle dry-run already sees **6093** objects under the evidence prefixes, so reconciliation is too heavy for an on-request health/runtime path.
  - Practical effect: one slow `/health` or `/runtime` request can wedge the entire public app because the dashboard server is single-threaded.
- `journalctl -u vinted-dashboard.service` confirms the timeline: the last successful dashboard responses were around **`06:53 UTC`** (`/health` still 200 then); after that, newer requests stopped completing, which matches one blocking request pinning the single worker.
- The malformed systemd drop-in is still present and should be cleaned up separately. `/etc/systemd/system/vinted-scraper.service.d/platform.conf` still contains leftover heredoc/command text after the `Environment=...` lines, which explains the earlier `Missing '='` parser warnings.
- Operational conclusion: the **shadow collector soak itself is still healthy**, but the **public dashboard/health surface is no longer trustworthy** because `platform-audit`/`platform-reconcile` are being executed synchronously inside the single-threaded request path.

### 2026-04-09 external follow-up
- From this workstation, the public VPS socket on **`46.225.113.129:8765`** still accepts TCP connections quickly (`connect ok` in ~50 ms), so the host/port is reachable.
- Public HTTP checks are currently unhealthy from the outside:
  - `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111 --expected-cutover-mode dual-write-shadow` timed out before the first response.
  - direct GET probes to `/health`, `/api/runtime`, and `/` timed out with **no bytes received**, including a `/health` probe left open for 90 seconds.
  - `curl -v --max-time 20 http://46.225.113.129:8765/health` confirmed the TCP connection opens and the request is sent, but no HTTP response arrives before timeout.
- Operational meaning: the soak test is no longer in a externally healthy/proven state. Until VPS-side logs are checked again, treat this as **needs-attention** rather than assuming the 2026-04-08 healthy spot check is still representative.

### 2026-04-08 systemd soak-test start
- `vinted-dashboard.service` and `vinted-scraper.service` were restarted successfully under systemd.
- Both services point to **`/root/Vinted/data/vinted-radar.clean.db`**.
- `vinted-scraper.service` is running `continuous --db /root/Vinted/data/vinted-radar.clean.db --page-limit 1 --state-refresh-limit 6 --interval-seconds 1800`.
- The first post-restart `platform-audit` still showed the expected red posture (`analytical: never-run`, `backfill: not-run`, `current_state: never-run`, reconciliation mismatch).
- That same audit also showed fresh SQLite discovery activity up to `2026-04-08T21:53:56+00:00`, which means the service started doing real work immediately after restart.
- A manual 10-minute spot check later showed the first long `continuous` cycle completed successfully under systemd:
  - `405 successful scans, all scans clean`
  - `38835 sightings, 38269 unique IDs`
  - `State probes: 6 / 6`
  - `State refresh health: healthy | direct 6 | inconclusive 0 | degraded 0`
  - `Tracked listings: 38330`
- SQLite growth check at that point showed:
  - `discovery_runs = 8`
  - `max(discovery_runs.started_at) = 2026-04-08T21:53:51+00:00`
  - `listing_discoveries = 39219`
  - `max(listing_discoveries.observed_at) = 2026-04-08T21:53:56+00:00`
- No return of the earlier fatal signatures was seen in that spot check (`ForeignKeyViolation`, `cannot adapt type 'dict'`, runtime crash traceback).
- Caveat: `systemd` logged `Missing '='` warnings while parsing `/etc/systemd/system/vinted-scraper.service.d/platform.conf`, so the drop-in file should be cleaned up before treating the systemd environment as pristine. The collector itself still ran successfully despite those malformed lines.

### Platform foundation
- PostgreSQL, ClickHouse, and MinIO/object storage bootstrap and doctor checks were brought back to green on the VPS.
- `platform-bootstrap` and `platform-doctor` already proved the platform stack itself is healthy.
- The live SQLite database on the VPS is **`data/vinted-radar.clean.db`**.
- The old huge live SQLite file was deleted intentionally to recover disk and simplify operations.
- Current disk posture after reset: roughly **57 GB free**.

### Shadow-mode contract currently in force
- `VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES=true`
- `VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES=true`
- `VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES=true`
- `VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=false`

Interpretation:
- writes go to SQLite + PostgreSQL + ClickHouse outbox/object storage paths
- operator/runtime reads still stay on SQLite
- this is **dual-write shadow**, not full cutover

### Code fixes already pushed during the VPS rollout
- `ad8bca1` — Fix ClickHouse 25.1 V002 migration compatibility
- `d8ea87a` — Allow nullable keys in ClickHouse rollup tables
- `d0ffaa4` — Stop synthetic Postgres mutable-truth event refs
- `e367c2c` — Use mapping rows for Postgres mutable truth
- `90e572f` — Handle decoded JSONB rows in mutable truth
- `c3fc496` — Materialize synthetic mutable-truth events
- `29eafbb` — Materialize mutable manifests for direct discovery projection
- `d9a6f30` — Bootstrap probe projections without prior identity rows
- `4bf6db4` — Normalize decoded current-state JSONB on replay

### Root cause that was fixed last
The final VPS crash was:
- `cannot adapt type 'dict' using placeholder '%s'`

Actual cause:
- an existing PostgreSQL `platform_listing_current_state` row could return `state_explanation_json` already decoded as a Python `dict`
- discovery projection then reused that row and tried to write the decoded dict back through SQL placeholders
- psycopg rejected that raw dict during replay

Fix:
- normalize `listing_current_state()` hydration and current-state upsert inputs so JSONB is re-encoded safely before write-back
- regression test added in `tests/test_postgres_repository_projections.py`

### Latest VPS proof after the final fix
After pulling `4bf6db4`, the following command succeeded on the VPS:

```bash
./venv/bin/python -m vinted_radar.cli batch --db data/vinted-radar.clean.db --page-limit 1 --max-leaf-categories 1 --state-refresh-limit 2
```

Observed result:
- cycle completed successfully
- discovery succeeded
- state probes succeeded
- no `ForeignKeyViolation`
- no `cannot adapt type 'dict'`
- no mutable-truth crash in the collector path

Sample success signals from that run:
- `Status: completed (phase completed)`
- `Discovery: 96 sightings, 96 unique IDs, 1 successful scans, all scans clean`
- `State probes: 2 / 2`
- `State refresh health: healthy | direct 2 | inconclusive 0 | degraded 0`

## Important interpretation of the latest platform-audit output

`platform-audit --format json` still returned `ok: false`, but this no longer means the shadow write path is broken.

### What the red audit means now
1. **Historical parity is still missing**
   - PostgreSQL row counts do not yet match the full SQLite corpus.
   - This is expected without a full historical backfill.

2. **ClickHouse ingest checkpoint has not been advanced yet**
   - `analytical.status = never-run`
   - this means the ClickHouse outbox consumer has not been run yet

3. **Object-storage reconciliation is misleading in this context**
   - the audit currently counts only manifests with `capture_source=sqlite_backfill`
   - live dual-write shadow batches do not make that section go green

4. **Current-state checkpoint semantics are stricter than the direct shadow path**
   - the audit expects the separate `postgres-current-state-projector` checkpoint
   - a healthy direct shadow write path does not, by itself, satisfy that checkpoint

### Operational conclusion
A successful shadow `batch`/`continuous` run with clean logs and growing PostgreSQL mutable-truth rows is currently the real proof that shadow writes work on the VPS.

Do **not** treat the current red `platform-audit` result as proof that the latest mutable-truth fixes failed.

## Remaining work

### Immediate next work
1. Run a real long-duration shadow soak test (recommended: 8 hours).
2. Confirm the collector remains stable over time:
   - no crashes
   - no FK regressions
   - no JSON adaptation regressions
   - runtime cycles keep completing
3. Restart the systemd services for normal operation once the soak-test approach is chosen.

### Separate work not yet closed
These are different from “does shadow writing work?”

1. **Historical parity / backfill**
   - needed if the goal is PostgreSQL/ClickHouse/object-storage parity with the full SQLite history
   - likely path: `full-backfill`

2. **ClickHouse analytical consumer proof**
   - needed if the goal is a non-`never-run` analytical checkpoint
   - likely path: `clickhouse-ingest`

3. **Current-state audit checkpoint/orchestration gap**
   - needed if the goal is a fully green `platform-audit`
   - current audit semantics expect the `postgres-current-state-projector` checkpoint, while the observed VPS proof came from direct shadow writes

### Safe service-side next step after choosing to proceed
```bash
systemctl daemon-reload
systemctl start vinted-dashboard.service vinted-scraper.service
```

## Known pitfalls

### Terminal behavior
- The VPS shell has repeatedly broken multiline pasted commands.
- The `batch` command must be pasted on **one single line**.
- Avoid heredocs and long pasted blocks where possible.

### Correct database
- The real active DB for this rollout is **`data/vinted-radar.clean.db`**.
- `data/vinted-radar.db` is not the live proof source for this shadow validation.

### Audit interpretation
- A red `platform-audit` after a healthy live shadow batch does **not** necessarily mean the live shadow write path is broken.
- Use logs + runtime status + PostgreSQL growth as the primary signal for this rollout stage.

### Current runtime-monitoring caveat
- The current build still wires `continuous` to the PostgreSQL control-plane repository whenever PostgreSQL writes are enabled, even in `dual-write-shadow`.
- `runtime-status` in shadow mode still reads SQLite, so it can report `No runtime cycles recorded yet.` while the scraper is actually running and writing discovery rows.
- For the current soak test, treat `journalctl` plus growth in SQLite discovery tables as the primary signal until that control-plane wiring is corrected in the repo.

## Recommended 8-hour shadow soak test

### Goal
Validate that the VPS collector can run for 8 hours in dual-write shadow mode without crashing and while continuing to write truthfully to SQLite and PostgreSQL.

### Recommended mode
Use the real systemd service if it is already configured for the clean DB and the shadow env vars. This is the most honest production-like test.

### Start the test
```bash
systemctl daemon-reload
systemctl restart vinted-dashboard.service vinted-scraper.service
systemctl --no-pager --full status vinted-dashboard.service vinted-scraper.service
```

### Baseline checks at start
```bash
./venv/bin/python -m vinted_radar.cli runtime-status --db data/vinted-radar.clean.db --format json
./venv/bin/python -m vinted_radar.cli platform-audit --db data/vinted-radar.clean.db --format json
```

Keep the initial outputs if you want before/after comparison.

### During the 8 hours
Check every 30 to 60 minutes:

```bash
./venv/bin/python -m vinted_radar.cli runtime-status --db data/vinted-radar.clean.db
```

and:

```bash
journalctl -u vinted-scraper.service --since "60 min ago" --no-pager
```

### What to look for in logs
Healthy signs:
- cycles continue
- no repeated stack traces
- discovery continues to finish
- state refresh continues to finish
- no persistent anti-bot collapse beyond what degraded-mode already reports

Bad signs to grep for explicitly:
- `ForeignKeyViolation`
- `cannot adapt type 'dict'`
- `Traceback`
- `RuntimeError`
- `platform_runtime_cycles_last_event_id_fkey`
- `platform_discovery_runs_last_event_id_fkey`
- `platform_listing_identity_last_manifest_id_fkey`
- `platform_listing_current_state_listing_id_fkey`

Practical filter:
```bash
journalctl -u vinted-scraper.service --since "8 hours ago" --no-pager | egrep "ForeignKeyViolation|cannot adapt type|Traceback|RuntimeError|last_event_id_fkey|last_manifest_id_fkey|listing_current_state_listing_id_fkey"
```

### End-of-test checks
At the end of 8 hours:

```bash
./venv/bin/python -m vinted_radar.cli runtime-status --db data/vinted-radar.clean.db --format json
./venv/bin/python -m vinted_radar.cli platform-audit --db data/vinted-radar.clean.db --format json
```

Optional downstream analytical check:
```bash
./venv/bin/python -m vinted_radar.cli clickhouse-ingest --format json
./venv/bin/python -m vinted_radar.cli clickhouse-ingest-status --format json
```

### Success criteria for the 8-hour shadow test
Treat the test as successful if all of the following are true:

1. `vinted-scraper.service` stays up for the full period.
2. `runtime-status` shows completed cycles and no growing failure pattern.
3. scraper logs contain no new FK violation and no new JSON adaptation error.
4. the collector continues to discover listings and execute state refresh normally.
5. the PostgreSQL shadow side shows ongoing activity, even if `platform-audit` remains globally red because parity/backfill is not finished.

### What would make the test fail
- service crash or restart loop
- recurring collector exception in logs
- any return of the previous FK failures
- any return of `cannot adapt type 'dict'`
- runtime cycles stop advancing while the service still appears nominally started

## Recommended next discussion starting point
For the next discussion, read this file first together with:
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/M002-VALIDATION.md`
- `vinted_radar/services/platform_audit.py`
- `vinted_radar/services/reconciliation.py`

Then decide explicitly between two goals:
1. **Shadow stability proof** — keep dual-write shadow, run the 8h soak, and confirm collector stability.
2. **Audit green / cutover proof** — close backfill, downstream consumers, and current-state checkpoint semantics.
