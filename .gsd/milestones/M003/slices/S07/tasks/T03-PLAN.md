---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T03: Build and run the final best-profile acceptance bundle

Why: Closeout needs one authoritative bundle that proves the final profile is actually better and still operationally honest.
Do:
- Build a final acceptance script that compares baseline versus final winner on throughput, duplicates, challenge rate, bytes/new listing, CPU/RAM, runtime truth, and public-serving health.
- Reuse the existing serving verifier and platform/runtime audit surfaces where possible.
- Fail loudly if any claimed improvement comes with a serving/runtime regression.
Done when:
- One acceptance command returns pass/fail and leaves behind a bundle future agents can trust.

## Inputs

- `.gsd/milestones/M003/benchmarks/baseline-fr-page1.json`
- `.gsd/milestones/M003/benchmarks/production-candidate-soak.json`

## Expected Output

- `scripts/verify_best_profile_acceptance.py`
- `.gsd/milestones/M003/M003-SUMMARY.md source metrics`

## Verification

python scripts/verify_best_profile_acceptance.py --host 46.225.113.129 --base-url http://46.225.113.129:8765 --baseline .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --candidate .gsd/milestones/M003/benchmarks/production-candidate-soak.json
