---
id: T01
parent: S01
milestone: M002
provides:
  - SQL-backed overview snapshot contract with category, brand, price-band, condition, and sold-state comparison modules plus explicit honesty metadata
key_files:
  - vinted_radar/repository.py
  - vinted_radar/state_machine.py
  - tests/test_overview_repository.py
  - .gsd/DECISIONS.md
key_decisions:
  - D021: keep the overview home contract repository-owned in SQL and preserve thin-support rows with explicit low-support flags instead of hiding them
patterns_established:
  - Share state thresholds/confidence constants between `state_machine.py` and the repository SQL snapshot so the overview payload and Python state surfaces do not drift
observability_surfaces:
  - `RadarRepository.overview_snapshot()`
  - `tests/test_overview_repository.py`
  - `/api/runtime`
  - `/health`
duration: 1h45m
verification_result: passed
completed_at: 2026-03-22T20:16:33+01:00
blocker_discovered: false
---

# T01: Define the SQL overview contract and comparison lenses

**Added a SQL-backed `overview_snapshot()` contract with first comparison lenses and explicit low-support / honesty metadata.**

## What Happened

I replaced the missing overview seam in `vinted_radar/repository.py` with a repository-owned `overview_snapshot()` contract built from SQL CTEs over `listings`, `listing_observations`, `catalog_scans`, and `item_page_probes`.

To keep the SQL and Python state vocabularies aligned, I promoted the state-machine ages and confidence scores in `vinted_radar/state_machine.py` into named constants and reused those values from the repository SQL classifier.

The new repository payload now exposes:
- summary inventory counts
- summary honesty/freshness blocks
- comparison modules for category, brand, price band, condition, and sold state
- per-row support counts, support-share, drilldown filter values, sold-like mix, and state counts
- explicit honesty fields for observed/inferred/unknown basis, partial/thin signal, estimated-publication presence, and low-support flags
- explicit module `status` / `reason` for empty or thin-support lenses

I added `tests/test_overview_repository.py` with a realistic seeded SQLite fixture covering all required lenses and edge cases: active, sold observed, sold probable, unavailable, deleted, unknown, partial signal, missing estimated-publication, and thin-support behavior.

I also recorded the architectural choice in `.gsd/DECISIONS.md` and added a `.gsd/KNOWLEDGE.md` note that the overview SQL must stay numerically aligned with the shared state-machine constants.

## Verification

Task-level verification passed:
- `tests/test_overview_repository.py` proves the new SQL contract returns summary counts and first comparison modules without going through full-corpus scoring.
- `tests/test_history_repository.py` still passes, so the shared evidence/history seam stayed intact.
- `tests/test_state_machine.py` still passes after the constant extraction.

Broader slice verification is partially green, as expected for an intermediate task:
- the broader pytest slice checks already pass
- the real `dashboard` command boots and `/health` returns 200
- browser verification shows the old English M001 home still rendering, while the expected French overview text is still absent; that gap is the planned T02 work, not a blocker for T01
- the live page already exposes working links to `/explorer`, `/api/dashboard`, `/api/runtime`, and `/health`

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_overview_repository.py` | 0 | ✅ pass | 1.89s |
| 2 | `python -m pytest tests/test_history_repository.py` | 0 | ✅ pass | 1.98s |
| 3 | `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | ✅ pass | 2.35s |
| 4 | `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765` | 0 | ✅ pass | 0.81s |
| 5 | `browser_assert @ http://127.0.0.1:8765/ (French overview text + slice links)` | 1 | ❌ fail | n/a |

## Diagnostics

Future agents can inspect the new contract directly with `RadarRepository.overview_snapshot()` and the seeded fixture in `tests/test_overview_repository.py`.

The most useful observability fields added here are:
- `summary.inventory.state_counts`
- `summary.honesty` basis / partial / thin / estimated-publication counts
- `summary.freshness.latest_successful_scan_at`
- `summary.freshness.latest_runtime_cycle_status`
- `summary.freshness.recent_acquisition_failures`
- `comparisons.<lens>.status` and `comparisons.<lens>.reason`
- per-row `honesty.low_support` flags and drilldown filters

## Deviations

None.

## Known Issues

- The slice-level browser expectation for a French-first home still fails because `/` still renders the M001 dashboard copy; that is the planned T02 implementation gap, not a T01 blocker.
- `data/vinted-radar-s01.db` was not pre-seeded locally before verification, so the real dashboard command was verified for startup/health and current link exposure rather than for final market-content fidelity.

## Files Created/Modified

- `vinted_radar/repository.py` — added the SQL overview snapshot CTEs, summary aggregation, and first comparison modules with low-support / honesty metadata.
- `vinted_radar/state_machine.py` — extracted shared state thresholds and confidence constants so the repository SQL classifier reuses the same numeric vocabulary.
- `tests/test_overview_repository.py` — added seeded repository regression coverage for overview counts, lens ordering, support-threshold handling, and honesty metadata.
- `.gsd/DECISIONS.md` — recorded the repository-owned SQL overview contract decision as D021.
- `.gsd/KNOWLEDGE.md` — documented the rule that overview SQL and Python state thresholds must stay aligned.
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — marked T01 complete.
