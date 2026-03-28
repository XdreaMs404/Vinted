---
id: T02
parent: S10
milestone: M002
provides: []
requires: []
affects: []
key_files: ["infra/docker-compose.data-platform.yml", "infra/postgres/migrations/V001__platform_bootstrap_audit.sql", "infra/clickhouse/migrations/V001__platform_bootstrap_audit.sql", "vinted_radar/platform/migrations.py", "vinted_radar/platform/bootstrap.py", "vinted_radar/platform/__init__.py", "vinted_radar/cli.py", "tests/test_data_platform_bootstrap.py", "README.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["D035: use versioned `V###__name.sql` directories with per-provider `platform_schema_migrations` ledgers and persistent object-store prefix markers/write probes so bootstrap and doctor stay idempotent and observable across PostgreSQL, ClickHouse, and S3-compatible storage."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python -m pytest tests/test_data_platform_bootstrap.py -q` passed (5 tests), covering migration parsing, PostgreSQL/ClickHouse bootstrap behavior, MinIO bucket/prefix bootstrap, doctor failure reporting, and CLI rendering/exit codes. `python -m pytest tests/test_platform_config.py -q` also passed (5 tests) as a regression check because this task expanded the same `vinted_radar.platform` package boundary and CLI imports."
completed_at: 2026-03-28T19:16:32.424Z
blocker_discovered: false
---

# T02: Added platform bootstrap/doctor commands with versioned PostgreSQL and ClickHouse migrations plus MinIO bucket/prefix checks.

> Added platform bootstrap/doctor commands with versioned PostgreSQL and ClickHouse migrations plus MinIO bucket/prefix checks.

## What Happened
---
id: T02
parent: S10
milestone: M002
key_files:
  - infra/docker-compose.data-platform.yml
  - infra/postgres/migrations/V001__platform_bootstrap_audit.sql
  - infra/clickhouse/migrations/V001__platform_bootstrap_audit.sql
  - vinted_radar/platform/migrations.py
  - vinted_radar/platform/bootstrap.py
  - vinted_radar/platform/__init__.py
  - vinted_radar/cli.py
  - tests/test_data_platform_bootstrap.py
  - README.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D035: use versioned `V###__name.sql` directories with per-provider `platform_schema_migrations` ledgers and persistent object-store prefix markers/write probes so bootstrap and doctor stay idempotent and observable across PostgreSQL, ClickHouse, and S3-compatible storage.
duration: ""
verification_result: passed
completed_at: 2026-03-28T19:16:32.425Z
blocker_discovered: false
---

# T02: Added platform bootstrap/doctor commands with versioned PostgreSQL and ClickHouse migrations plus MinIO bucket/prefix checks.

**Added platform bootstrap/doctor commands with versioned PostgreSQL and ClickHouse migrations plus MinIO bucket/prefix checks.**

## What Happened

Implemented the polyglot platform bootstrap foundation for the slice. Added `vinted_radar/platform/migrations.py` to load contiguous `V###__name.sql` migrations, fingerprint SQL with checksums, and compute pending/current schema state through a shared runner. Added `vinted_radar/platform/bootstrap.py` to connect to PostgreSQL, ClickHouse, and S3-compatible storage, manage per-provider `platform_schema_migrations` ledgers, apply pending migrations during bootstrap, validate schema state during doctor runs, create the configured object-store bucket when needed, ensure persistent `.prefix` marker objects, and run write/delete probes across the raw-events/manifests/parquet prefixes. Wired `platform-bootstrap` and `platform-doctor` into `vinted_radar.cli`, exported the new helpers through `vinted_radar.platform.__init__`, added a local `infra/docker-compose.data-platform.yml` stack plus initial PostgreSQL/ClickHouse V001 audit-table migrations, documented the operator flow in `README.md`, recorded D035 for the idempotent bootstrap contract, and added focused pytest coverage using fakes for PostgreSQL, ClickHouse, S3, migration parsing, and CLI output/exit behavior.

## Verification

`python -m pytest tests/test_data_platform_bootstrap.py -q` passed (5 tests), covering migration parsing, PostgreSQL/ClickHouse bootstrap behavior, MinIO bucket/prefix bootstrap, doctor failure reporting, and CLI rendering/exit codes. `python -m pytest tests/test_platform_config.py -q` also passed (5 tests) as a regression check because this task expanded the same `vinted_radar.platform` package boundary and CLI imports.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_data_platform_bootstrap.py -q` | 0 | ✅ pass | 1274ms |
| 2 | `python -m pytest tests/test_platform_config.py -q` | 0 | ✅ pass | 1007ms |


## Deviations

Exported the new bootstrap helpers from `vinted_radar.platform.__init__` and added a `.gsd/KNOWLEDGE.md` entry for the ClickHouse database-agnostic migration rule so downstream slices can reuse the package seam safely. No slice replan was needed.

## Known Issues

None.

## Files Created/Modified

- `infra/docker-compose.data-platform.yml`
- `infra/postgres/migrations/V001__platform_bootstrap_audit.sql`
- `infra/clickhouse/migrations/V001__platform_bootstrap_audit.sql`
- `vinted_radar/platform/migrations.py`
- `vinted_radar/platform/bootstrap.py`
- `vinted_radar/platform/__init__.py`
- `vinted_radar/cli.py`
- `tests/test_data_platform_bootstrap.py`
- `README.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Exported the new bootstrap helpers from `vinted_radar.platform.__init__` and added a `.gsd/KNOWLEDGE.md` entry for the ClickHouse database-agnostic migration rule so downstream slices can reuse the package seam safely. No slice replan was needed.

## Known Issues
None.
