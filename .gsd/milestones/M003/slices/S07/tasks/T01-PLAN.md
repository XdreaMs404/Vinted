---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: Encode the winning profile as reproducible production config

Why: The measured winner must become executable production configuration, not a report someone has to translate by hand later.
Do:
- Encode the winning market, lane, transport, frontier, and retention settings into versioned config/scripts and any required systemd/env templates.
- Keep rollback/revert paths explicit.
- Document which benchmark artifact selected the profile.
Done when:
- The candidate production profile can be deployed reproducibly from repo state alone.

## Inputs

- `.gsd/milestones/M003/benchmarks/cross-market-frontier-winner.json`
- `.gsd/milestones/M003/benchmarks/storage-compare.json`

## Expected Output

- `versioned production acquisition profile`
- `rollback-safe VPS config updates`

## Verification

python -m pytest tests/test_runtime_cli.py tests/test_platform_audit.py -q
