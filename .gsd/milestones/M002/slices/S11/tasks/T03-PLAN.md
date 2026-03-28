---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T03: Collector emission to evidence lake

Connect discovery and state-refresh to the new raw-evidence path. Emit listing-seen and probe evidence batches through the outbox/manifests seam, keep write operations idempotent, and make sure one collected run can produce retrievable raw evidence without yet requiring the mutable/read cutover slices.

## Inputs

- `vinted_radar/services/discovery.py`
- `vinted_radar/services/state_refresh.py`
- `vinted_radar/platform/outbox.py`
- `vinted_radar/platform/lake_writer.py`

## Expected Output

- `Collector-to-lake emission path`
- `tests for listing-seen/probe evidence batches`

## Verification

python -m pytest tests/test_evidence_batches.py tests/test_discovery_service.py tests/test_runtime_service.py -q
