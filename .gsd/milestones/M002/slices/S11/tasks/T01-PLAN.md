---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T01: Minimal evidence schema

Redefine the listing-card evidence contract around minimal fragments. Replace the API parser's `raw_card=dict(item)` posture with the same targeted proof philosophy already used by the HTML parser, update `card_payload.py` and tests, and make the evidence contract explicit about what is preserved for explainability versus what is dropped from the hot path.

## Inputs

- `vinted_radar/parsers/api_catalog_page.py`
- `vinted_radar/parsers/catalog_page.py`
- `vinted_radar/card_payload.py`
- `.gsd/KNOWLEDGE.md`

## Expected Output

- `Unified minimal evidence schema for API + HTML cards`
- `tests proving targeted fragment preservation`

## Verification

python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q
