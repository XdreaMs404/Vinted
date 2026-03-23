---
id: S05
parent: M002
milestone: M002
provides:
  - A narrative-first listing detail contract and HTML route with progressive proof disclosures
requires:
  - slice: S01
    provides: French overview language, honesty vocabulary, and brownfield detail compatibility seams
  - slice: S03
    provides: shared shell, responsive layout contract, and mounted detail route structure
  - slice: S04
    provides: explorer context preservation and the authoritative explorer → detail analytical loop
affects:
  - S06
  - S07
key_files:
  - vinted_radar/dashboard.py
  - tests/test_dashboard.py
  - README.md
  - .gsd/milestones/M002/slices/S05/S05-UAT.md
key_decisions:
  - D029: keep `/api/listings/<id>` as raw proof while layering narrative/provenance in `dashboard.py` and rendering HTML detail as narrative-first with progressive proof disclosures.
patterns_established:
  - Translate visible proof copy in the product layer while leaving raw proof semantics literal in JSON and core engines.
observability_surfaces:
  - /listings/<id>
  - /api/listings/<id>
  - tests/test_dashboard.py
  - .gsd/milestones/M002/slices/S05/S05-UAT.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
---

# S05: Listing Detail Narrative + Progressive Proof

**Turned `/listings/<id>` from a proof-first detail dump into a French narrative reading with explicit provenance/prudence and disclosure-based proof, then re-proved the explorer → detail → return loop on desktop and mobile.**

## What Happened

S05 started from a brownfield detail route that already had the data but still read like an internal proof panel. The first task kept the existing evidence semantics intact and added a reusable `narrative` + `provenance` contract on top of the detail payload. That contract now translates state, score, timing, seller, and engagement inputs into a broader-audience reading while keeping the raw `state_explanation`, `score_explanation`, `history`, and `transitions` available in JSON.

The second task rebuilt the HTML detail route around that contract. The page now leads with `Ce que le radar voit d’abord`, keeps the active explorer context visible, surfaces prudence/provenance before the technical proof, and pushes the proof itself behind `Preuve d’état`, `Contexte de score`, and `Chronologie radar` disclosures. Browser QA exposed two real quality seams — visible proof reasons still leaking English from `state_machine.py`, and small grammar issues in the visible provenance copy — so the product layer now translates those proof reasons/factor labels without mutating the raw proof engines.

The final task updated README and wrote a slice-specific UAT file so the richer workflow is reproducible. The slice was then re-proven against `data/vinted-radar-s04.db`: filtered explorer open, listing drill-down, narrative detail, translated proof disclosure, return to the same explorer URL, and a mobile no-overflow check.

## Verification

The slice passed automated route coverage plus browser proof on the local S04 demo DB.

## Requirements Advanced

- R004 — the detail route now keeps observed vs inferred vs estimated vs radar-timestamp boundaries visible in broader-audience language instead of burying them in raw proof blocks.
- R009 — the overview/explorer/detail information architecture is stronger because detail now reads like a first-class product surface rather than a secondary debugger view.
- R012 — the product utility deepens beyond browsing by giving each listing a readable interpretation plus accessible proof.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The slice plan did not explicitly call for translating visible proof reasons and score-factor labels, but browser QA showed that leaving the disclosure panels in mixed English/French would violate the slice’s plain-language promise. That translation stayed in the product layer only; the raw proof JSON and core semantics were left untouched.

## Known Limitations

- The detail route is now productized, but it still builds from `load_listing_scores()` at request time rather than a fully SQL-first detail seam; S05 improved readability and provenance, not the remaining detail-path scalability posture.
- S06 still needs degraded acquisition and partial-signal messaging to flow through the richer detail route, not just the underlying runtime/repository data.
- S07 still needs mounted/VPS proof on the fully assembled product, not just local proof on `data/vinted-radar-s04.db`.

## Follow-ups

- Revisit the remaining request-time detail-path scoring/loading seam when detail-route scalability becomes the active risk again.
- If `state_machine.py` reason strings change, update the product-layer translations in `dashboard.py` before treating the detail route as French-complete.
- Reuse the S05 UAT path during S07 so final acceptance re-proves explorer context, narrative detail, proof disclosures, and return-to-results on the real VPS entrypoint.

## Files Created/Modified

- `vinted_radar/dashboard.py` — added narrative/provenance detail payload sections, rebuilt the detail HTML hierarchy, translated visible proof copy, and added disclosure panels.
- `tests/test_dashboard.py` — added/updated detail payload and route assertions for narrative structure, provenance boundaries, and final HTML wording.
- `README.md` — documented the richer listing-detail workflow and JSON contract shape.
- `.gsd/milestones/M002/slices/S05/S05-UAT.md` — recorded the repeatable S05 explorer → detail → proof → return UAT flow.
- `.gsd/DECISIONS.md` — appended D029 for the narrative-layer/progressive-proof detail architecture.
- `.gsd/KNOWLEDGE.md` — added the rule to keep raw proof semantics in JSON and translate only the visible HTML proof layer.

## Forward Intelligence

### What the next slice should know
- The strongest local proof path for detail work is still the filtered S04 explorer URL on `data/vinted-radar-s04.db`, because it exercises context preservation and the real user loop instead of an isolated `/listings/<id>` open.

### What's fragile
- Product-layer translation of state reasons in `vinted_radar/dashboard.py` — it depends on matching the current English `state_machine.py` reason strings, so upstream wording changes can silently desync the visible French proof layer.
- The detail route’s request-time `load_listing_scores()` dependency — it remains a scalability seam even though the route is now much more usable.

### Authoritative diagnostics
- `tests/test_dashboard.py` — quickest regression alarm for the narrative/provenance/detail-route contract.
- `.gsd/milestones/M002/slices/S05/S05-UAT.md` — the most trustworthy local human-flow proof for this slice.
- `/api/listings/<id>` — authoritative raw proof + narrative/provenance payload when the HTML route feels suspicious.

### What assumptions changed
- “Moving proof behind disclosures is enough for S05.” — false; the disclosure panels still leaked mixed-language internals until the product layer translated visible proof reasons and factor labels.
