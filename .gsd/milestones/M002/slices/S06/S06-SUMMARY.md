---
id: S06
parent: M002
milestone: M002
provides:
  - Proxy-aware state refresh, persisted degraded acquisition telemetry, and explicit healthy/partial/degraded product honesty across overview, explorer, detail, runtime, `/api/runtime`, and `/health`
requires:
  - slice: S02
    provides: persisted runtime controller truth and runtime-status/health surfaces that S06 extends with acquisition health
  - slice: S03
    provides: shared product shell and mounted-serving contract used by all S06 HTML/JSON routes
  - slice: S04
    provides: SQL-first explorer/workspace that now carries degraded acquisition honesty
  - slice: S05
    provides: narrative-first listing detail route that S06 extends with degraded-probe prudence and provenance
affects:
  - S07
key_files:
  - vinted_radar/parsers/item_page.py
  - vinted_radar/services/state_refresh.py
  - vinted_radar/services/runtime.py
  - vinted_radar/repository.py
  - vinted_radar/dashboard.py
  - vinted_radar/cli.py
  - README.md
  - .gsd/milestones/M002/slices/S06/S06-UAT.md
key_decisions:
  - D029: degraded acquisition truth now lives in persisted runtime/repository payloads and only the visible product wording is translated in `dashboard.py`.
patterns_established:
  - Keep degraded acquisition repository-owned in `runtime_status().acquisition`, thread its summary into overview freshness, and let the product layer explain the same truth without page-local heuristics.
observability_surfaces:
  - python -m vinted_radar.cli runtime-status --db <db> --format json
  - python -m vinted_radar.cli state-refresh --db <db> --format json
  - /api/runtime
  - /health
  - .gsd/milestones/M002/slices/S06/S06-UAT.md
  - .artifacts/browser/2026-03-23T15-11-53-531Z-session/s06-browser-timeline.json
drill_down_paths:
  - .gsd/milestones/M002/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S06/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S06/tasks/T03-SUMMARY.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
---

# S06: Acquisition Hardening + Degraded-Mode Visibility

**Made the weak item-page acquisition seam proxy-aware and challenge-aware, persisted degraded probe truth on runtime cycles, and surfaced one honest healthy/partial/degraded acquisition contract across the whole product.**

## What Happened

S06 closed the last big honesty gap before M002’s final live acceptance. Up to S05, the product had become much more usable, but the weakest acquisition flank — item-page probing during state refresh — still bypassed the proxy path and collapsed degraded collection into generic `unknown` outcomes. That meant the product could look polished while hiding the fact that direct page-level evidence had gone soft.

T01 fixed the transport seam itself. `state-refresh` now accepts repeatable `--proxy` values and the runtime path forwards the same proxy pool into item-page refresh as discovery already used. The item-page parser now distinguishes anti-bot/challenge-shaped responses from ordinary inconclusive HTML, and the refresh service returns a structured `probe_summary` instead of a bare probe count. Runtime cycles persist that summary in `state_refresh_summary_json`, so degraded probe truth survives beyond the moment of execution.

T02 turned that telemetry into a shared contract. `RadarRepository.runtime_status()` now exposes an `acquisition` block that combines the latest usable state-refresh summary with recent discovery scan failures. Overview freshness now carries `acquisition_status`, probe-issue counts, and example degraded probes; explorer, detail, runtime, `/api/runtime`, and `/health` all read from the same source of truth. The product layer translates that contract into French-first warnings: overview and explorer show `acquisition dégradée`, detail adds `Dernière probe dégradée` plus provenance `historique radar après probe dégradée`, and runtime shows a dedicated acquisition-health panel separate from scheduler truth.

T03 closed the slice operationally. README now documents the new healthy/partial/degraded semantics and the proxy-aware `state-refresh` path, S06 has a repeatable UAT file, the seeded `data/vinted-radar-s06.db` flow is reproducible, and the served browser proof covered overview, explorer, detail, runtime, `/api/runtime`, and `/health`. Browser proof also caught small but real product-layer issues — stale served code after edits, raw English acquisition reasons leaking into visible copy, and cramped runtime warning labels — and those were fixed before closeout.

## Verification

The slice passed targeted parser/runtime/repository/dashboard coverage, the full test suite, and served-browser proof on the seeded degraded S06 demo DB.

## Requirements Advanced

- R011 — degraded or partial acquisition is now explicit in persisted telemetry, product HTML, `/api/runtime`, and `/health` instead of being flattened into generic uncertainty.
- R004 — the visible evidence boundary now includes acquisition health itself, not only listing freshness and confidence.
- R010 — runtime truth remains separate from acquisition truth, so a scheduled controller can still report degraded collection honestly.
- R009 — the clearer overview/explorer/detail/runtime information architecture now carries degraded-mode honesty end to end instead of only on operator-facing JSON.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The written plan did not explicitly call for cleaning up visible acquisition-copy glitches after browser proof, but served verification showed that raw English reason strings and cramped warning labels would undercut the slice’s French-first honesty promise. Those fixes stayed in the product layer and did not change the machine-facing JSON contract.

## Known Limitations

- S06 proves the degraded-mode honesty contract locally on a seeded dataset; it does not yet prove live VPS behavior over time under real anti-bot variability.
- `/api/runtime` and `/health` intentionally keep raw/literal machine-facing reason strings in JSON while the visible HTML copy is translated in `dashboard.py`; this is correct, but future agents need to remember the split.
- Explorer result cards still keep a concise latest-probe display. The page-level warning is now honest, but per-card degraded-probe wording could become richer later if it adds value without bloating the grid.

## Follow-ups

- Use the S06 UAT flow during S07, but run it against the real VPS base URL and a live long-running database instead of the seeded local DB.
- If live anti-bot pressure shifts from challenge pages toward transport failures or scan failures, extend `runtime_status().acquisition` rather than inventing new page-local heuristics.
- Consider whether explorer cards should eventually surface a short per-card degraded-probe badge once the live product needs more inline acquisition nuance.

## Files Created/Modified

- `vinted_radar/parsers/item_page.py` — added explicit challenge-aware probe classification.
- `vinted_radar/services/state_refresh.py` — added proxy-aware refresh construction and structured probe summaries.
- `vinted_radar/services/runtime.py` — persisted state-refresh summaries on runtime cycles and forwarded proxy pools into state refresh.
- `vinted_radar/repository.py` — added repository-owned acquisition-health aggregation and threaded it into runtime/overview contracts.
- `vinted_radar/dashboard.py` — surfaced degraded acquisition truth across overview, explorer, detail, runtime, `/api/runtime`, and `/health`.
- `vinted_radar/cli.py` — exposed proxy-aware `state-refresh` and richer runtime/state-refresh CLI output.
- `README.md` — documented degraded acquisition visibility and proxy-aware state refresh.
- `.gsd/milestones/M002/slices/S06/S06-UAT.md` — recorded the repeatable served-browser UAT flow for S06.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marked S06 complete.
- `.gsd/PROJECT.md` — updated the living project state to include the completed degraded-mode slice.
- `.gsd/KNOWLEDGE.md` — appended the degraded-acquisition repository-owned pattern for future slices.
- `.gsd/REQUIREMENTS.md` — refreshed R011 with S06 proof while keeping final live acceptance for S07.
- `.gsd/DECISIONS.md` — recorded the S06 degraded-acquisition honesty architecture and restored the missing S05 detail-route decision.

## Forward Intelligence

### What the next slice should know
- The cleanest local proof path for degraded-mode honesty is still the seeded `data/vinted-radar-s06.db` server on `8786`, because it exercises all six surfaces against the same persisted runtime/acquisition contract.

### What's fragile
- The product-layer translation of acquisition reasons in `dashboard.py` — the machine JSON remains literal by design, so future wording changes should stay in the product layer instead of mutating repository/runtime payload semantics.
- `latest_cycle` ordering in runtime tests when two cycles start in the same second — use `acquisition.latest_cycle_id` for the authoritative degraded acquisition cycle rather than assuming the lexicographically latest cycle row is the one with the state-refresh summary you care about.

### Authoritative diagnostics
- `repository.runtime_status()['acquisition']` — the single best machine-readable truth for degraded acquisition status, reasons, and example probes.
- `/api/runtime` and `/health` — quickest served-route comparison when HTML copy feels suspicious.
- `.gsd/milestones/M002/slices/S06/S06-UAT.md` — repeatable human-flow proof for the slice.

### What assumptions changed
- “If the scheduler is healthy, the acquisition story will feel healthy enough in the UI.” — false; S06 needed a separate acquisition-health contract because the controller can be perfectly scheduled while page-level probes are degraded.
- “Generic `unknown` probe outcomes are good enough for product honesty.” — false; anti-bot/challenge-shaped failures need to stay explicit or the product quietly overstates the quality of its direct evidence.
