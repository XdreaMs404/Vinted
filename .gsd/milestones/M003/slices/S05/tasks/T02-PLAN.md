---
estimated_steps: 7
estimated_files: 5
skills_used: []
---

# T02: Wire adaptive frontier strategies into discovery and runtime

Why: The planner only matters if runtime and discovery can consume it to decide depth and lane budgets dynamically.
Do:
- Wire adaptive page-budget allocation and lane strategies into discovery/runtime.
- Support distinct frontier, expansion, and optional backfill strategies while preserving per-lane truth.
- Keep a deterministic fallback profile for debugging and baseline comparison.
Done when:
- Runtime/discovery tests prove adaptive and fixed strategies can both execute and remain inspectable.

## Inputs

- `vinted_radar/services/discovery.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/services/frontier_planner.py`

## Expected Output

- `adaptive frontier runtime integration`
- `lane strategy config contract`

## Verification

python -m pytest tests/test_discovery_service.py tests/test_runtime_service.py tests/test_runtime_cli.py -q
