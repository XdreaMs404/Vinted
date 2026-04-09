---
estimated_steps: 7
estimated_files: 6
skills_used: []
---

# T02: Compact redundant hot-history writes without losing evidence lookup

Why: The current hot path duplicates heavy payload/history rows too aggressively for the desired throughput target.
Do:
- Reduce redundant hot-history writes using delta/hash/reference strategies that keep evidence lookup possible without re-storing identical payloads every cycle.
- Preserve the raw-evidence path in the platform/lake so explainability is not traded away for compactness.
- Add regression coverage for listing detail, evidence lookup, and history queries.
Done when:
- Repository/evidence tests prove compact writes and unchanged drill-down semantics together.

## Inputs

- `vinted_radar/repository.py`
- `vinted_radar/services/evidence_lookup.py`
- `vinted_radar/platform/lake_writer.py`

## Expected Output

- `compacted hot-history write path`
- `regression coverage for evidence drill-down`

## Verification

python -m pytest tests/test_repository.py tests/test_evidence_lookup.py tests/test_lake_writer.py -q
