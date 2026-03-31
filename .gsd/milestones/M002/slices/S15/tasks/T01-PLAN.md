---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T01: Added a `platform-lifecycle` retention command that enforces ClickHouse TTL, archives/prunes transient PostgreSQL rows, and reports explicit storage posture.

Implement bounded-storage lifecycle controls. Add ClickHouse TTL policy activation, PostgreSQL pruning/archival jobs for mutable transient data, object-store retention classes/lifecycle config, and reporting that makes current storage posture visible instead of implicit.

## Inputs

- `vinted_radar/platform/clickhouse_schema/`
- `vinted_radar/platform/postgres_schema/`
- `vinted_radar/platform/config.py`

## Expected Output

- `Lifecycle jobs + storage posture report`
- `tests/test_lifecycle_jobs.py`

## Verification

python -m pytest tests/test_lifecycle_jobs.py -q
