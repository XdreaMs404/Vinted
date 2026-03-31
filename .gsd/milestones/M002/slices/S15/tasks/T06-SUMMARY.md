---
id: T06
parent: S15
milestone: M002
provides: []
requires: []
affects: []
key_files: ["scripts/verify_cutover_stack.py", "README.md", "tests/test_cutover_smoke.py", ".gsd/milestones/M002/slices/S15/tasks/T06-SUMMARY.md"]
key_decisions: ["Make `scripts/verify_cutover_stack.py` the single operator acceptance artifact by composing platform-audit posture, feature-mart/change-fact validation, and ClickHouse-vs-SQLite route parity."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q` and got `3 passed, 1 skipped`. The passing smoke proof now covers platform audit posture, feature-mart freshness/drill-down, ClickHouse route parity, serving checks, and object-storage evidence."
completed_at: 2026-03-31T16:12:42.334Z
blocker_discovered: false
---

# T06: Expanded `verify_cutover_stack.py` to prove platform-audit posture, fresh change facts, evidence-pack drill-down, and ClickHouse route parity.

> Expanded `verify_cutover_stack.py` to prove platform-audit posture, fresh change facts, evidence-pack drill-down, and ClickHouse route parity.

## What Happened
---
id: T06
parent: S15
milestone: M002
key_files:
  - scripts/verify_cutover_stack.py
  - README.md
  - tests/test_cutover_smoke.py
  - .gsd/milestones/M002/slices/S15/tasks/T06-SUMMARY.md
key_decisions:
  - Make `scripts/verify_cutover_stack.py` the single operator acceptance artifact by composing platform-audit posture, feature-mart/change-fact validation, and ClickHouse-vs-SQLite route parity.
duration: ""
verification_result: passed
completed_at: 2026-03-31T16:12:42.335Z
blocker_discovered: false
---

# T06: Expanded `verify_cutover_stack.py` to prove platform-audit posture, fresh change facts, evidence-pack drill-down, and ClickHouse route parity.

**Expanded `verify_cutover_stack.py` to prove platform-audit posture, fresh change facts, evidence-pack drill-down, and ClickHouse route parity.**

## What Happened

Extended the final cutover acceptance proof so it no longer stops at doctor/ingest/object-storage checks. The verifier now validates platform-audit reconciliation/current-state/analytical/backfill posture, confirms ClickHouse feature marts contain populated change facts including a fresh row for the latest discovery run, requires evidence-pack drill-down commands tied to real manifest/event trace IDs, and embeds ClickHouse-vs-SQLite route parity proof to show the remaining SQLite read hot path is no longer required. Updated the README live cutover proof and VPS runbook to reflect the richer acceptance contract and expanded the live smoke test to assert the new proof sections.

## Verification

Ran `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q` and got `3 passed, 1 skipped`. The passing smoke proof now covers platform audit posture, feature-mart freshness/drill-down, ClickHouse route parity, serving checks, and object-storage evidence.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m pytest tests/test_platform_audit.py tests/test_cutover_smoke.py -q` | 0 | ✅ pass | 280ms |


## Deviations

Used `python3` for the final pytest run because an initial async `python -m pytest ...` launch failed before execution due a shell/launcher tokenization issue in the harness, not due repository code.

## Known Issues

None.

## Files Created/Modified

- `scripts/verify_cutover_stack.py`
- `README.md`
- `tests/test_cutover_smoke.py`
- `.gsd/milestones/M002/slices/S15/tasks/T06-SUMMARY.md`


## Deviations
Used `python3` for the final pytest run because an initial async `python -m pytest ...` launch failed before execution due a shell/launcher tokenization issue in the harness, not due repository code.

## Known Issues
None.
