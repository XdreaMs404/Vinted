---
id: M001
title: Listing-Level Market Radar
verification_result: needs-attention
completed_at: 2026-03-22
requirement_outcomes:
  - id: R004
    from_status: active
    to_status: validated
    proof: S05 dashboard verification plus current browser verification confirmed visible coverage, freshness, confidence, and listing-detail evidence on the main product surface.
  - id: R005
    from_status: active
    to_status: validated
    proof: S04 and S05 delivered demand-led rankings with score explanations, and the current dashboard still renders demand proof from repository-backed evidence.
  - id: R006
    from_status: active
    to_status: validated
    proof: S04 and S05 delivered a separate premium ranking with contextual-price explanations, and the current dashboard still renders that split cleanly.
  - id: R008
    from_status: active
    to_status: validated
    proof: S04 introduced market-summary payloads and S05 rendered performing and rising segment modules on the main dashboard.
  - id: R009
    from_status: active
    to_status: validated
    proof: S05 browser verification and current closeout verification confirmed a mixed dashboard with filters, ranking tables, and listing-detail drill-down.
  - id: R010
    from_status: active
    to_status: validated
    proof: S06 live verification proved batch and continuous modes with persisted runtime diagnostics through the CLI, /api/runtime, /health, and the dashboard runtime card.
---

# M001: Listing-Level Market Radar

**Implementation is complete and the assembled stack works end to end, but milestone verification remains `needs-attention` because the multi-day credibility criterion is not yet backed by a healthy, readable multi-day market corpus.**

## What Happened

M001 assembled the first full local Vinted radar across six slices. The repository now has a real discovery pipeline, per-run observation history, cautious state derivation with direct item-page probes, explainable demand and premium scoring, a server-rendered dashboard with truthful JSON diagnostics, and top-level `batch` / `continuous` operator commands backed by persisted `runtime_cycles` in SQLite.

Closeout verification re-checked the integrated system against live behavior instead of relying only on slice artifacts. The current codebase passes the full automated suite (`100 passed`), a fresh live `batch` cycle still completes successfully against public Vinted data, the resulting DB still supports coverage/state/market-summary queries, and the local dashboard still renders market summary, rankings, runtime state, and listing detail without console or network errors.

The remaining gap is elapsed-runtime proof. The code supports multi-day operation, and `data/vinted-radar.db` shows runtime metadata spanning 2026-03-20 through 2026-03-22, but the listing-history tables in that DB are malformed and cannot support trustworthy market-read sign-off. The older `data/m001-closeout.db` is also not openable through the current repository bootstrap path because schema/index creation now expects `listings.created_at_ts` before the migration adds it. That leaves M001 with strong implementation proof but incomplete healthy multi-day evidence.

## Success Criteria Audit

### 1) A local user can run the radar and see a mixed dashboard that combines market summary, listing rankings, coverage, freshness, and confidence surfaces.
**Verdict:** MET

**Evidence:**
- S05 shipped the mixed dashboard and browser-verified it against a live DB.
- Current closeout verification used `python -m vinted_radar.cli batch --db data/m001-verify.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --request-delay 0.0` followed by `python -m vinted_radar.cli dashboard --db data/m001-verify.db --host 127.0.0.1 --port 8780`.
- Browser verification at `http://127.0.0.1:8780` confirmed visible market summary, runtime, freshness, confidence, demand/premium proof tables, and a populated listing detail panel with no console errors and no failed requests.

### 2) The system preserves historical observations for listings and exposes first seen, last seen, revisit cadence, and listing evolution over time.
**Verdict:** MET

**Evidence:**
- S02 added `listing_observations`, migration/backfill behavior, and CLI freshness / revisit-plan / history inspection surfaces.
- S06 made repeated cycles operational through `batch`, `continuous`, and persisted `runtime_cycles`.
- The current suite includes passing coverage for history and runtime behavior (`tests/test_history_repository.py`, `tests/test_history_cli.py`, `tests/test_runtime_service.py`, `tests/test_runtime_cli.py`).

### 3) Listing states are cautious, traceable, and explicit about what was observed versus inferred.
**Verdict:** MET

**Evidence:**
- S03 shipped the cautious state engine over observation history plus `item_page_probes`.
- Passing state tests (`tests/test_state_machine.py`, `tests/test_state_cli.py`) cover the taxonomy and explanation surfaces.
- Current closeout verification against `data/m001-verify.db` showed `state-summary --format json` returning explicit state counts, observed basis, and confidence counts.

### 4) The “demande pure” and “premium” rankings are explainable and backed by visible listing evidence rather than simplistic likes or recency sorting.
**Verdict:** MET

**Evidence:**
- S04 shipped explainable `demand` and `premium` scores with explicit context thresholds and no-context fallback.
- S05 rendered both proof tables and listing-detail score explanations on the dashboard.
- Current closeout verification against `data/m001-verify.db` showed `market-summary --format json` and the live dashboard still rendering separate demand and premium proof surfaces from the same repository-backed payloads.

### 5) After several days of real local runtime, the product provides a market read that is already useful for judging which sub-categories and listings are moving now.
**Verdict:** NOT MET

**Evidence:**
- `data/vinted-radar.db` does show persisted runtime metadata over three distinct days (`runtime_cycles.started_at` from `2026-03-20T08:34:50+00:00` to `2026-03-22T05:08:00+00:00`; `discovery_runs.started_at` over the same span), which proves the operator loop has run over multiple days.
- However, the same DB has malformed listing-history tables, so the multi-day market corpus cannot be queried truthfully for closeout verification.
- `data/m001-closeout.db` remains a one-day corpus (`listing_observations.observed_at` from `2026-03-18T11:56:10+00:00` to `2026-03-18T19:44:03+00:00`), so it does not retire the elapsed-runtime criterion either.

**Conclusion:** the implementation supports multi-day use, but the milestone does not yet have a healthy, readable multi-day evidence DB that proves the market read is already useful after several days.

## Definition of Done Audit

- **All slice deliverables are complete with substantive implementation rather than placeholders:** MET  
  All six slice summaries exist (`S01` through `S06`), and the current test suite passed with `100 passed`.
- **Discovery, history, cautious state logic, scoring, and UI surfaces are actually wired together:** MET  
  The current `batch` run produced a fresh DB that was immediately queryable through `coverage`, `state-summary`, `market-summary`, `runtime-status`, and the dashboard.
- **The real local entrypoints for batch mode, continuous mode, and dashboard access exist and are exercised:** MET  
  S06 live verification already exercised `batch`, `continuous --dashboard`, `/api/runtime`, `/api/dashboard`, and `/health`; current closeout verification re-exercised `batch` and the dashboard successfully.
- **Success criteria are re-checked against live behavior and persisted runtime evidence, not only artifacts or fixtures:** MET AS AN AUDIT STEP  
  This closeout explicitly re-ran tests, a live batch cycle, JSON diagnostics, and browser checks, and also inspected persisted multi-day runtime evidence in existing DBs.
- **Final integrated acceptance scenarios pass against real public Vinted observations gathered over time:** NOT MET  
  The code path is real and integrated, but the healthy readable proof corpus still does not span several distinct observation days.

**Overall milestone definition of done verdict:** `needs-attention`

## Requirement Outcome Verification

### Confirmed status transitions
- **R004: active → validated**  
  Supported by S05 dashboard/browser verification and current closeout browser verification showing visible coverage, freshness, confidence, and listing-detail evidence.
- **R005: active → validated**  
  Supported by S04 ranking logic, S05 dashboard proof tables, and current live dashboard confirmation of demand-backed listing proof.
- **R006: active → validated**  
  Supported by S04 premium logic, S05 dashboard proof, and current live dashboard confirmation of separate premium ranking behavior.
- **R008: active → validated**  
  Supported by S04 market-summary generation and S05 rendering of performing/rising segment modules on the main product surface.
- **R009: active → validated**  
  Supported by S05 browser verification and current listing-detail verification on the live dashboard.
- **R010: active → validated**  
  Supported by S06 live verification of `batch`, `continuous`, `runtime-status`, `/api/runtime`, `/health`, and the dashboard runtime card.

### Requirements that remain active after M001 closeout
- **R001** remains active. Public discovery exists and was live-verified, but the milestone-level multi-day credibility proof is not yet healthy enough to close out the full radar promise.
- **R002** remains active. Revisit history exists and is operational, but the final elapsed-runtime proof remains incomplete.
- **R003** remains active. The cautious state engine works and is tested, but the final milestone still lacks healthy multi-day live state evolution evidence.
- **R007** remains active by design. M001 intentionally shipped only the first lightweight contextualization layer, with richer contextualization deferred to M002.
- **R011** remains active. Graceful degradation exists across discovery, state, scoring, and runtime surfaces, but closeout also exposed a schema/bootstrap regression on older DBs that must be addressed before this requirement can be considered fully retired.

## Verification

- `python -m pytest` → **100 passed**
- `python -m vinted_radar.cli batch --db data/m001-verify.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --request-delay 0.0`
  - completed batch cycle
  - 192 sightings
  - 40 unique listing IDs
  - 2 successful scans / 0 failed scans
  - 4 state probes
- `python -m vinted_radar.cli runtime-status --db data/m001-verify.db --format json`
  - confirmed persisted completed `runtime_cycles` state for the live batch run
- `python -m vinted_radar.cli coverage --db data/m001-verify.db --format json`
  - confirmed persisted Homme/Femme coverage counts from the live run
- `python -m vinted_radar.cli state-summary --db data/m001-verify.db --format json`
  - confirmed active/high-confidence/observed-basis state counts from the live run
- `python -m vinted_radar.cli market-summary --db data/m001-verify.db --limit 8 --format json`
  - confirmed performing and rising segment output from the live run
- Browser verification at `http://127.0.0.1:8780`
  - dashboard rendered market summary, runtime, freshness, confidence, and ranking proof surfaces
  - clicking `Inspect` populated the listing detail panel
  - explicit browser assertions passed for visible detail selectors, visible table selectors, zero console errors, and zero failed requests
- Direct SQLite evidence audit
  - `data/vinted-radar.db` shows multi-day runtime metadata across 3 distinct days, but listing-history tables are malformed
  - `data/m001-closeout.db` is still only a same-day corpus and currently fails to open through the repository bootstrap path

## Deviations

- The assembled codebase no longer uses the original S01 SSR catalog-page path as the primary listing discovery surface. Discovery now flows through `https://www.vinted.fr/api/v2/catalog/items`, while public item pages remain a separate evidence path for state resolution.
- Closeout live verification used a fresh `data/m001-verify.db` because the older closeout DBs were not suitable as truthful current proof surfaces.

## Known Limitations

- Milestone verification does not pass yet because the “several days of real local runtime” criterion still lacks a healthy, readable multi-day market corpus.
- Older SQLite DBs that predate the `listings.created_at_ts` column can fail to open through the current repository bootstrap path because schema index creation now references that column before the migration adds it.
- The existing multi-day DB (`data/vinted-radar.db`) cannot serve as closeout proof because its listing-history tables are malformed.

## Follow-ups

- Fix schema bootstrap / migration ordering so older SQLite DBs remain openable.
- Rebuild or recover a healthy multi-day proof DB, then rerun M001 closeout verification against that corpus.
- Carry the evidence-first runtime and drill-down patterns into M002 without losing truthful diagnostics while the UX becomes broader and less operator-centric.

## Files Created/Modified

- `.gsd/milestones/M001/M001-SUMMARY.md` — milestone closeout summary and verification audit.
- `.gsd/PROJECT.md` — updated project state after M001 closeout.
- `.gsd/KNOWLEDGE.md` — appended closeout lessons on schema migration ordering and proof DB health.
- `.gsd/STATE.md` — moved the project out of active M001 closeout and into handoff state.

## Forward Intelligence

### What the next milestone should know
- The current M001 implementation is operational and integrated: new DBs work, batch cycles still succeed live, and the dashboard still reflects repository-backed truth cleanly.
- Multi-day operator metadata alone is not enough for milestone sign-off; future closeout proof must preserve queryable listing history and state evidence, not only runtime-cycle timestamps.
- The dashboard/runtime truth split established in S05/S06 remains sound and should survive the richer M002 UX redesign.

### What is fragile
- Backward compatibility for older SQLite files is currently weaker than the slice summaries imply because schema/index creation can outrun migrations.
- Acquisition throughput now depends on the Vinted web catalog API path remaining usable enough for local operation.

### Authoritative diagnostics
- `python -m vinted_radar.cli batch --db data/m001-verify.db ...` — fastest truthful end-to-end live proof on a fresh DB.
- `python -m vinted_radar.cli runtime-status --db <path> --format json` — operator truth for current cycles.
- `http://127.0.0.1:8780/api/dashboard` and `http://127.0.0.1:8780/api/runtime` — exact dashboard-backed JSON surfaces for current local verification.
