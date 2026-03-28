---
id: T04
parent: S10
milestone: M002
provides: []
requires: []
affects: []
key_files: ["infra/docker-compose.data-platform.yml", "pyproject.toml", "vinted_radar/platform/health.py", "vinted_radar/platform/__init__.py", "vinted_radar/cli.py", "tests/conftest.py", "tests/test_data_platform_smoke.py", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Use env-substituted host ports, unique compose project names, and shared health-rendering helpers so real smoke runs stay isolated and assert the same readiness text the CLI prints."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python -m pytest tests/test_data_platform_smoke.py -q` passed against the real local Docker stack, proving isolated-port compose startup, PostgreSQL V001/V002 and ClickHouse V001 migration application, MinIO bucket/prefix bootstrap, a real outbox publish into PostgreSQL, a manifest JSON write/read in object storage, and healthy `platform-doctor` / shared health rendering afterward. I then ran `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py tests/test_event_envelope.py tests/test_outbox.py tests/test_data_platform_smoke.py -q`, and all 15 platform-foundation tests passed as the final S10 regression set."
completed_at: 2026-03-28T19:48:24.564Z
blocker_discovered: false
---

# T04: Added a Docker-backed platform smoke proof with shared health rendering and isolated compose fixtures.

> Added a Docker-backed platform smoke proof with shared health rendering and isolated compose fixtures.

## What Happened
---
id: T04
parent: S10
milestone: M002
key_files:
  - infra/docker-compose.data-platform.yml
  - pyproject.toml
  - vinted_radar/platform/health.py
  - vinted_radar/platform/__init__.py
  - vinted_radar/cli.py
  - tests/conftest.py
  - tests/test_data_platform_smoke.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Use env-substituted host ports, unique compose project names, and shared health-rendering helpers so real smoke runs stay isolated and assert the same readiness text the CLI prints.
duration: ""
verification_result: passed
completed_at: 2026-03-28T19:48:24.568Z
blocker_discovered: false
---

# T04: Added a Docker-backed platform smoke proof with shared health rendering and isolated compose fixtures.

**Added a Docker-backed platform smoke proof with shared health rendering and isolated compose fixtures.**

## What Happened

Implemented the final proof layer for the S10 platform foundation. I parameterized `infra/docker-compose.data-platform.yml` so PostgreSQL, ClickHouse, and MinIO can bind to unique host ports during tests, which also removed the real ClickHouse/MinIO host-port collision on `9000`. I added `vinted_radar.platform.health` plus package exports and switched the CLI to render platform bootstrap/doctor diagnostics through those shared helpers, so both operator output and test assertions read the same readiness surface. I expanded `tests/conftest.py` with Docker-aware smoke fixtures, ephemeral compose project setup, backend client factories, and captured subprocess diagnostics, then added `tests/test_data_platform_smoke.py` to boot the real stack, run `platform-bootstrap`, verify PostgreSQL and ClickHouse migrations, publish a real outbox event with a manifest row, write a manifest JSON object to MinIO, and confirm `platform-doctor` plus direct health summaries stay green afterward. During live execution the Windows environment also exposed that bare `psycopg` could not load `libpq`, so I pinned `psycopg[binary]` in `pyproject.toml` and recorded that workstation-specific setup rule in `.gsd/KNOWLEDGE.md`.

## Verification

`python -m pytest tests/test_data_platform_smoke.py -q` passed against the real local Docker stack, proving isolated-port compose startup, PostgreSQL V001/V002 and ClickHouse V001 migration application, MinIO bucket/prefix bootstrap, a real outbox publish into PostgreSQL, a manifest JSON write/read in object storage, and healthy `platform-doctor` / shared health rendering afterward. I then ran `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py tests/test_event_envelope.py tests/test_outbox.py tests/test_data_platform_smoke.py -q`, and all 15 platform-foundation tests passed as the final S10 regression set.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_data_platform_smoke.py -q` | 0 | ✅ pass | 49720ms |
| 2 | `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py tests/test_event_envelope.py tests/test_outbox.py tests/test_data_platform_smoke.py -q` | 0 | ✅ pass | 49150ms |


## Deviations

Expanded the task slightly beyond the original file list to parameterize compose host ports and pin `psycopg[binary]` in `pyproject.toml`, because the live smoke run surfaced a real host-port collision and a Windows `libpq` loader failure that would have made the planned proof non-executable. No slice replan was needed.

## Known Issues

The smoke/regression pytest runs still emit one transitive Python 3.13 deprecation warning (`'u'` type code) from imported dependency code, but all platform verification passes.

## Files Created/Modified

- `infra/docker-compose.data-platform.yml`
- `pyproject.toml`
- `vinted_radar/platform/health.py`
- `vinted_radar/platform/__init__.py`
- `vinted_radar/cli.py`
- `tests/conftest.py`
- `tests/test_data_platform_smoke.py`
- `.gsd/KNOWLEDGE.md`


## Deviations
Expanded the task slightly beyond the original file list to parameterize compose host ports and pin `psycopg[binary]` in `pyproject.toml`, because the live smoke run surfaced a real host-port collision and a Windows `libpq` loader failure that would have made the planned proof non-executable. No slice replan was needed.

## Known Issues
The smoke/regression pytest runs still emit one transitive Python 3.13 deprecation warning (`'u'` type code) from imported dependency code, but all platform verification passes.
