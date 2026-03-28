---
id: T04
parent: S11
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/cli.py", "vinted_radar/platform/object_store.py", "vinted_radar/services/evidence_export.py", "vinted_radar/services/evidence_lookup.py", "tests/test_evidence_export.py", ".gsd/milestones/M002/slices/S11/tasks/T04-SUMMARY.md"]
key_decisions: ["Export legacy SQLite discovery, observation, and probe rows under explicit vinted.backfill.* batch event types instead of pretending they came from live collector invocations.", "Decode canonical-JSON Parquet cells back into navigable row.*, event.*, and manifest.* fragments during evidence lookup so immutable lake storage stays inspectable."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan verification command `python -m pytest tests/test_evidence_export.py -q` and it passed. Ran the full slice regression stack `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py tests/test_lake_writer.py tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_evidence_export.py -q` and it passed. Ran `python -m pytest tests/test_runtime_cli.py tests/test_history_cli.py tests/test_cli_smoke.py -q` to confirm the shared CLI surface still behaved after adding the new commands."
completed_at: 2026-03-28T20:53:20.834Z
blocker_discovered: false
---

# T04: Added SQLite evidence backfill and manifest/event lookup commands for the Parquet lake.

> Added SQLite evidence backfill and manifest/event lookup commands for the Parquet lake.

## What Happened
---
id: T04
parent: S11
milestone: M002
key_files:
  - vinted_radar/cli.py
  - vinted_radar/platform/object_store.py
  - vinted_radar/services/evidence_export.py
  - vinted_radar/services/evidence_lookup.py
  - tests/test_evidence_export.py
  - .gsd/milestones/M002/slices/S11/tasks/T04-SUMMARY.md
key_decisions:
  - Export legacy SQLite discovery, observation, and probe rows under explicit vinted.backfill.* batch event types instead of pretending they came from live collector invocations.
  - Decode canonical-JSON Parquet cells back into navigable row.*, event.*, and manifest.* fragments during evidence lookup so immutable lake storage stays inspectable.
duration: ""
verification_result: passed
completed_at: 2026-03-28T20:53:20.835Z
blocker_discovered: false
---

# T04: Added SQLite evidence backfill and manifest/event lookup commands for the Parquet lake.

**Added SQLite evidence backfill and manifest/event lookup commands for the Parquet lake.**

## What Happened

Added vinted_radar/services/evidence_export.py to stream historical listing discovery, observation, and probe evidence out of SQLite and publish it as immutable manifested Parquet batches under explicit vinted.backfill.* batch event types. Added vinted_radar/services/evidence_lookup.py plus object-store key listing support so operators can resolve an event or manifest reference back to the batch event, manifest, Parquet object, selected row, and decoded fragment path. Wired both capabilities into new Typer commands in vinted_radar/cli.py and added tests/test_evidence_export.py to cover direct export, manifest-driven lookup, and a CLI round-trip against a seeded legacy SQLite snapshot.

## Verification

Ran the task-plan verification command `python -m pytest tests/test_evidence_export.py -q` and it passed. Ran the full slice regression stack `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py tests/test_lake_writer.py tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_evidence_export.py -q` and it passed. Ran `python -m pytest tests/test_runtime_cli.py tests/test_history_cli.py tests/test_cli_smoke.py -q` to confirm the shared CLI surface still behaved after adding the new commands.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_evidence_export.py -q` | 0 | ✅ pass | 850ms |
| 2 | `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py tests/test_lake_writer.py tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py tests/test_evidence_export.py -q` | 0 | ✅ pass | 18440ms |
| 3 | `python -m pytest tests/test_runtime_cli.py tests/test_history_cli.py tests/test_cli_smoke.py -q` | 0 | ✅ pass | 1500ms |


## Deviations

The task-plan inputs mentioned vinted_radar/repository.py, but the existing schema plus the new service modules were enough to stream the historical rows directly from SQLite without adding repository-only wrapper methods.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/cli.py`
- `vinted_radar/platform/object_store.py`
- `vinted_radar/services/evidence_export.py`
- `vinted_radar/services/evidence_lookup.py`
- `tests/test_evidence_export.py`
- `.gsd/milestones/M002/slices/S11/tasks/T04-SUMMARY.md`


## Deviations
The task-plan inputs mentioned vinted_radar/repository.py, but the existing schema plus the new service modules were enough to stream the historical rows directly from SQLite without adding repository-only wrapper methods.

## Known Issues
None.
