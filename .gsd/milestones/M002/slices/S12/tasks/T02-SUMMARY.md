---
id: T02
parent: S12
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/platform/postgres_repository.py", "vinted_radar/services/projectors.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S12/tasks/T02-SUMMARY.md"]
key_decisions: ["D044: project listing identity/presence/current-state from outbox-backed page batches, but do not derive follow-up misses from page-scoped manifests."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python3 - <<'PY' ... py_compile.compile('vinted_radar/platform/postgres_repository.py'); py_compile.compile('vinted_radar/services/projectors.py') ... PY` passed, proving the landed repository/projector scaffold imports and compiles."
completed_at: 2026-03-30T21:07:41.967Z
blocker_discovered: false
---

# T02: Scaffolded the PostgreSQL mutable-truth projector service and replay-safe listing batch projection, but discovery/runtime wiring and tests remain unfinished.

> Scaffolded the PostgreSQL mutable-truth projector service and replay-safe listing batch projection, but discovery/runtime wiring and tests remain unfinished.

## What Happened
---
id: T02
parent: S12
milestone: M002
key_files:
  - vinted_radar/platform/postgres_repository.py
  - vinted_radar/services/projectors.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S12/tasks/T02-SUMMARY.md
key_decisions:
  - D044: project listing identity/presence/current-state from outbox-backed page batches, but do not derive follow-up misses from page-scoped manifests.
duration: ""
verification_result: passed
completed_at: 2026-03-30T21:07:41.967Z
blocker_discovered: false
---

# T02: Scaffolded the PostgreSQL mutable-truth projector service and replay-safe listing batch projection, but discovery/runtime wiring and tests remain unfinished.

**Scaffolded the PostgreSQL mutable-truth projector service and replay-safe listing batch projection, but discovery/runtime wiring and tests remain unfinished.**

## What Happened

Implemented the first half of the T02 contract by extending `PostgresMutableTruthRepository` with a new `project_listing_seen_batch(...)` path that can upsert listing identity, presence summaries, and current-state rows from manifest-backed batch rows without duplicating raw evidence blobs. I also made the probe projector manifest-aware, added a replay guard in presence-summary merging so reprocessing the same event does not inflate rollups, and created `MutableTruthProjectorService` with manifest fetch, parquet row loading, outbox claiming/delivery/failure handling, mutable-manifest status updates, and outbox-checkpoint observability. The execution unit stopped before the planned `DiscoveryService` / `RadarRuntimeService` wiring and projector tests could be completed, but the slice plan still holds and the next unit can resume from those integration points.

## Verification

`python3 - <<'PY' ... py_compile.compile('vinted_radar/platform/postgres_repository.py'); py_compile.compile('vinted_radar/services/projectors.py') ... PY` passed, proving the landed repository/projector scaffold imports and compiles.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 - <<'PY' ... py_compile.compile('vinted_radar/platform/postgres_repository.py'); py_compile.compile('vinted_radar/services/projectors.py') ... PY` | 0 | ✅ pass | 16ms |


## Deviations

Stopped after the repository + projector-service scaffold because the execution unit hit the context/time-budget wrap-up boundary before the planned discovery/runtime adapter wiring and test additions were completed.

## Known Issues

`vinted_radar/services/discovery.py` is still not wired to mirror discovery bookkeeping into PostgreSQL mutable truth; `vinted_radar/services/runtime.py` is still not wired to mirror runtime/controller snapshots or trigger the new projector sync callback; no automated tests were added in this unit; `vinted_radar/services/projectors.py` is not yet referenced by any default factory or CLI path.

## Files Created/Modified

- `vinted_radar/platform/postgres_repository.py`
- `vinted_radar/services/projectors.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S12/tasks/T02-SUMMARY.md`


## Deviations
Stopped after the repository + projector-service scaffold because the execution unit hit the context/time-budget wrap-up boundary before the planned discovery/runtime adapter wiring and test additions were completed.

## Known Issues
`vinted_radar/services/discovery.py` is still not wired to mirror discovery bookkeeping into PostgreSQL mutable truth; `vinted_radar/services/runtime.py` is still not wired to mirror runtime/controller snapshots or trigger the new projector sync callback; no automated tests were added in this unit; `vinted_radar/services/projectors.py` is not yet referenced by any default factory or CLI path.
