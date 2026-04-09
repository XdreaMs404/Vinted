---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T02: Implement start-to-start scheduling and multi-lane orchestration

Why: Throughput improvements require fresh-frontier and expansion work to run on deliberate schedules, not on one serialized loop.
Do:
- Rework runtime scheduling so interval semantics are start-to-start.
- Add a lane orchestrator that can run named workload profiles with bounded overlap and clear ownership of proxies/concurrency settings.
- Preserve graceful shutdown and interruption visibility.
Done when:
- Runtime service tests prove start-to-start cadence and multi-lane execution semantics under success, failure, pause, and resume paths.

## Inputs

- `vinted_radar/services/runtime.py`
- `tests/test_runtime_service.py`

## Expected Output

- `start-to-start scheduler`
- `lane orchestrator in runtime service`

## Verification

python -m pytest tests/test_runtime_service.py tests/test_runtime_cli.py -q
