---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T04: Persist the production recommendation and residual limits

Why: The next milestone should inherit the chosen profile and the remaining limits, not rediscover them from commit diffs.
Do:
- Summarize the measured winner, rejected alternatives, residual ceilings, and safe rollback path in milestone artifacts and project docs.
- Update project-level state/knowledge when the final evidence justifies it.
- Keep the summary tied to artifact paths and commands rather than prose-only claims.
Done when:
- A future agent can answer “what won, what lost, and why?” from the saved artifacts in minutes.

## Inputs

- `scripts/verify_best_profile_acceptance.py`
- `.gsd/milestones/M003/benchmarks/production-candidate-soak.json`

## Expected Output

- `M003 acceptance narrative and operator notes`
- `updated project knowledge if warranted`

## Verification

test -s .gsd/milestones/M003/benchmarks/production-candidate-soak.json
