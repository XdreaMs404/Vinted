---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T04: Historical export + evidence lookup

Add historical export and evidence inspection tooling. Provide a CLI/backfill command that can export legacy SQLite discovery/observation/probe raw evidence into the Parquet lake, and add an inspection command that resolves an event or manifest reference back to a concrete evidence fragment for debugging and proof drill-down.

## Inputs

- `vinted_radar/db.py`
- `vinted_radar/repository.py`
- `vinted_radar/platform/lake_writer.py`

## Expected Output

- `SQLite-to-lake export command`
- `evidence inspection command`
- `tests/test_evidence_export.py`

## Verification

python -m pytest tests/test_evidence_export.py -q
