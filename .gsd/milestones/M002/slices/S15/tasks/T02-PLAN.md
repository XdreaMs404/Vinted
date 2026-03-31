---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Added a unified `platform-audit` surface that wraps reconciliation, ingest lag, lifecycle drift, and backfill posture into CLI and runtime/health payloads.

Add durable reconciliation and lag audit surfaces. Build commands and health payloads that compare PostgreSQL current-state windows, ClickHouse analytical windows, and Parquet manifest coverage, then expose lag/failure state for ingestion, lifecycle, and backfill paths so operators can trust the platform day to day.

## Inputs

- `vinted_radar/services/reconciliation.py`
- `vinted_radar/platform/postgres_repository.py`
- `vinted_radar/platform/clickhouse_ingest.py`
- `vinted_radar/platform/lake_writer.py`

## Expected Output

- `Cross-store audit commands`
- `health/runtime data-platform audit surface`
- `tests/test_platform_audit.py`

## Verification

python -m pytest tests/test_platform_audit.py -q
