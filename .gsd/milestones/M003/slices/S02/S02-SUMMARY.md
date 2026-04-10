---
id: S02
parent: M003
milestone: M003
provides:
  - Lane-aware runtime persistence and controller state for named acquisition lanes.
  - Start-to-start per-lane scheduling plus threaded multi-lane orchestration with lane isolation and fail-fast control-plane guards.
  - Lane-aware CLI/dashboard/runtime surfaces with redacted per-lane config, benchmark labels, timers, and failure visibility.
  - A canonical 30-minute VPS proof bundle showing concurrent `frontier` + `expansion` operation with truthful serving/runtime surfaces.
requires:
  - slice: S01
    provides: acquisition benchmark scorecards, CLI/report substrate, and the VPS runner artifact pattern reused by the dual-lane smoke proof
affects:
  - S03
  - S04
  - S05
  - S07
key_files:
  - vinted_radar/db.py
  - vinted_radar/repository.py
  - vinted_radar/services/runtime.py
  - vinted_radar/cli.py
  - vinted_radar/dashboard.py
  - scripts/run_vps_benchmark.py
  - tests/test_runtime_repository.py
  - tests/test_runtime_service.py
  - tests/test_runtime_cli.py
  - tests/test_dashboard.py
  - tests/test_vps_benchmark_runner.py
  - .gsd/milestones/M003/benchmarks/dual-lane-smoke.json
  - .gsd/milestones/M003/benchmarks/dual-lane-smoke.md
key_decisions:
  - D053 — implement multi-lane runtime as one sequential start-to-start scheduler per lane coordinated by a threaded supervisor, with shared control-plane access serialized and non-lane-aware control planes rejected for multi-lane runs.
  - D054 — keep authoritative per-lane controller state in `runtime_lane_controller_state` and project the legacy singleton controller view from the default/frontier lane only.
  - D055 — serialize file-backed SQLite runtime bootstrap per path with a busy timeout so multi-lane startup does not deadlock on fresh DB initialization.
  - D056 — force explicit multi-lane benchmark windows to start each lane immediately and derive global runtime truth from active lane views instead of the legacy singleton controller projection alone.
patterns_established:
  - Explicit live benchmark windows must schedule their benchmark lanes immediately instead of inheriting a persisted future `next_resume_at` from the steady-state controller.
  - Top-level runtime truth during multi-lane windows must aggregate from active lane views; the legacy singleton controller projection is not sufficient for `/health` or other global status surfaces during concurrent proof windows.
  - Multi-lane VPS proof should avoid remote snapshot export churn and treat orphaned `*.benchmark-export-*.db` files as disposable residue, because repeated interrupted exports can fill `/root/Vinted/data` and wedge Docker PostgreSQL.
observability_surfaces:
  - python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_vps_benchmark_runner.py tests/test_http.py -q
  - python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile dual-lane-smoke --duration-minutes 30 --verify-base-url http://46.225.113.129:8765 --output .gsd/milestones/M003/benchmarks/dual-lane-smoke.json --markdown .gsd/milestones/M003/benchmarks/dual-lane-smoke.md
  - python - <<'PY' ... dual-lane bundle + serving assertions ... PY
  - http://46.225.113.129:8765/runtime
  - http://46.225.113.129:8765/api/runtime
  - http://46.225.113.129:8765/health
drill_down_paths:
  - .gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-10T09:17:53.468Z
blocker_discovered: false
---

# S02: Start-to-Start Multi-Lane Runtime Control

**Delivered a lane-aware start-to-start runtime with a real 30-minute dual-lane VPS proof bundle and repaired the runner/VPS failure modes that had kept S02 open.**

## What Happened

S02 replaced the old finish-plus-sleep runtime posture with a lane-aware start-to-start orchestration model and then proved that model on the live VPS.

T01 and T02 established the runtime/control-plane core: `runtime_cycles` and controller state now understand named lanes, the legacy singleton controller view remains compatible for frontier-facing brownfield reads, and the runtime service coordinates one sequential scheduler per lane through a threaded supervisor. T03 lifted that truth into the operator surfaces so `/runtime`, `/api/runtime`, and CLI `runtime-status` can show lane-level status, timing, benchmark labels, config, and failures without hiding healthy sibling lanes.

T04 then retired the real operational unknowns on the VPS. The first closeout attempt had not merely "timed out"; the log showed several stacked failures. Auto-mode had been misled by a partial `S02-SUMMARY.md`, long benchmark attempts had left many orphaned `vinted-radar.clean.benchmark-export-*.db` files on the VPS, `/root/Vinted/data` filled completely, Docker PostgreSQL entered a `No space left on device` recovery loop, and explicit benchmark windows could still inherit a far-future `next_resume_at` from the live controllers and wait through most of their proof window instead of starting immediately. On top of that, the serving verifier was comparing `/runtime`, `/api/runtime`, and `/health` as strictly if they were one atomic read, which turned healthy state transitions between sequential requests into false "drift" failures.

I fixed those actual blockers instead of papering over them. The benchmark path now forces explicit multi-lane proof windows to start their lanes immediately, top-level runtime truth aggregates from active lane views during multi-lane windows, the serving verifier tolerates healthy transition races while still failing real route/health breakage, and the multi-lane proof path avoids remote snapshot export churn. On the VPS I deleted the orphaned benchmark exports and stale helper scripts, which immediately freed the disk and let `infra-postgres-1` recover, then resynced the updated runtime/repository code and restarted the public services.

With those repairs in place, the exact task-plan command finally produced the canonical proof bundle at `.gsd/milestones/M003/benchmarks/dual-lane-smoke.json` / `.md`. The final live window ran from `2026-04-10T08:51:06+00:00` to `2026-04-10T09:06:37+00:00`, completed two `frontier` cycles and two `expansion` cycles, kept `remote_result.ok == true`, and captured `serving_verification.ok == true` with both lanes observed concurrently during the benchmark. After the run, the VPS returned cleanly to its steady-state posture with both `vinted-dashboard.service` and `vinted-scraper.service` active again.

## Verification

Local closeout verification is green (`67 passed` across the runtime repository/service/CLI/dashboard, VPS benchmark runner, and transport retry packs), the exact 30-minute task-plan benchmark command produced the canonical `dual-lane-smoke.json` / `.md` bundle with `remote_result.ok == true` and `serving_verification.ok == true`, and a final assertion command confirmed that `/runtime`, `/api/runtime`, and `/health` all returned HTTP 200 after the proof run restored the normal VPS service posture.

## Requirements Advanced

- R010 — S02 turned runtime control from one opaque loop into lane-aware persisted operator truth with explicit timers, current config, benchmark labels, and per-lane errors across CLI, dashboard, and the live VPS proof bundle.
- R004 — S02 made lane-specific failures visible without hiding healthy siblings and kept that truth observable through `/runtime`, `/api/runtime`, `/health`, and the benchmark-runner bundle.

## Requirements Validated

- R010 — `python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py tests/test_runtime_cli.py tests/test_dashboard.py tests/test_vps_benchmark_runner.py tests/test_http.py -q` plus `.gsd/milestones/M003/benchmarks/dual-lane-smoke.json` now prove truthful lane-aware operability on the live VPS and through the local regression packs.
- R004 — The canonical `dual-lane-smoke.json` bundle records both lanes, per-lane cycle outcomes, and `serving_verification.ok == true`, while the runtime/dashboard regression packs keep failure visibility explicit without collapsing sibling-lane truth.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T04 was not a simple one-shot benchmark. Closing the slice required removing three real blockers first: explicit live benchmark windows were inheriting a far-future `next_resume_at` from the live controller instead of starting immediately, repeated interrupted benchmark exports had filled `/root/Vinted/data` and pushed Docker PostgreSQL into `No space left on device` recovery loops, and the serving verifier was treating healthy transition races between sequential `/runtime` → `/api/runtime` → `/health` reads as hard failures. The slice stayed in scope, but the final proof depended on repairing those execution-path issues before rerunning the exact 30-minute command.

## Known Limitations

The public VPS steady-state service remains single-lane outside the explicit benchmark window, so future multi-lane acceptance still depends on the dedicated benchmark runner rather than the normal systemd service posture. The proof bundle is trustworthy, but benchmark retention on the VPS still needs an explicit cleanup policy to avoid another disk-pressure incident if later runs are interrupted.

## Follow-ups

Add explicit retention/cleanup for orphaned benchmark exports on the VPS before later M003 slices increase the number of live benchmark windows, so disk pressure cannot silently wedge Docker PostgreSQL again. Keep the dedicated benchmark runner as the multi-lane proof path until a steady-state multi-lane service is intentionally introduced in a later slice.

## Files Created/Modified

- `vinted_radar/db.py` — Moved lane-aware bootstrap/index creation behind migration-safe bootstrap guards and serialized file-backed SQLite bootstrap per path to prevent lane-start lock contention.
- `vinted_radar/repository.py` — Persisted lane-aware controller truth, aggregated top-level runtime status from active lane views for multi-lane windows, and kept the legacy singleton projection for backward-compatible frontier reads.
- `vinted_radar/services/runtime.py` — Added immediate-start support for explicit benchmark-triggered lanes so live proof windows do not inherit a far-future `next_resume_at` from the steady-state controller.
- `scripts/run_vps_benchmark.py` — Extended the benchmark runner to use the immediate-start multi-lane path, keep multi-lane runs on remote facts/no-snapshot export, and tolerate healthy endpoint transition races during serving verification.
- `tests/test_runtime_repository.py` — Added regression coverage for migration-safe runtime bootstrap, immediate-start continuous runs, aggregate runtime truth, and serving-verifier transition tolerance.
- `tests/test_runtime_service.py` — Added regression coverage for immediate benchmark lane starts over an existing future schedule.
- `tests/test_vps_benchmark_runner.py` — Added runner coverage for transition-tolerant serving verification and the repaired dual-lane proof contract.
- `.gsd/KNOWLEDGE.md` — Recorded the VPS benchmark-export disk-pressure recovery lesson for future operators and agents.
- `.gsd/milestones/M003/benchmarks/dual-lane-smoke.json` — Canonical 30-minute live dual-lane proof bundle proving two completed cycles per lane with `serving_verification.ok == true`.
- `.gsd/milestones/M003/benchmarks/dual-lane-smoke.md` — Human-readable closeout summary for the canonical 30-minute live dual-lane proof bundle.
