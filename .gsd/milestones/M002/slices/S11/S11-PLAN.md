# S11: Minimal Evidence Contract + Parquet Lake

**Goal:** Replace heavyweight raw payload persistence with a deliberate minimal evidence contract and immutable Parquet lake so raw proof leaves the hot path while staying inspectable, replayable, and explainable.
**Demo:** After this: After this: discovery and state-refresh emit minimal evidence fragments into partitioned Parquet on object storage with manifests, so raw proof leaves the hot mutable path instead of bloating operational tables.

## Tasks
- [ ] **T01: Minimal evidence schema** — Redefine the listing-card evidence contract around minimal fragments. Replace the API parser's `raw_card=dict(item)` posture with the same targeted proof philosophy already used by the HTML parser, update `card_payload.py` and tests, and make the evidence contract explicit about what is preserved for explainability versus what is dropped from the hot path.
  - Estimate: 2 sessions
  - Files: vinted_radar/parsers/api_catalog_page.py, vinted_radar/parsers/catalog_page.py, vinted_radar/card_payload.py, vinted_radar/models.py, tests/test_api_catalog_page.py, tests/test_card_payload.py
  - Verify: python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q
- [ ] **T02: Parquet writer + object-store manifests** — Implement the Parquet lake writer and manifest registry. Add partitioned Parquet writing with schema versioning and ZSTD compression, S3-compatible upload support, manifest/checksum recording, and a local MinIO-backed integration path so evidence batches can be staged and read back safely.
  - Estimate: 2 sessions
  - Files: vinted_radar/platform/lake_writer.py, vinted_radar/platform/object_store.py, vinted_radar/domain/manifests.py, vinted_radar/cli.py, tests/test_lake_writer.py
  - Verify: python -m pytest tests/test_lake_writer.py -q
- [ ] **T03: Collector emission to evidence lake** — Connect discovery and state-refresh to the new raw-evidence path. Emit listing-seen and probe evidence batches through the outbox/manifests seam, keep write operations idempotent, and make sure one collected run can produce retrievable raw evidence without yet requiring the mutable/read cutover slices.
  - Estimate: 2 sessions
  - Files: vinted_radar/services/discovery.py, vinted_radar/services/state_refresh.py, vinted_radar/platform/outbox.py, vinted_radar/platform/lake_writer.py, tests/test_discovery_service.py, tests/test_runtime_service.py, tests/test_evidence_batches.py
  - Verify: python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q
- [ ] **T04: Historical export + evidence lookup** — Add historical export and evidence inspection tooling. Provide a CLI/backfill command that can export legacy SQLite discovery/observation/probe raw evidence into the Parquet lake, and add an inspection command that resolves an event or manifest reference back to a concrete evidence fragment for debugging and proof drill-down.
  - Estimate: 1-2 sessions
  - Files: vinted_radar/cli.py, vinted_radar/services/evidence_export.py, vinted_radar/services/evidence_lookup.py, tests/test_evidence_export.py
  - Verify: python -m pytest tests/test_evidence_export.py -q
