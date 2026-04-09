# S06: Hot-Store Compaction + Bounded Live History

**Goal:** Cut hot-path storage growth aggressively while preserving evidence drill-down, runtime truth, and later analytical/AI usefulness under the new high-throughput acquisition profile.
**Demo:** After this: After this: the chosen high-throughput acquisition profile can run repeatedly without ballooning hot storage, and operators can inspect bytes/new listing, retained history policy, and evidence-preservation diagnostics.

## Tasks
- [ ] **T01: Instrument storage-growth and bytes-per-new-listing audits** — Why: Storage work is blind unless the system can attribute growth to concrete tables, payload paths, and per-discovery cost.
Do:
- Add storage-growth audit helpers that measure DB/table/index growth, bytes per run, and bytes per new listing.
- Make the benchmark/reporting pipeline ingest these metrics automatically.
- Keep the audit usable both locally and against VPS snapshots.
Done when:
- Automated tests can compute table-growth attribution and bytes-per-new-listing from fixture snapshots.
  - Estimate: 1.5h
  - Files: vinted_radar/storage_audit.py, vinted_radar/long_run_audit.py, tests/test_storage_audit.py, tests/test_long_run_audit.py
  - Verify: python -m pytest tests/test_storage_audit.py tests/test_long_run_audit.py -q
- [ ] **T02: Compact redundant hot-history writes without losing evidence lookup** — Why: The current hot path duplicates heavy payload/history rows too aggressively for the desired throughput target.
Do:
- Reduce redundant hot-history writes using delta/hash/reference strategies that keep evidence lookup possible without re-storing identical payloads every cycle.
- Preserve the raw-evidence path in the platform/lake so explainability is not traded away for compactness.
- Add regression coverage for listing detail, evidence lookup, and history queries.
Done when:
- Repository/evidence tests prove compact writes and unchanged drill-down semantics together.
  - Estimate: 2h
  - Files: vinted_radar/repository.py, vinted_radar/db.py, vinted_radar/services/evidence_lookup.py, vinted_radar/platform/lake_writer.py, tests/test_repository.py, tests/test_evidence_lookup.py
  - Verify: python -m pytest tests/test_repository.py tests/test_evidence_lookup.py tests/test_lake_writer.py -q
- [ ] **T03: Bound hot-history retention and surface it in audit diagnostics** — Why: Even compact writes need bounded retention and explicit archive rules if the new throughput target is going to hold over time.
Do:
- Extend lifecycle/retention controls to cover the hot-path history this milestone still needs locally.
- Make retained-history policy and archive behavior visible through audit surfaces.
- Verify that product/runtime reads still succeed after pruning/archive thresholds are applied.
Done when:
- Lifecycle and audit tests prove bounded retention while preserving required runtime/product truth.
  - Estimate: 1.5h
  - Files: vinted_radar/services/lifecycle.py, vinted_radar/services/platform_audit.py, tests/test_lifecycle_jobs.py, tests/test_platform_audit.py
  - Verify: python -m pytest tests/test_lifecycle_jobs.py tests/test_platform_audit.py -q
- [ ] **T04: Prove lower storage growth on the VPS** — Why: The storage slice only matters if the real VPS profile gets cheaper in practice, not just in unit tests.
Do:
- Run a controlled VPS soak comparing the selected strategy before and after compaction/retention changes.
- Record DB growth, bytes per new listing, and any evidence/product regressions.
- Persist the comparison artifact for the final rollout decision.
Done when:
- The milestone has a VPS storage comparison artifact showing materially improved per-discovery cost.
  - Estimate: 1h
  - Files: scripts/run_vps_benchmark.py, .gsd/milestones/M003/benchmarks/
  - Verify: python scripts/run_vps_benchmark.py --host 46.225.113.129 --profile storage-compare --duration-minutes 180 --output .gsd/milestones/M003/benchmarks/storage-compare.json --markdown .gsd/milestones/M003/benchmarks/storage-compare.md
