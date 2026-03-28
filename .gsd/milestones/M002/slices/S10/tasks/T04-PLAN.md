---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T04: Foundation smoke proof

Prove the foundation end to end in a narrow but real smoke path. Wire pytest fixtures/helpers for PostgreSQL, ClickHouse, and MinIO, and add one platform smoke that boots the stack, runs migrations, inserts a test outbox event, writes a manifest stub, and verifies all readiness/health diagnostics surface correctly.

## Inputs

- `infra/docker-compose.data-platform.yml`
- `vinted_radar/platform/migrations.py`
- `vinted_radar/platform/outbox.py`

## Expected Output

- `tests/test_data_platform_smoke.py`
- `CLI doctor/bootstrap smoke proof`

## Verification

python -m pytest tests/test_data_platform_smoke.py -q
