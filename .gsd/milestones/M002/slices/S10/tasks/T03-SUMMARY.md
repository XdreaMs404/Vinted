---
id: T03
parent: S10
milestone: M002
provides: []
requires: []
affects: []
key_files: ["vinted_radar/domain/events.py", "vinted_radar/domain/manifests.py", "vinted_radar/domain/__init__.py", "vinted_radar/platform/outbox.py", "infra/postgres/migrations/V002__platform_event_outbox.sql", "tests/test_event_envelope.py", "tests/test_outbox.py", "vinted_radar/platform/config.py", "vinted_radar/platform/__init__.py", "tests/test_platform_config.py", "tests/test_data_platform_bootstrap.py", "README.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["D036: use canonical-JSON versioned event envelopes with deterministic UUIDv5 IDs, deterministic SHA-256 manifest checksums/IDs, and a PostgreSQL outbox keyed by unique `(event_id, sink)` rows with leased claim/retry state."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "`python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q` passed, covering deterministic envelope IDs, JSON round-trips, manifest ID/checksum stability, idempotent outbox publish semantics, leased claim/retry behavior, and delivery completion. `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` also passed because this task introduced a real PostgreSQL V002 migration and provider-specific schema-version defaults. A final combined run of all four platform tests passed as well."
completed_at: 2026-03-28T19:31:43.596Z
blocker_discovered: false
---

# T03: Added deterministic listing event envelopes, evidence manifests, and a leased PostgreSQL outbox contract.

> Added deterministic listing event envelopes, evidence manifests, and a leased PostgreSQL outbox contract.

## What Happened
---
id: T03
parent: S10
milestone: M002
key_files:
  - vinted_radar/domain/events.py
  - vinted_radar/domain/manifests.py
  - vinted_radar/domain/__init__.py
  - vinted_radar/platform/outbox.py
  - infra/postgres/migrations/V002__platform_event_outbox.sql
  - tests/test_event_envelope.py
  - tests/test_outbox.py
  - vinted_radar/platform/config.py
  - vinted_radar/platform/__init__.py
  - tests/test_platform_config.py
  - tests/test_data_platform_bootstrap.py
  - README.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D036: use canonical-JSON versioned event envelopes with deterministic UUIDv5 IDs, deterministic SHA-256 manifest checksums/IDs, and a PostgreSQL outbox keyed by unique `(event_id, sink)` rows with leased claim/retry state.
duration: ""
verification_result: passed
completed_at: 2026-03-28T19:31:43.596Z
blocker_discovered: false
---

# T03: Added deterministic listing event envelopes, evidence manifests, and a leased PostgreSQL outbox contract.

**Added deterministic listing event envelopes, evidence manifests, and a leased PostgreSQL outbox contract.**

## What Happened

Built the durable event/outbox foundation for the polyglot platform slice. Added a versioned `EventEnvelope` with canonical JSON serialization, deterministic UUIDv5 event IDs, payload checksums, storage-key helpers, and a concrete `build_listing_observed_event(...)` constructor over the current `ListingCard` discovery shape. Added deterministic evidence-manifest contracts with per-object checksums and storage keys, then introduced a PostgreSQL V002 migration plus `PostgresOutbox` publish/claim/fail/deliver flows so future sinks can consume unique `(event_id, sink)` rows with lease-based retries instead of ad hoc dedupe. Because PostgreSQL advanced to V002 while ClickHouse stayed on V001, I also split provider-specific schema-version defaults, updated bootstrap/config regressions, exported the outbox seam, documented the new baseline, recorded D036, and appended the schema-version-default gotcha to `.gsd/KNOWLEDGE.md`.

## Verification

`python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q` passed, covering deterministic envelope IDs, JSON round-trips, manifest ID/checksum stability, idempotent outbox publish semantics, leased claim/retry behavior, and delivery completion. `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` also passed because this task introduced a real PostgreSQL V002 migration and provider-specific schema-version defaults. A final combined run of all four platform tests passed as well.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q` | 0 | ✅ pass | 110ms |
| 2 | `python -m pytest tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` | 0 | ✅ pass | 310ms |
| 3 | `python -m pytest tests/test_event_envelope.py tests/test_outbox.py tests/test_platform_config.py tests/test_data_platform_bootstrap.py -q` | 0 | ✅ pass | 320ms |


## Deviations

Added `vinted_radar/domain/__init__.py` as the package seam for the new contracts, and updated the platform config/bootstrap docs/tests so the new PostgreSQL V002 migration becomes the default expected baseline without incorrectly forcing ClickHouse past V001. No slice replan was needed.

## Known Issues

None.

## Files Created/Modified

- `vinted_radar/domain/events.py`
- `vinted_radar/domain/manifests.py`
- `vinted_radar/domain/__init__.py`
- `vinted_radar/platform/outbox.py`
- `infra/postgres/migrations/V002__platform_event_outbox.sql`
- `tests/test_event_envelope.py`
- `tests/test_outbox.py`
- `vinted_radar/platform/config.py`
- `vinted_radar/platform/__init__.py`
- `tests/test_platform_config.py`
- `tests/test_data_platform_bootstrap.py`
- `README.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Added `vinted_radar/domain/__init__.py` as the package seam for the new contracts, and updated the platform config/bootstrap docs/tests so the new PostgreSQL V002 migration becomes the default expected baseline without incorrectly forcing ClickHouse past V001. No slice replan was needed.

## Known Issues
None.
