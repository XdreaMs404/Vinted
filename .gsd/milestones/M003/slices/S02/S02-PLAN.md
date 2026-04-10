# S02: Start-to-Start Multi-Lane Runtime Control

**Goal:** Replace the current finish-plus-sleep loop with a lane-aware start-to-start runtime that can run frontier and expansion work concurrently without losing operator truth.
**Demo:** After this: After this: the runtime can execute named lanes such as frontier and expansion start-to-start, and `/runtime` / CLI surfaces show truthful per-lane state, timers, errors, and current config.

## Tasks
- [x] **T01: Add lane-aware runtime persistence and repository contracts** — Why: The current controller state assumes one continuous loop and cannot describe parallel acquisition lanes truthfully.
Do:
- Extend runtime controller/cycle persistence to represent named lanes, their current config, active cycle, next scheduled start, and latest benchmark label.
- Preserve backward-compatible FR single-lane reads where possible so the migration is observable rather than disruptive.
- Keep pause/resume/failure semantics explicit per lane.
Done when:
- Repository/runtime tests can load, update, and inspect more than one lane without ambiguous current state.
  - Estimate: 1.5h
  - Files: vinted_radar/repository.py, vinted_radar/db.py, tests/test_runtime_repository.py, tests/test_runtime_service.py
  - Verify: python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py -q
- [x] **T02: Added start-to-start per-lane scheduling and a threaded multi-lane runtime orchestrator with lane isolation tests.** — Why: Throughput improvements require fresh-frontier and expansion work to run on deliberate schedules, not on one serialized loop.
Do:
- Rework runtime scheduling so interval semantics are start-to-start.
- Add a lane orchestrator that can run named workload profiles with bounded overlap and clear ownership of proxies/concurrency settings.
- Preserve graceful shutdown and interruption visibility.
Done when:
- Runtime service tests prove start-to-start cadence and multi-lane execution semantics under success, failure, pause, and resume paths.
  - Estimate: 2h
  - Files: vinted_radar/services/runtime.py, tests/test_runtime_service.py, tests/test_runtime_cli.py
  - Verify: python -m pytest tests/test_runtime_service.py tests/test_runtime_cli.py -q
- [x] **T03: Added lane-aware runtime-status output and /api/runtime summaries with redacted per-lane config and failure visibility.** — Why: The new runtime contract is not usable if operators cannot inspect and control it through the existing surfaces.
Do:
- Extend CLI runtime commands and runtime/dashboard payloads to show lane-level status, timers, configs, benchmark labels, and last errors.
- Keep the public operator surfaces lightweight so they do not reintroduce request-path stalls under load.
- Add explicit failure visibility for one broken lane without hiding healthy sibling lanes.
Done when:
- CLI and runtime/dashboard tests prove lane-level truth and redaction-safe config rendering.
  - Estimate: 1.5h
  - Files: vinted_radar/cli.py, vinted_radar/dashboard.py, tests/test_runtime_cli.py, tests/test_dashboard.py
  - Verify: python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py -q
- [x] **T04: Prove the lane runtime on the VPS** — Why: The slice is not retired until the runtime contract survives on the real VPS.
Do:
- Run a bounded dual-lane smoke on the VPS using conservative frontier + expansion configs.
- Verify that `/runtime`, `/api/runtime`, `/health`, and the benchmark artifact bundle all stay truthful while both lanes run.
- Record any operator-facing surprises before later slices build on the lane model.
Done when:
- The repo has a VPS smoke artifact proving real dual-lane operation and healthy serving/runtime surfaces.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, scripts/verify_vps_serving.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile dual-lane-smoke --duration-minutes 30 --verify-base-url http://46.225.113.129:8765 --output .gsd/milestones/M003/benchmarks/dual-lane-smoke.json --markdown .gsd/milestones/M003/benchmarks/dual-lane-smoke.md
