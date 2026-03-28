---
id: T02
parent: S11
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/platform/object_store.py", "vinted_radar/platform/lake_writer.py", "vinted_radar/platform/__init__.py", "tests/test_lake_writer.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S11/tasks/T02-SUMMARY.md"]
key_decisions: ["Anchor each evidence batch on a deterministic batch EventEnvelope and store the batch JSON, Parquet object, and manifest under deterministic keys.", "Treat object-store keys as immutable by recording SHA-256 metadata and rejecting same-key rewrites when the bytes differ."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan verification command `python -m pytest tests/test_lake_writer.py -q`. It passed with three green checks covering deterministic manifest/parquet writing against a fake S3 backend, immutable key rejection for divergent rewrites, and a real MinIO round-trip that restored the batch event, manifest, and Parquet rows from object storage."
completed_at: 2026-03-28T20:14:59.347Z
blocker_discovered: false
---

# T02: Added an immutable S3-backed Parquet batch writer with uploaded manifests and MinIO round-trip tests.

> Added an immutable S3-backed Parquet batch writer with uploaded manifests and MinIO round-trip tests.

## What Happened
---
id: T02
parent: S11
milestone: M002
key_files:
  - vinted_radar/platform/object_store.py
  - vinted_radar/platform/lake_writer.py
  - vinted_radar/platform/__init__.py
  - tests/test_lake_writer.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S11/tasks/T02-SUMMARY.md
key_decisions:
  - Anchor each evidence batch on a deterministic batch EventEnvelope and store the batch JSON, Parquet object, and manifest under deterministic keys.
  - Treat object-store keys as immutable by recording SHA-256 metadata and rejecting same-key rewrites when the bytes differ.
duration: ""
verification_result: passed
completed_at: 2026-03-28T20:14:59.348Z
blocker_discovered: false
---

# T02: Added an immutable S3-backed Parquet batch writer with uploaded manifests and MinIO round-trip tests.

**Added an immutable S3-backed Parquet batch writer with uploaded manifests and MinIO round-trip tests.**

## What Happened

Added vinted_radar/platform/object_store.py with a reusable checksum-aware S3-compatible object-store client that can create buckets, upload/download bytes/text/JSON, expose manifest-ready object metadata, and reject same-key rewrites when the recorded SHA-256 differs. Added vinted_radar/platform/lake_writer.py with a ParquetLakeWriter that anchors each evidence batch on a batch EventEnvelope, stages ZSTD-compressed Parquet locally, uploads the batch event JSON plus the partitioned Parquet file, and publishes an EvidenceManifest that references both objects under deterministic keys. Exported the new platform types through vinted_radar/platform/__init__.py, added unit and MinIO-backed integration coverage in tests/test_lake_writer.py, and recorded the immutable-key checksum rule in project knowledge plus architecture decision D039.

## Verification

Ran the task-plan verification command `python -m pytest tests/test_lake_writer.py -q`. It passed with three green checks covering deterministic manifest/parquet writing against a fake S3 backend, immutable key rejection for divergent rewrites, and a real MinIO round-trip that restored the batch event, manifest, and Parquet rows from object storage.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_lake_writer.py -q` | 0 | ✅ pass | 18300ms |


## Deviations

The slice roadmap mentioned vinted_radar/domain/manifests.py and vinted_radar/cli.py as likely touchpoints, but the existing manifest model and CLI surfaces were already sufficient for this task, so I kept the implementation scoped to the new object-store/writer modules, package exports, tests, and knowledge/decision updates.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/platform/object_store.py`
- `vinted_radar/platform/lake_writer.py`
- `vinted_radar/platform/__init__.py`
- `tests/test_lake_writer.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S11/tasks/T02-SUMMARY.md`


## Deviations
The slice roadmap mentioned vinted_radar/domain/manifests.py and vinted_radar/cli.py as likely touchpoints, but the existing manifest model and CLI surfaces were already sufficient for this task, so I kept the implementation scoped to the new object-store/writer modules, package exports, tests, and knowledge/decision updates.

## Known Issues
None.
