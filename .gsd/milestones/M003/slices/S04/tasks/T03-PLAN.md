---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T03: Wire benchmark-selected transport profiles into runtime and CLI

Why: Once a winner exists, runtime commands need a safe way to use it while still allowing explicit overrides during experiments.
Do:
- Add transport profile selection to CLI/runtime configuration and artifact rendering.
- Make the chosen recipe visible in runtime/benchmark outputs and keep overrides explicit for auditability.
- Preserve safe defaults when no winner has been chosen yet.
Done when:
- Runtime tests prove recommended profiles and explicit overrides both work and remain inspectable.

## Inputs

- `vinted_radar/cli.py`
- `vinted_radar/services/runtime.py`

## Expected Output

- `runtime transport-profile selection`
- `inspectable winner/override rendering`

## Verification

python -m pytest tests/test_runtime_cli.py tests/test_runtime_service.py -q
