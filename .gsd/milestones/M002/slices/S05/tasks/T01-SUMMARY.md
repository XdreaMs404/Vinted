---
id: T01
parent: S05
milestone: M002
provides:
  - A narrative-first JSON contract for `/api/listings/<id>` that stays grounded in the existing state, score, timing, seller, and engagement evidence
key_files:
  - vinted_radar/dashboard.py
  - tests/test_dashboard.py
key_decisions:
  - Keep the new plain-language layer in `dashboard.py` on top of the existing proof payload instead of changing scoring or state semantics for UI convenience.
patterns_established:
  - Detail narration should be derived from the evidence payload once and exposed in JSON so HTML and future consumers share the same grounded reading.
observability_surfaces:
  - /api/listings/<id>
  - tests/test_dashboard.py
  - python -m pytest tests/test_dashboard.py -k detail
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: Add a narrative listing-detail contract on top of the proof payload

**Added a narrative layer to `/api/listings/<id>` that translates the existing proof into French product language while keeping provenance boundaries and the raw proof intact.**

## What Happened

I kept the brownfield seam intact: `build_listing_detail_payload()` still starts from the existing state/scoring/history inputs, but it now assembles `narrative` and `provenance` sections before returning the detail payload.

The narrative layer now exposes:
- a radar reading headline and summary
- market, timing, and public-visibility highlight blocks
- explicit risk notes when the state is inferred, premium context is thin, publication timing is only estimated, or public card fields are incomplete
- a proof guide so the later HTML route can progressively reveal technical detail without inventing new logic

I also added a dedicated provenance block that separates three boundaries the milestone cares about: state signal, publication timing, and radar observation window. That keeps the JSON truthful about what is observed, what is inferred, what is estimated, and what comes from the local radar timeline.

The tests now assert on the new narrative/provenance contract and still guard explorer-context preservation, so later HTML work can safely consume this richer payload.

## Verification

Targeted detail tests passed first, then the broader dashboard/dashboard-cli suite stayed green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py -k detail` | 0 | PASS | 0.25s |
| 2 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | PASS | 1.08s |

## Diagnostics

Use `/api/listings/<id>` as the authoritative contract check: it now contains `narrative` and `provenance` alongside the raw `state_explanation`, `score_explanation`, `history`, and `transitions`. `tests/test_dashboard.py` is the quickest drift alarm if a future change collapses those boundaries.

## Deviations

None.

## Known Issues

The HTML route still renders the old proof-first body. T02 still needs to consume the new narrative contract and move the technical proof behind progressive disclosure.

## Files Created/Modified

- `vinted_radar/dashboard.py` — added narrative/provenance builders and extended the listing-detail payload.
- `tests/test_dashboard.py` — added payload assertions for the narrative/provenance contract and integrated JSON route coverage.
