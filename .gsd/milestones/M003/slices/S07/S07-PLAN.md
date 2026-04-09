# S07: Best-Profile VPS Rollout + Acceptance Closure

**Goal:** Roll out the measured winning acquisition profile to the real VPS and prove end to end that throughput, storage, runtime truth, and public surfaces remain healthy together.
**Demo:** After this: After this: the VPS runs the measured winning acquisition profile, public surfaces stay healthy, and a final acceptance bundle shows baseline-vs-production throughput, stability, and storage outcomes with no hand-wavy gaps.

## Tasks
- [ ] **T01: Encode the winning profile as reproducible production config** — Why: The measured winner must become executable production configuration, not a report someone has to translate by hand later.
Do:
- Encode the winning market, lane, transport, frontier, and retention settings into versioned config/scripts and any required systemd/env templates.
- Keep rollback/revert paths explicit.
- Document which benchmark artifact selected the profile.
Done when:
- The candidate production profile can be deployed reproducibly from repo state alone.
  - Estimate: 1.5h
  - Files: vinted_radar/cli.py, scripts/run_vps_benchmark.py, README.md, infra/
  - Verify: python -m pytest tests/test_runtime_cli.py tests/test_platform_audit.py -q
- [ ] **T02: Deploy and soak the production-candidate profile on the VPS** — Why: The milestone only matters if the real VPS runs the chosen profile successfully.
Do:
- Deploy the chosen profile to the VPS, restart only the affected services, and preserve backups/rollback points.
- Run a guarded production-candidate soak long enough to collect meaningful benchmark/storage/runtime evidence.
- Keep the public product surfaces under verification during the soak rather than checking them only at the end.
Done when:
- The VPS is running the candidate profile and the soak artifact shows stable collector + serving health.
  - Estimate: 1.5h
  - Files: scripts/run_vps_benchmark.py, scripts/verify_vps_serving.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile production-candidate-soak --duration-minutes 480 --verify-base-url http://46.225.113.129:8765 --output .gsd/milestones/M003/benchmarks/production-candidate-soak.json --markdown .gsd/milestones/M003/benchmarks/production-candidate-soak.md
- [ ] **T03: Build and run the final best-profile acceptance bundle** — Why: Closeout needs one authoritative bundle that proves the final profile is actually better and still operationally honest.
Do:
- Build a final acceptance script that compares baseline versus final winner on throughput, duplicates, challenge rate, bytes/new listing, CPU/RAM, runtime truth, and public-serving health.
- Reuse the existing serving verifier and platform/runtime audit surfaces where possible.
- Fail loudly if any claimed improvement comes with a serving/runtime regression.
Done when:
- One acceptance command returns pass/fail and leaves behind a bundle future agents can trust.
  - Estimate: 1.5h
  - Files: scripts/verify_best_profile_acceptance.py, scripts/verify_vps_serving.py, scripts/verify_cutover_stack.py, README.md
  - Verify: python scripts/verify_best_profile_acceptance.py --host 46.225.113.129 --base-url http://46.225.113.129:8765 --baseline .gsd/milestones/M003/benchmarks/baseline-fr-page1.json --candidate .gsd/milestones/M003/benchmarks/production-candidate-soak.json
- [ ] **T04: Persist the production recommendation and residual limits** — Why: The next milestone should inherit the chosen profile and the remaining limits, not rediscover them from commit diffs.
Do:
- Summarize the measured winner, rejected alternatives, residual ceilings, and safe rollback path in milestone artifacts and project docs.
- Update project-level state/knowledge when the final evidence justifies it.
- Keep the summary tied to artifact paths and commands rather than prose-only claims.
Done when:
- A future agent can answer “what won, what lost, and why?” from the saved artifacts in minutes.
  - Estimate: 1h
  - Files: .gsd/milestones/M003/M003-SUMMARY.md, .gsd/KNOWLEDGE.md, README.md
  - Verify: test -s .gsd/milestones/M003/benchmarks/production-candidate-soak.json
