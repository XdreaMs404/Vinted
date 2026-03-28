---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: Platform dependencies + config contract

Add the new platform dependency base and configuration layer. Extend `pyproject.toml` with PostgreSQL, ClickHouse, Parquet, and S3-compatible client libraries; introduce a shared platform config module that loads/validates connection settings, storage prefixes, schema versions, and cutover flags; and document the new environment contract without yet changing product reads.

## Inputs

- `pyproject.toml`
- `README.md`
- `.gsd/DECISIONS.md`

## Expected Output

- `vinted_radar/platform/config.py`
- `tests/test_platform_config.py`
- `README.md`

## Verification

python -m pytest tests/test_platform_config.py -q
