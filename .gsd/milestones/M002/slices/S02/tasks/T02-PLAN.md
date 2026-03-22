---
estimated_steps: 4
estimated_files: 5
skills_used:
  - debug-like-expert
  - code-optimizer
  - best-practices
  - test
  - review
---

# T02: Make continuous runtime and CLI controls honor the persisted controller truth

**Slice:** S02 — Runtime Truth + Pause/Resume Surface
**Milestone:** M002

## Description

Load `debug-like-expert`, `test`, and `review` before coding. This task turns the new controller contract into truthful runtime behavior. The current loop sleeps blindly between cycles, so it cannot persist a scheduled window or notice a pause request until the entire interval expires. Replace that with cooperative scheduling, then make the CLI mutate and display the same DB-backed truth.

## Steps

1. Rework `RadarRuntimeService.run_continuous()` in `vinted_radar/services/runtime.py` to persist controller transitions for running, scheduled, paused, and failed states, replacing the one-shot sleep with a short poll/heartbeat wait loop and explicit resume metadata handling.
2. Define cooperative pause semantics: if pause is requested mid-cycle, finish the current cycle, then enter `paused`; when resumed, clear pause metadata and return to scheduled/running truth using the configured interval.
3. Extend `vinted_radar/cli.py` with pause/resume commands plus richer `runtime-status` output/JSON that consumes the repository contract instead of reconstructing state from cycle rows.
4. Expand `tests/test_runtime_service.py` and `tests/test_runtime_cli.py` to prove scheduled windows, pause during wait, resume, and failure vs controller-state separation.

## Must-Haves

- [ ] Continuous mode persists a truthful scheduled window between cycles and refreshes controller heartbeat data while waiting.
- [ ] Pause requests are observed without waiting the full interval and resume restores truthful scheduling state.
- [ ] CLI control/status surfaces read and write the repository-owned controller contract, not ad-hoc inferred state.

## Verification

- `python -m pytest tests/test_runtime_service.py tests/test_runtime_cli.py`
- `python -m pytest tests/test_runtime_service.py -k continuous`

## Observability Impact

- Signals added/changed: controller state transitions, waiting heartbeat updates, pause/resume timestamps, and operator-visible last-error/current-status output.
- How a future agent inspects this: run `python -m vinted_radar.cli runtime-status --db ... --format json`, exercise `runtime-pause` / `runtime-resume`, and rerun the runtime service/CLI regression tests.
- Failure state exposed: a loop stuck in scheduled, a missed pause request, or a failure that still plans a retry becomes visible as controller-state drift instead of being hidden behind the last completed cycle row.

## Inputs

- `vinted_radar/services/runtime.py` — existing continuous loop with one blocking sleep that must become cooperative.
- `vinted_radar/cli.py` — current batch/continuous/runtime-status operator surface that needs pause/resume control and richer status output.
- `vinted_radar/repository.py` — T01 controller snapshot helpers and runtime-status contract consumed by the service and CLI.
- `tests/test_runtime_service.py` — current runtime orchestration coverage that should expand to scheduled/paused/resumed truth.
- `tests/test_runtime_cli.py` — current CLI coverage for batch/continuous/runtime-status that should grow to pause/resume and richer status output.
- `tests/test_runtime_repository.py` — T01 contract assertions that define what the service/CLI may rely on.

## Expected Output

- `vinted_radar/services/runtime.py` — cooperative scheduling/heartbeat/pause-resume runtime orchestration.
- `vinted_radar/cli.py` — pause/resume commands and controller-backed runtime status output.
- `vinted_radar/repository.py` — any additional controller helper methods needed by the CLI/runtime loop.
- `tests/test_runtime_service.py` — regression coverage for scheduled windows, pause/resume, and failure-state truth.
- `tests/test_runtime_cli.py` — regression coverage for CLI pause/resume commands and richer controller-backed runtime status output.
