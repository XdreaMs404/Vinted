---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Parquet writer + object-store manifests

Implement the Parquet lake writer and manifest registry. Add partitioned Parquet writing with schema versioning and ZSTD compression, S3-compatible upload support, manifest/checksum recording, and a local MinIO-backed integration path so evidence batches can be staged and read back safely.

## Inputs

- `vinted_radar/platform/config.py`
- `vinted_radar/domain/manifests.py`
- `infra/docker-compose.data-platform.yml`

## Expected Output

- `vinted_radar/platform/lake_writer.py`
- `vinted_radar/platform/object_store.py`
- `tests/test_lake_writer.py`

## Verification

python -m pytest tests/test_lake_writer.py -q
