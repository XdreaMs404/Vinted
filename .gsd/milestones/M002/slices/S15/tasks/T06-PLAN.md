---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T06: Operational closure + final acceptance against the corrected warehouse contract

Close S15 only after the repaired warehouse contract is proven end to end. Update operator docs and verification so lifecycle posture, reconciliation health, change-fact freshness, feature-mart evidence drill-down, and the remaining SQLite hot-path removal are all exercised by the final acceptance proof.

## Inputs

- `README.md`
- `scripts/verify_cutover_stack.py`
- `vinted_radar/services/platform_audit.py`
- `vinted_radar/platform/health.py`

## Expected Output

- `updated operating-model documentation`
- `final acceptance proof that includes change-fact and feature-mart verification`

## Verification

python -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q
