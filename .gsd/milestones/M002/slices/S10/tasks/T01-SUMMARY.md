---
id: T01
parent: S10
milestone: M002
provides: []
requires: []
affects: []
key_files: ["pyproject.toml", "vinted_radar/platform/__init__.py", "vinted_radar/platform/config.py", "tests/test_platform_config.py", "README.md", ".gsd/DECISIONS.md"]
key_decisions: ["D034: centralize the polyglot platform env contract in `vinted_radar.platform.config` with normalized storage prefixes, explicit schema versions, redacted diagnostics, and all cutover flags defaulting to false."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python -m pytest tests/test_platform_config.py -q` passed (5 tests). This verified default local settings, env override parsing, storage-prefix normalization, schema/cutover parsing, secret redaction, and invalid-value rejection. Python LSP diagnostics were attempted but no language server is configured in this workspace, so the concrete verification gate was the passing pytest run."
completed_at: 2026-03-28T18:55:06.229Z
blocker_discovered: false
---

# T01: Added the shared polyglot platform config contract with dependency pins, env validation, redacted observability, and README docs.

> Added the shared polyglot platform config contract with dependency pins, env validation, redacted observability, and README docs.

## What Happened
---
id: T01
parent: S10
milestone: M002
key_files:
  - pyproject.toml
  - vinted_radar/platform/__init__.py
  - vinted_radar/platform/config.py
  - tests/test_platform_config.py
  - README.md
  - .gsd/DECISIONS.md
key_decisions:
  - D034: centralize the polyglot platform env contract in `vinted_radar.platform.config` with normalized storage prefixes, explicit schema versions, redacted diagnostics, and all cutover flags defaulting to false.
duration: ""
verification_result: passed
completed_at: 2026-03-28T18:55:06.231Z
blocker_discovered: false
---

# T01: Added the shared polyglot platform config contract with dependency pins, env validation, redacted observability, and README docs.

**Added the shared polyglot platform config contract with dependency pins, env validation, redacted observability, and README docs.**

## What Happened

Extended the project dependency base for the final data-platform stack, then introduced a shared `vinted_radar.platform.config` module that validates PostgreSQL, ClickHouse, and S3-compatible settings, normalizes object prefixes, carries schema-version expectations, and exposes redacted diagnostics for later bootstrap/doctor commands. Added focused pytest coverage for defaults, overrides, negative validation paths, and secret redaction, documented the new environment contract in the README, and recorded the architectural choice as D034 while keeping live product reads on SQLite.

## Verification

`python -m pytest tests/test_platform_config.py -q` passed (5 tests). This verified default local settings, env override parsing, storage-prefix normalization, schema/cutover parsing, secret redaction, and invalid-value rejection. Python LSP diagnostics were attempted but no language server is configured in this workspace, so the concrete verification gate was the passing pytest run.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_platform_config.py -q` | 0 | ✅ pass | 1819ms |


## Deviations

Added `vinted_radar/platform/__init__.py` so the planned `vinted_radar.platform.config` module is importable as a real package boundary. No slice replan was needed.

## Known Issues

None.

## Files Created/Modified

- `pyproject.toml`
- `vinted_radar/platform/__init__.py`
- `vinted_radar/platform/config.py`
- `tests/test_platform_config.py`
- `README.md`
- `.gsd/DECISIONS.md`


## Deviations
Added `vinted_radar/platform/__init__.py` so the planned `vinted_radar.platform.config` module is importable as a real package boundary. No slice replan was needed.

## Known Issues
None.
