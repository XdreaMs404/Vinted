---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: Add lane-aware runtime persistence and repository contracts

Why: The current controller state assumes one continuous loop and cannot describe parallel acquisition lanes truthfully.
Do:
- Extend runtime controller/cycle persistence to represent named lanes, their current config, active cycle, next scheduled start, and latest benchmark label.
- Preserve backward-compatible FR single-lane reads where possible so the migration is observable rather than disruptive.
- Keep pause/resume/failure semantics explicit per lane.
Done when:
- Repository/runtime tests can load, update, and inspect more than one lane without ambiguous current state.

## Inputs

- `vinted_radar/services/runtime.py`
- `vinted_radar/repository.py`

## Expected Output

- `lane-aware runtime controller schema`
- `tests/test_runtime_repository.py lane coverage`

## Verification

python -m pytest tests/test_runtime_repository.py tests/test_runtime_service.py -q
