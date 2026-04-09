---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T03: Bound hot-history retention and surface it in audit diagnostics

Why: Even compact writes need bounded retention and explicit archive rules if the new throughput target is going to hold over time.
Do:
- Extend lifecycle/retention controls to cover the hot-path history this milestone still needs locally.
- Make retained-history policy and archive behavior visible through audit surfaces.
- Verify that product/runtime reads still succeed after pruning/archive thresholds are applied.
Done when:
- Lifecycle and audit tests prove bounded retention while preserving required runtime/product truth.

## Inputs

- `vinted_radar/services/lifecycle.py`
- `vinted_radar/services/platform_audit.py`

## Expected Output

- `hot-history retention controls`
- `audit-visible retention status`

## Verification

python -m pytest tests/test_lifecycle_jobs.py tests/test_platform_audit.py -q
