---
id: T03
parent: S11
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/platform/lake_writer.py", "vinted_radar/services/discovery.py", "vinted_radar/services/state_refresh.py", "vinted_radar/services/runtime.py", "vinted_radar/cli.py", "vinted_radar/platform/__init__.py", "tests/platform_test_fakes.py", "tests/test_evidence_batches.py", "tests/test_discovery_service.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S11/tasks/T03-SUMMARY.md"]
key_decisions: ["Auto-wire collector evidence emission from platform cutover flags in the default discovery/state-refresh factories, and expose emitted batch metadata on service reports for later inspection.", "Emit one deterministic discovery batch per accepted catalog page and one deterministic state-refresh batch per refresh invocation, so immutable object keys and outbox rows stay idempotent."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan verification command `python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q`, and it passed with 20 green checks covering publisher idempotence, retrievable discovery evidence batches, and runtime regressions."
completed_at: 2026-03-28T20:31:58.612Z
blocker_discovered: false
---

# T03: Wired discovery and state-refresh to emit deterministic Parquet evidence batches with manifests and outbox metadata.

> Wired discovery and state-refresh to emit deterministic Parquet evidence batches with manifests and outbox metadata.

## What Happened
---
id: T03
parent: S11
milestone: M002
key_files:
  - vinted_radar/platform/lake_writer.py
  - vinted_radar/services/discovery.py
  - vinted_radar/services/state_refresh.py
  - vinted_radar/services/runtime.py
  - vinted_radar/cli.py
  - vinted_radar/platform/__init__.py
  - tests/platform_test_fakes.py
  - tests/test_evidence_batches.py
  - tests/test_discovery_service.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S11/tasks/T03-SUMMARY.md
key_decisions:
  - Auto-wire collector evidence emission from platform cutover flags in the default discovery/state-refresh factories, and expose emitted batch metadata on service reports for later inspection.
  - Emit one deterministic discovery batch per accepted catalog page and one deterministic state-refresh batch per refresh invocation, so immutable object keys and outbox rows stay idempotent.
duration: ""
verification_result: passed
completed_at: 2026-03-28T20:31:58.612Z
blocker_discovered: false
---

# T03: Wired discovery and state-refresh to emit deterministic Parquet evidence batches with manifests and outbox metadata.

**Wired discovery and state-refresh to emit deterministic Parquet evidence batches with manifests and outbox metadata.**

## What Happened

Added a shared CollectorEvidencePublisher that writes immutable manifested Parquet batches and optional outbox rows, then wired discovery and state-refresh to emit deterministic listing-seen and probe evidence batches through that seam. Discovery now emits one batch per accepted catalog page, state refresh emits one batch per refresh invocation, both services surface emitted batch metadata on their reports, and runtime/CLI cleanup now closes full services so auto-wired platform clients are released correctly. Added focused tests for publisher idempotence, discovery-side lake emission, and the contracted runtime verification surface, and recorded the new service-close rule in project knowledge plus decision D040.

## Verification

Ran the task-plan verification command `python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q`, and it passed with 20 green checks covering publisher idempotence, retrievable discovery evidence batches, and runtime regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q` | 0 | ✅ pass | 2978ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/platform/lake_writer.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/services/state_refresh.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/cli.py`
- `vinted_radar/platform/__init__.py`
- `tests/platform_test_fakes.py`
- `tests/test_evidence_batches.py`
- `tests/test_discovery_service.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S11/tasks/T03-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
