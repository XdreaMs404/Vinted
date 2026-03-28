# S10: Polyglot Data Platform Foundation

**Goal:** Introduce the final polyglot data-platform foundation without another future storage rewrite: shared config, versioned migrations, platform bootstrap/doctor commands, and idempotent event/outbox/manifests contracts for PostgreSQL, ClickHouse, and S3-compatible object storage.
**Demo:** After this: After this: the repo can boot the final PostgreSQL + ClickHouse + S3-compatible platform locally and on the VPS, with versioned schemas, shared config, and idempotent event/outbox plumbing ready for real ingestion.

## Tasks
- [x] **T01: Added the shared polyglot platform config contract with dependency pins, env validation, redacted observability, and README docs.** — Add the new platform dependency base and configuration layer. Extend `pyproject.toml` with PostgreSQL, ClickHouse, Parquet, and S3-compatible client libraries; introduce a shared platform config module that loads/validates connection settings, storage prefixes, schema versions, and cutover flags; and document the new environment contract without yet changing product reads.
  - Estimate: 1-2 sessions
  - Files: pyproject.toml, vinted_radar/platform/config.py, vinted_radar/cli.py, README.md, tests/test_platform_config.py
  - Verify: python -m pytest tests/test_platform_config.py -q
- [x] **T02: Added platform bootstrap/doctor commands with versioned PostgreSQL and ClickHouse migrations plus MinIO bucket/prefix checks.** — Introduce provider bootstrap and migration runners. Add versioned SQL migration directories for PostgreSQL and ClickHouse, local compose/bootstrap helpers for PostgreSQL + ClickHouse + MinIO, and CLI doctor/bootstrap commands that validate connectivity, schema version, and writable object-store prefixes.
  - Estimate: 2 sessions
  - Files: infra/docker-compose.data-platform.yml, infra/postgres/, infra/clickhouse/, vinted_radar/platform/migrations.py, vinted_radar/platform/bootstrap.py, vinted_radar/cli.py, tests/test_data_platform_bootstrap.py
  - Verify: python -m pytest tests/test_data_platform_bootstrap.py -q
- [x] **T03: Added deterministic listing event envelopes, evidence manifests, and a leased PostgreSQL outbox contract.** — Define the durable event, outbox, and manifest contracts that future slices will write once and project many times. Add versioned event envelope dataclasses/serializers, deterministic event IDs, evidence manifest IDs/checksums, and PostgreSQL outbox tables/interfaces that make multi-sink delivery idempotent instead of ad hoc.
  - Estimate: 2 sessions
  - Files: vinted_radar/domain/events.py, vinted_radar/domain/manifests.py, vinted_radar/platform/outbox.py, vinted_radar/platform/postgres_schema/, tests/test_event_envelope.py, tests/test_outbox.py
  - Verify: python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q
- [x] **T04: Added a Docker-backed platform smoke proof with shared health rendering and isolated compose fixtures.** — Prove the foundation end to end in a narrow but real smoke path. Wire pytest fixtures/helpers for PostgreSQL, ClickHouse, and MinIO, and add one platform smoke that boots the stack, runs migrations, inserts a test outbox event, writes a manifest stub, and verifies all readiness/health diagnostics surface correctly.
  - Estimate: 1 session
  - Files: tests/conftest.py, tests/test_data_platform_smoke.py, vinted_radar/platform/health.py, vinted_radar/cli.py
  - Verify: python -m pytest tests/test_data_platform_smoke.py -q
