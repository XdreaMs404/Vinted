---
id: S11
parent: M002
milestone: M002
provides:
  - A shared minimal listing-card evidence contract for both HTML and API catalog cards, plus backward-compatible normalization for historical rows.
  - An immutable S3-compatible Parquet lake writer with deterministic event/parquet/manifest keys, uploaded manifests, ZSTD compression, and checksum-guarded rewrites.
  - Collector-side discovery and state-refresh evidence emission that can publish manifested Parquet batches and outbox metadata idempotently.
  - Historical SQLite evidence export and event/manifest lookup tooling that turns the lake into a real replay/debug surface instead of a write-only archive.
requires:
  - slice: S10
    provides: The shared polyglot platform config, deterministic event/manifest contracts, object-store prefixes, and leased outbox seams that S11 reuses for immutable evidence publishing.
affects:
  - M002/S12
  - M002/S13
  - M002/S14
  - M002/S15
  - M003
key_files:
  - vinted_radar/card_payload.py
  - vinted_radar/parsers/api_catalog_page.py
  - vinted_radar/parsers/catalog_page.py
  - vinted_radar/platform/object_store.py
  - vinted_radar/platform/lake_writer.py
  - vinted_radar/platform/__init__.py
  - vinted_radar/services/discovery.py
  - vinted_radar/services/state_refresh.py
  - vinted_radar/services/runtime.py
  - vinted_radar/services/evidence_export.py
  - vinted_radar/services/evidence_lookup.py
  - vinted_radar/cli.py
  - tests/test_card_payload.py
  - tests/test_api_catalog_page.py
  - tests/test_lake_writer.py
  - tests/test_evidence_batches.py
  - tests/test_discovery_service.py
  - tests/test_runtime_service.py
  - tests/test_evidence_export.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D038 — Persist versioned minimal listing-card evidence envelopes (`schema_version`, `evidence_source`, `fragments`) for both HTML and API cards, while keeping normalization backward-compatible with legacy flat payloads.
  - D039 — Anchor each evidence batch on a deterministic batch `EventEnvelope`, upload the batch event JSON plus the partitioned Parquet object under deterministic keys, and reject same-key rewrites when the recorded SHA-256 differs.
  - D040 — Auto-wire collector evidence emission from platform cutover flags in the default discovery/state-refresh factories, emit deterministic Parquet/manifests batches when object-storage writes are enabled, and surface emitted batch metadata on service reports.
  - D041 — Export legacy SQLite discovery, observation, and probe rows under explicit `vinted.backfill.*` batch event types with `capture_source=sqlite_backfill` metadata instead of pretending they came from live collector invocations.
  - D042 — Decode canonical-JSON Parquet cell strings back into navigable nested `row.*`, `event.*`, and `manifest.*` fragments during evidence inspection.
patterns_established:
  - Evolve listing-card proof through a shared versioned `schema_version` + `evidence_source` + `fragments` envelope, but keep normalizers compatible with older flat payloads so historical rows do not become unreadable.
  - Treat the Parquet lake as immutable storage: deterministic batch event -> deterministic Parquet key -> deterministic manifest key, all protected by recorded SHA-256 checksums.
  - Emit one discovery batch per accepted catalog page and one state-refresh batch per refresh invocation so retries stay idempotent and downstream sinks can reason about stable batch boundaries.
  - When collector services auto-wire platform publishers from cutover flags, close the full service rather than only the SQLite repository so newly owned S3/Postgres clients are released correctly.
  - Keep historical backfill distinguishable from live ingestion (`vinted.backfill.*`) and decode JSON-like Parquet cells on lookup so the lake remains replayable and drillable down to concrete evidence fragments.
observability_surfaces:
  - `python -m vinted_radar.cli evidence-export --db <sqlite.db> --format json`
  - `python -m vinted_radar.cli evidence-inspect --event-id <id> --listing-id <id> --field-path row.raw_card.price.amount --format json`
  - Discovery service / discovery CLI reports now expose emitted batch metadata for published evidence batches.
  - State-refresh service/runtime surfaces now expose emitted batch metadata for published probe batches.
drill_down_paths:
  - .gsd/milestones/M002/slices/S11/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S11/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S11/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S11/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T09:55:18.663Z
blocker_discovered: false
---

# S11: Minimal Evidence Contract + Parquet Lake

**S11 shrank raw collector proof to a minimal versioned evidence contract and moved it onto an immutable, inspectable Parquet/object-store lake with deterministic manifests, collector emission, and legacy SQLite backfill/lookup tooling.**

## What Happened

S11 turned the S10 platform foundation into the first real raw-evidence boundary for the project. T01 replaced the old API habit of copying full `dict(item)` payloads into SQLite with the same targeted proof posture already used for HTML cards: both parsers now emit a shared `schema_version` + `evidence_source` + `fragments` envelope, and `normalize_card_snapshot()` still understands legacy flat payloads so historical observation rows remain explainable while the forward-write contract gets dramatically smaller.

T02 added the immutable lake-writing layer on top of S10's event/manifest seams. Evidence batches are now anchored on deterministic batch `EventEnvelope`s, serialized to ZSTD-compressed Parquet, uploaded under deterministic object keys, and linked by uploaded manifests. The object-store helper now records SHA-256 metadata and refuses same-key/different-bytes rewrites, so the new Parquet lake behaves like an immutable evidence boundary rather than a mutable file bucket.

T03 connected real collector behavior to that boundary. Discovery now emits one deterministic listing-seen batch per accepted catalog page, state refresh emits one deterministic probe batch per refresh invocation, and both surfaces expose emitted batch metadata so operators and downstream slices can inspect what was published. The default factories auto-wire the shared publisher from platform cutover flags, and runtime/CLI cleanup now closes the full service rather than only the SQLite repository so the newly owned object-store/Postgres clients do not leak.

T04 closed the historical and debugging loop. Legacy SQLite discovery, observation, and probe rows can now be exported into the lake under explicit `vinted.backfill.*` event types, and `evidence-inspect` can resolve an event or manifest reference back down to the concrete Parquet row and decoded fragment path such as `row.raw_card.price.amount` or `row.detail.reason`. That means S12-S15 can treat the object-store lake as a real replay/debug surface now, not just a write-only archive.

The practical shape this slice established is: minimal evidence envelope -> deterministic batch event -> immutable Parquet object -> uploaded manifest -> inspectable event/manifest/row fragment drill-down. That is the seam downstream projector, warehouse, backfill, and grounded-AI slices should extend instead of inventing a second raw-evidence format.

## Verification

Re-ran every slice-plan verification command during closeout on 2026-03-29, and every command exited 0:

- `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q` → **50 passed**. Re-proved the shared minimal evidence envelope plus backward-compatible normalization across new and legacy card payloads.
- `python -m pytest tests/test_lake_writer.py -q` → **2 passed, 1 skipped**. Re-proved deterministic manifested Parquet writing and immutable-key checksum protection; the Docker-gated MinIO integration case skipped in this workstation session because the local Docker daemon was unavailable.
- `python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q` → **20 passed**. Re-proved idempotent collector evidence publishing plus deterministic discovery/state-refresh batch emission without runtime regressions.
- `python -m pytest tests/test_evidence_export.py -q` → **3 passed**. Re-proved SQLite backfill, manifest/event lookup, and the operator-style `evidence-export` + `evidence-inspect` CLI round-trip.

This also satisfies the slice-level observability/diagnostic check: the closeout reran the dedicated export/inspect coverage that resolves lake objects back to concrete fragments, and the collector/report tests confirmed that discovery and state-refresh surface emitted batch metadata for later debugging.

## Requirements Advanced

- R014 — S11 moved raw proof onto a deterministic manifest + Parquet/object-store boundary and added fragment-level lookup, creating the durable evidence substrate future grounded AI summaries and inline insights can reference instead of SQLite-bound JSON blobs.
- R016 — S11 reduced hot-path storage pressure, introduced immutable lake retention with inspectable manifests, and added operator backfill/lookup tooling that advances the project toward a production-grade data platform.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

- T01 created `tests/test_card_payload.py` because the slice plan assumed a focused contract test file that was not present in the checkout.
- T02 reused the existing manifest model and CLI seams instead of adding extra domain or command wrappers that turned out not to be necessary.
- T04 streamed legacy rows directly from SQLite through the new export service instead of adding repository-only wrapper methods first.
- No slice replan was required.

## Known Limitations

- The live user-facing product still reads from the legacy SQLite boundary; S11 adds an immutable raw-evidence lake but does not yet cut mutable truth or serving reads over to PostgreSQL/ClickHouse.
- Object-store and outbox publishing remain staged behind platform configuration/cutover flags, so not every local collector invocation emits lake batches unless that platform path is enabled.
- Multi-row evidence batches require an explicit selector (`--row-index`, `--listing-id`, or `--probe-id`) for unambiguous inspection.
- This closeout session could not execute the Docker-gated MinIO case inside `tests/test_lake_writer.py` because the local Docker daemon was unavailable, although the command still passed and the deterministic/unit contract remained green.
- The slice adds strong pull-based inspection surfaces, but not continuous publish-lag metrics, alerting, or automated remediation for lake-write failures yet.

## Follow-ups

- S12 should consume the deterministic batch/manifests seam to project current-state and control-plane truth into PostgreSQL instead of extending SQLite mutation tables.
- S13 should build ClickHouse raw facts and serving rollups from the same manifested batch contract rather than introducing a second ingestion shape.
- S14 should use the explicit `vinted.backfill.*` export path to move the real historical SQLite corpus into the new platform and then cut live reads off the old SQLite history boundary.
- Re-run the Docker-backed MinIO lake verification path when a Docker daemon is available on the closeout workstation or target VPS environment.
- Add publish-failure visibility, lag metrics, and operator runbooks around the new evidence-lake path before the platform becomes the mandatory live boundary.

## Files Created/Modified

- `vinted_radar/card_payload.py` — Introduced the shared minimal listing-card evidence envelope builders and backward-compatible snapshot normalization.
- `vinted_radar/parsers/api_catalog_page.py` — Stopped persisting heavyweight full API card payloads and emitted targeted API evidence fragments instead.
- `vinted_radar/parsers/catalog_page.py` — Aligned HTML card evidence generation with the shared minimal envelope contract.
- `vinted_radar/platform/object_store.py` — Added checksum-aware immutable S3 object operations plus key listing support for manifest/event lookup.
- `vinted_radar/platform/lake_writer.py` — Implemented deterministic manifested Parquet batch writing/reading with ZSTD compression and stable object keys.
- `vinted_radar/services/discovery.py` — Published discovery listing-seen evidence batches and surfaced emitted batch references on service reports.
- `vinted_radar/services/state_refresh.py` — Published probe evidence batches for refresh runs and surfaced emitted batch references.
- `vinted_radar/services/runtime.py` — Updated cleanup behavior so full auto-wired services close their owned platform clients correctly.
- `vinted_radar/services/evidence_export.py` — Streamed legacy SQLite discoveries, observations, and probes into explicit backfill evidence batches.
- `vinted_radar/services/evidence_lookup.py` — Resolved event/manifest references back to decoded row/event/manifest fragments inside the Parquet lake.
- `vinted_radar/cli.py` — Added `evidence-export` and `evidence-inspect` operator commands and updated service-level cleanup paths.
- `tests/test_card_payload.py` — Added focused contract coverage for the minimal envelope and legacy normalization compatibility.
- `tests/test_lake_writer.py` — Added deterministic batch, immutability, and MinIO round-trip coverage for the Parquet lake writer.
- `tests/test_evidence_batches.py` — Added idempotent collector-publisher and manifested batch emission coverage.
- `tests/test_evidence_export.py` — Added historical export, lookup, and CLI round-trip coverage for the new lake tooling.
- `.gsd/DECISIONS.md` — Recorded S11 decisions D038 through D042 for the evidence contract, immutable lake graph, collector emission, backfill typing, and lookup decoding posture.
- `.gsd/KNOWLEDGE.md` — Recorded reusable S11 patterns for explicit backfill event typing and decoded Parquet fragment lookup.
- `.gsd/PROJECT.md` — Updated the project state to reflect S11 completion and the new Parquet/object-store evidence boundary.
