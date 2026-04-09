---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T03: Expose lane-aware status through CLI and runtime surfaces

Why: The new runtime contract is not usable if operators cannot inspect and control it through the existing surfaces.
Do:
- Extend CLI runtime commands and runtime/dashboard payloads to show lane-level status, timers, configs, benchmark labels, and last errors.
- Keep the public operator surfaces lightweight so they do not reintroduce request-path stalls under load.
- Add explicit failure visibility for one broken lane without hiding healthy sibling lanes.
Done when:
- CLI and runtime/dashboard tests prove lane-level truth and redaction-safe config rendering.

## Inputs

- `vinted_radar/cli.py`
- `vinted_radar/dashboard.py`

## Expected Output

- `lane-aware runtime-status output`
- `lane-aware `/api/runtime` payload`

## Verification

python -m pytest tests/test_runtime_cli.py tests/test_dashboard.py -q
