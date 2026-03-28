---
id: T01
parent: S11
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/card_payload.py", "vinted_radar/parsers/api_catalog_page.py", "vinted_radar/parsers/catalog_page.py", "tests/test_api_catalog_page.py", "tests/test_card_payload.py", "tests/test_parsers.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M002/slices/S11/tasks/T01-SUMMARY.md"]
key_decisions: ["Persist listing-card raw evidence as a versioned schema_version + evidence_source + fragments envelope for both HTML and API cards.", "Keep normalize_card_snapshot() backward-compatible with legacy flat HTML/API payloads so historical observation rows remain explainable while the forward-write contract shrinks."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Passed the task-plan verification command (python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q) and an additional downstream regression on event serialization and repository hydration (python -m pytest tests/test_event_envelope.py tests/test_repository.py -q)."
completed_at: 2026-03-28T20:03:30.701Z
blocker_discovered: false
---

# T01: Replaced full API raw-card persistence with a shared minimal evidence envelope and normalization tests.

> Replaced full API raw-card persistence with a shared minimal evidence envelope and normalization tests.

## What Happened
---
id: T01
parent: S11
milestone: M002
key_files:
  - vinted_radar/card_payload.py
  - vinted_radar/parsers/api_catalog_page.py
  - vinted_radar/parsers/catalog_page.py
  - tests/test_api_catalog_page.py
  - tests/test_card_payload.py
  - tests/test_parsers.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M002/slices/S11/tasks/T01-SUMMARY.md
key_decisions:
  - Persist listing-card raw evidence as a versioned schema_version + evidence_source + fragments envelope for both HTML and API cards.
  - Keep normalize_card_snapshot() backward-compatible with legacy flat HTML/API payloads so historical observation rows remain explainable while the forward-write contract shrinks.
duration: ""
verification_result: passed
completed_at: 2026-03-28T20:03:30.702Z
blocker_discovered: false
---

# T01: Replaced full API raw-card persistence with a shared minimal evidence envelope and normalization tests.

**Replaced full API raw-card persistence with a shared minimal evidence envelope and normalization tests.**

## What Happened

Introduced a shared minimal listing-card evidence contract in vinted_radar/card_payload.py using a versioned envelope with schema_version, evidence_source, and fragments. Switched the HTML parser to emit the shared envelope and replaced the API parser's old raw_card=dict(item) behavior with a targeted fragment builder that preserves only title/brand/size/status/price proof while dropping heavy nested payloads from the hot path. Expanded normalize_card_snapshot() so repository hydration accepts both the new envelope and historical flat HTML/API payloads, then added focused tests for envelope generation, snapshot normalization, and legacy compatibility. Recorded the durable contract choice in project knowledge and decision D038.

## Verification

Passed the task-plan verification command (python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q) and an additional downstream regression on event serialization and repository hydration (python -m pytest tests/test_event_envelope.py tests/test_repository.py -q).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_api_catalog_page.py tests/test_card_payload.py -q` | 0 | ✅ pass | 1234ms |
| 2 | `python -m pytest tests/test_event_envelope.py tests/test_repository.py -q` | 0 | ✅ pass | 1378ms |


## Deviations

The plan referenced tests/test_card_payload.py, but that file was not present in this checkout, so I created it and used it as the focused contract test surface.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/card_payload.py`
- `vinted_radar/parsers/api_catalog_page.py`
- `vinted_radar/parsers/catalog_page.py`
- `tests/test_api_catalog_page.py`
- `tests/test_card_payload.py`
- `tests/test_parsers.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M002/slices/S11/tasks/T01-SUMMARY.md`


## Deviations
The plan referenced tests/test_card_payload.py, but that file was not present in this checkout, so I created it and used it as the focused contract test surface.

## Known Issues
None.
