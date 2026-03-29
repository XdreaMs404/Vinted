---
id: T01
parent: S12
milestone: M002
provides: []
requires: []
affects: []
key_files: ["infra/postgres/migrations/V003__platform_mutable_truth.sql", "vinted_radar/platform/postgres_schema/__init__.py", "vinted_radar/platform/config.py", "vinted_radar/platform/__init__.py", "tests/test_postgres_schema.py", "tests/test_platform_config.py", "tests/test_data_platform_bootstrap.py", "tests/test_data_platform_smoke.py"]
key_decisions: ["D043: use separate PostgreSQL tables for mutable manifests, discovery runs, runtime cycles/controller state, catalogs, listing identity, listing current state, listing presence summaries, and composite-key outbox checkpoints, with natural primary keys and projector-facing provenance fields."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python -m pytest tests/test_postgres_schema.py -q` passed, proving the real migration runner applies V003 and that the expected mutable-truth tables, indexes, natural keys, and composite checkpoint key exist. `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` also passed, proving the version bump is wired into the repository’s default PostgreSQL baseline and bootstrap fixtures."
completed_at: 2026-03-29T10:11:05.929Z
blocker_discovered: false
---

# T01: Added PostgreSQL V003 mutable-truth schema for runtime, discovery, catalogs, listing state, manifests, and projector checkpoints.

> Added PostgreSQL V003 mutable-truth schema for runtime, discovery, catalogs, listing state, manifests, and projector checkpoints.

## What Happened
---
id: T01
parent: S12
milestone: M002
key_files:
  - infra/postgres/migrations/V003__platform_mutable_truth.sql
  - vinted_radar/platform/postgres_schema/__init__.py
  - vinted_radar/platform/config.py
  - vinted_radar/platform/__init__.py
  - tests/test_postgres_schema.py
  - tests/test_platform_config.py
  - tests/test_data_platform_bootstrap.py
  - tests/test_data_platform_smoke.py
key_decisions:
  - D043: use separate PostgreSQL tables for mutable manifests, discovery runs, runtime cycles/controller state, catalogs, listing identity, listing current state, listing presence summaries, and composite-key outbox checkpoints, with natural primary keys and projector-facing provenance fields.
duration: ""
verification_result: passed
completed_at: 2026-03-29T10:11:05.932Z
blocker_discovered: false
---

# T01: Added PostgreSQL V003 mutable-truth schema for runtime, discovery, catalogs, listing state, manifests, and projector checkpoints.

**Added PostgreSQL V003 mutable-truth schema for runtime, discovery, catalogs, listing state, manifests, and projector checkpoints.**

## What Happened

Implemented the PostgreSQL mutable-truth schema required for S12 by adding `infra/postgres/migrations/V003__platform_mutable_truth.sql` and a reusable `vinted_radar.platform.postgres_schema` contract module. The migration adds projector-safe tables for mutable manifests, discovery runs, runtime cycles, runtime controller truth, catalogs, listing identity, listing current state, listing presence summaries, and composite-key outbox checkpoints, all keyed so later projectors can upsert idempotently on natural IDs instead of inventing surrogate dedupe layers. I also moved the repository’s default PostgreSQL baseline to schema v3, re-exported the schema contract through `vinted_radar.platform`, and updated the existing platform config/bootstrap/smoke regressions so normal bootstrap flows now expect the new migration instead of leaving it disconnected from the live platform path.

## Verification

`python -m pytest tests/test_postgres_schema.py -q` passed, proving the real migration runner applies V003 and that the expected mutable-truth tables, indexes, natural keys, and composite checkpoint key exist. `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` also passed, proving the version bump is wired into the repository’s default PostgreSQL baseline and bootstrap fixtures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_postgres_schema.py -q` | 0 | ✅ pass | 1385ms |
| 2 | `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` | 0 | ✅ pass | 1721ms |


## Deviations

Updated the platform default schema version and existing platform bootstrap/smoke regression tests in addition to the new task-specific test file, because leaving the default PostgreSQL baseline at V002 would have made the V003 migration unreachable in the normal bootstrap path.

## Known Issues

None.

## Files Created/Modified

- `infra/postgres/migrations/V003__platform_mutable_truth.sql`
- `vinted_radar/platform/postgres_schema/__init__.py`
- `vinted_radar/platform/config.py`
- `vinted_radar/platform/__init__.py`
- `tests/test_postgres_schema.py`
- `tests/test_platform_config.py`
- `tests/test_data_platform_bootstrap.py`
- `tests/test_data_platform_smoke.py`


## Deviations
Updated the platform default schema version and existing platform bootstrap/smoke regression tests in addition to the new task-specific test file, because leaving the default PostgreSQL baseline at V002 would have made the V003 migration unreachable in the normal bootstrap path.

## Known Issues
None.
