---
id: S10
parent: M002
milestone: M002
provides:
  - A shared, validated, redacted platform configuration contract for PostgreSQL, ClickHouse, and S3-compatible object storage with staged cutover flags.
  - Idempotent `platform-bootstrap` and `platform-doctor` operator commands backed by versioned PostgreSQL/ClickHouse migrations and object-store prefix probes.
  - Deterministic versioned event-envelope and evidence-manifest contracts plus a leased PostgreSQL outbox ready for multi-sink delivery.
  - A real Docker-backed smoke proof and shared health-rendering path that future slices can reuse for local/VPS platform verification.
requires:
  - slice: S09
    provides: the post-S09 operator hardening and storage-growth evidence that justified replacing the monolithic SQLite boundary with a staged polyglot platform
affects:
  - M002/S11
  - M002/S12
  - M002/S13
  - M002/S14
  - M002/S15
  - M003
key_files:
  - pyproject.toml
  - vinted_radar/platform/config.py
  - infra/docker-compose.data-platform.yml
  - infra/postgres/migrations/V001__platform_bootstrap_audit.sql
  - infra/postgres/migrations/V002__platform_event_outbox.sql
  - infra/clickhouse/migrations/V001__platform_bootstrap_audit.sql
  - vinted_radar/platform/migrations.py
  - vinted_radar/platform/bootstrap.py
  - vinted_radar/platform/outbox.py
  - vinted_radar/platform/health.py
  - vinted_radar/domain/events.py
  - vinted_radar/domain/manifests.py
  - vinted_radar/cli.py
  - tests/test_data_platform_smoke.py
  - README.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D034 — use one dataclass-based `vinted_radar.platform.config` loader for PostgreSQL, ClickHouse, and S3-compatible settings with normalized prefixes, explicit per-provider schema versions, redacted diagnostics, and cutover flags defaulting to false.
  - D035 — use versioned `V###__name.sql` migration directories with per-provider ledgers plus persistent object-store prefix markers and write probes so bootstrap and doctor stay idempotent and observable.
  - D036 — use canonical-JSON versioned event envelopes with deterministic UUIDv5 IDs, deterministic SHA-256 manifest checksums/IDs, and a PostgreSQL outbox keyed by unique `(event_id, sink)` rows with leased claim/retry state.
  - D037 — use env-substituted host ports, unique Docker compose project names, and shared health-rendering helpers so the real smoke stack stays isolated and the CLI/test readiness text cannot drift.
patterns_established:
  - Centralize the polyglot env contract in `vinted_radar.platform.config` and keep all cutover flags explicit and disabled by default until downstream slices prove their writers/readers.
  - Keep provider-specific schema-version expectations instead of one shared platform version, because PostgreSQL and ClickHouse migrations advance independently.
  - Use versioned `V###__name.sql` directories plus per-provider ledgers, object-store `.prefix` markers, and write probes so bootstrap and doctor remain idempotent and observable.
  - Use deterministic event-envelope IDs, manifest IDs/checksums, and unique `(event_id, sink)` outbox rows with leased retry state so downstream sinks can stay replay-safe.
  - Parameterize the data-platform compose stack and reuse shared health renderers so real smoke tests stay isolated and assert the same readiness contract operators see.
observability_surfaces:
  - python -m vinted_radar.cli platform-bootstrap
  - python -m vinted_radar.cli platform-doctor
  - python -m pytest tests/test_data_platform_smoke.py -q
  - infra/docker-compose.data-platform.yml
  - vinted_radar/platform/health.py
drill_down_paths:
  - .gsd/milestones/M002/slices/S10/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S10/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S10/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S10/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-28T19:56:16.402Z
blocker_discovered: false
---

# S10: Polyglot Data Platform Foundation

**S10 established the staged PostgreSQL + ClickHouse + S3-compatible platform backbone—shared config, versioned migrations, bootstrap/doctor tooling, deterministic event/manifests, and a leased PostgreSQL outbox—without yet cutting the live product off SQLite.**

## What Happened

## What this slice actually delivered

S10 replaces the old “future platform” placeholder with a real, bootable polyglot foundation inside the repo.

T01 established a shared platform configuration boundary in `vinted_radar.platform.config`. PostgreSQL, ClickHouse, and S3-compatible object-storage settings now load from one validated contract, storage prefixes are normalized safely, schema versions are explicit per provider, cutover flags are present but default to `false`, and redacted diagnostics expose endpoints/versions without leaking secrets.

T02 turned that contract into operator tooling. The repo now contains versioned PostgreSQL and ClickHouse migration directories, a local `docker-compose.data-platform.yml` stack for PostgreSQL + ClickHouse + MinIO, and `platform-bootstrap` / `platform-doctor` CLI commands that bootstrap schema state, create the object-store bucket when needed, ensure persistent `.prefix` marker objects, and run write/delete probes across the `raw_events`, `manifests`, and `parquet` prefixes.

T03 added the write-once contracts that downstream ingestion slices need. Listing-observed events now have deterministic UUIDv5 IDs, canonical JSON serialization, payload checksums, and stable object keys. Evidence manifests now carry deterministic IDs/checksums plus stable object keys. PostgreSQL now also owns a leased outbox contract keyed by unique `(event_id, sink)` rows so future sinks can claim, retry, and mark deliveries idempotently instead of inventing per-sink dedupe rules.

T04 closed the loop with a real smoke path. The Docker-backed proof boots PostgreSQL, ClickHouse, and MinIO on isolated host ports, runs the real migrations, publishes a real outbox event, writes/reads a manifest object, and confirms that the same shared health renderer reports the platform healthy afterward.

## Patterns this slice established

- Keep the polyglot env contract centralized and staged: one config loader, explicit schema versions, redacted diagnostics, and cutover flags off by default until later slices are ready.
- Keep platform migration state provider-specific. PostgreSQL and ClickHouse can advance independently, so bootstrap/doctor must compare each provider to its own expected version.
- Treat object storage as a first-class platform dependency: bootstrap bucket state, persist prefix markers, and run write probes before future ingestion assumes the lake is writable.
- Treat event and manifest identities as deterministic contracts, not incidental row IDs, so evidence can be replayed, deduplicated, and joined across PostgreSQL, ClickHouse, and object storage.
- Keep health rendering shared between the CLI and tests so operator diagnostics and proof text do not drift.

## What the next slices should know

S11-S13 should build on the contracts in this slice rather than inventing new ones. The safe path is: emit the deterministic event envelope once, attach deterministic evidence manifests, publish leased outbox rows per sink, and let PostgreSQL / ClickHouse / object storage consumers project from that write-once boundary. Do not bypass the outbox with sink-local heuristics, and do not collapse provider-specific schema versions back into one shared constant.

The product is intentionally still staged on SQLite. Nothing in S10 silently flips live reads or writes. Downstream slices must opt into PostgreSQL writes, ClickHouse writes, object-storage writes, and polyglot reads deliberately via the cutover flags after their projectors and serving paths are proven.

## Operational Readiness (Q8)

- **Health signal:** `python -m vinted_radar.cli platform-doctor` exits `0`, prints `Healthy: yes`, and reports PostgreSQL schema `v2`, ClickHouse schema `v1`, plus successful object-store write probes for `raw_events`, `manifests`, and `parquet`.
- **Failure signal:** `platform-doctor` exits non-zero and surfaces concrete reasons such as pending migrations, checksum drift, missing bucket/prefix markers, or failed object-store write probes; the smoke proof also fails if bootstrap/doctor output drifts from the shared renderer.
- **Recovery procedure:** start or repair the local stack with `docker compose -f infra/docker-compose.data-platform.yml up -d`, rerun `python -m vinted_radar.cli platform-bootstrap`, rerun `python -m vinted_radar.cli platform-doctor`, and if the contract changed materially rerun `python -m pytest tests/test_data_platform_smoke.py -q`.
- **Monitoring gaps:** the slice provides strong pull-based operator diagnostics, but no continuous consumer lag metrics, remote alerting, or VPS-automated health/export path yet. Those remain follow-up work for the cutover slices.

## Verification

All slice-plan verification gates passed on 2026-03-28:

- `python -m pytest tests/test_platform_config.py -q` → **5 passed**. Verified default local settings, env override parsing, storage-prefix normalization, redacted diagnostics, and invalid-value rejection.
- `python -m pytest tests/test_data_platform_bootstrap.py -q` → **5 passed**. Verified migration parsing, PostgreSQL/ClickHouse bootstrap behavior, MinIO bucket/prefix bootstrap, doctor failure reporting, and CLI rendering/exit codes.
- `python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q` → **4 passed**. Verified deterministic event/manifests IDs/checksums plus idempotent outbox publish, lease, retry, and delivery behavior.
- `python -m pytest tests/test_data_platform_smoke.py -q` → **1 passed**. Verified the real Docker-backed platform smoke path: isolated stack startup, migrations, real outbox publish, manifest object write/read, and healthy `platform-bootstrap` / `platform-doctor` output through the shared health renderer.

This also satisfies the slice-level observability check: the smoke proof exercised and asserted the actual readiness surfaces that operators will use (`platform-bootstrap`, `platform-doctor`, and shared platform health rendering).

## Requirements Advanced

- R016 — S10 established versioned migrations, bootstrap/doctor diagnostics, and idempotent multi-store delivery plumbing that move the project away from the monolithic SQLite boundary toward a production-grade operational platform.
- R014 — S10 introduced deterministic event, manifest, and object-storage contracts that future grounded AI and evidence-linked summary slices can build on without another storage redesign.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

- Added `vinted_radar/platform/__init__.py` and `vinted_radar/domain/__init__.py` as explicit package seams so the new platform/domain contracts can be imported cleanly across later slices.
- Split provider-specific schema-version defaults once PostgreSQL advanced to V002 while ClickHouse intentionally remained on V001.
- Parameterized the data-platform compose stack with env-substituted host ports and pinned `psycopg[binary]` so the real Docker smoke path is executable on this Windows workstation.
- No slice replan was needed.

## Known Limitations

- SQLite remains the live user-facing read path; S10 intentionally lays the platform foundation without cutting production reads or writes over yet.
- Object storage is proven for bucket/prefix bootstrap, marker objects, write probes, and manifest smoke writes, but S11 still has to move real evidence fragments and parquet generation onto that boundary.
- No background consumer/projector exists yet, so outbox rows are ready for downstream sinks but are not consumed automatically in this slice.
- The Docker-backed smoke proof still emits one transitive Python 3.13 deprecation warning (`'u'` type code) from imported dependency code, although the verification itself passes.

## Follow-ups

- S11 should start emitting minimal evidence fragments and manifests into the object-store/parquet boundary using the deterministic event and manifest contracts introduced here.
- S12 should move mutable control-plane and current-state truth into PostgreSQL via projector-backed writes on top of the new outbox tables.
- S13 should build ClickHouse facts and serving rollups from the same write-once contract rather than introducing a second ingestion shape.
- S14 should backfill historical SQLite evidence into PostgreSQL, ClickHouse, and object storage, then cut product reads over off the legacy SQLite boundary.
- Add operator-grade VPS automation and continuous monitoring around `platform-bootstrap` / `platform-doctor`; today the health contract is strong, but it is still a pull-based CLI surface rather than a continuously exported monitoring stack.

## Files Created/Modified

- `pyproject.toml` — Pinned the polyglot platform dependency set and switched PostgreSQL support to `psycopg[binary]` for reliable local smoke execution.
- `vinted_radar/platform/config.py` — Added the shared platform config loader with env validation, redaction, prefix normalization, per-provider schema versions, and staged cutover flags.
- `infra/docker-compose.data-platform.yml` — Added the local PostgreSQL + ClickHouse + MinIO stack with env-substituted host ports for isolated bootstrap and smoke runs.
- `infra/postgres/migrations/V001__platform_bootstrap_audit.sql` — Added the PostgreSQL bootstrap audit baseline migration.
- `infra/postgres/migrations/V002__platform_event_outbox.sql` — Added the PostgreSQL event / manifest / outbox schema migration.
- `infra/clickhouse/migrations/V001__platform_bootstrap_audit.sql` — Added the ClickHouse bootstrap audit baseline migration.
- `vinted_radar/platform/migrations.py` — Implemented versioned SQL migration loading, checksum tracking, and contiguous-version enforcement.
- `vinted_radar/platform/bootstrap.py` — Implemented cross-provider bootstrap and doctor flows, including migration ledgers, bucket creation, prefix markers, and write probes.
- `vinted_radar/platform/outbox.py` — Implemented deterministic publish / claim / fail / deliver flows for the PostgreSQL leased outbox.
- `vinted_radar/domain/events.py` — Added deterministic versioned event-envelope helpers and listing-observed event construction.
- `vinted_radar/domain/manifests.py` — Added deterministic evidence-manifest entries, checksums, IDs, and object-key helpers.
- `vinted_radar/platform/health.py` — Added shared platform health summarization/rendering used by both CLI output and smoke assertions.
- `vinted_radar/cli.py` — Wired `platform-bootstrap` and `platform-doctor` into the CLI and shared reporting path.
- `tests/conftest.py` — Added isolated Docker-backed smoke fixtures and end-to-end platform smoke coverage.
- `tests/test_platform_config.py` — Added focused config, bootstrap, event-envelope, outbox, and real-stack smoke coverage for the new platform foundation.
- `tests/test_data_platform_bootstrap.py` — Added focused config, bootstrap, event-envelope, outbox, and real-stack smoke coverage for the new platform foundation.
- `tests/test_event_envelope.py` — Added focused config, bootstrap, event-envelope, outbox, and real-stack smoke coverage for the new platform foundation.
- `tests/test_outbox.py` — Added focused config, bootstrap, event-envelope, outbox, and real-stack smoke coverage for the new platform foundation.
- `tests/test_data_platform_smoke.py` — Added focused config, bootstrap, event-envelope, outbox, and real-stack smoke coverage for the new platform foundation.
- `README.md` — Documented the new environment contract, local stack, bootstrap flow, and doctor flow for downstream operators and slices.
- `.gsd/PROJECT.md` — Updated project state after the platform foundation landed.
- `.gsd/KNOWLEDGE.md` — Recorded reusable platform smoke and migration patterns for future slices.
- `.gsd/DECISIONS.md` — Appended the S10 architectural and verification decisions.
