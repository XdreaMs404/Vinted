---
id: T02
parent: S05
milestone: M002
provides:
  - A narrative-first HTML listing detail page with progressive proof disclosures
  - A French-visible proof layer for state reasons and score factors without changing the underlying JSON/state semantics
key_files:
  - vinted_radar/dashboard.py
  - tests/test_dashboard.py
key_decisions:
  - Keep the detail route inside the shared S03 shell, but move technical proof behind `<details>` disclosures instead of leading with proof blocks and raw jargon.
patterns_established:
  - The HTML detail route should consume the narrative JSON contract and translate proof-only sections in the product layer while leaving raw proof structures intact for diagnostics.
observability_surfaces:
  - /listings/<id>
  - tests/test_dashboard.py
  - browser assertions on the S04 demo DB
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: Rebuild the HTML listing detail as a narrative-first page with progressive proof

**Rebuilt `/listings/<id>` so the page now starts with a product reading and explorer context, then reveals state/score/history proof through accessible disclosures instead of proof-first panels.**

## What Happened

I rewired the detail body around the new `narrative` and `provenance` payload sections from T01.

The page now opens with:
- a narrative hero (`Ce que le radar voit d’abord`)
- a visible explorer-context block that explains why the listing was opened from the current filtered slice
- four readable interpretation cards for radar reading, market reading, timing, and public visibility
- an explicit prudence/provenance zone before the technical proof starts

The proof layer moved into disclosure panels:
- `Preuve d’état`
- `Contexte de score`
- `Chronologie radar`

I also translated the visible proof copy that was still leaking internal English/state-machine vocabulary. The JSON contract still keeps the raw `state_explanation` and `score_explanation`, but the HTML route now renders French-facing explanations for state reasons, factor labels, and provenance summaries.

The browser pass caught two real quality issues that the tests did not surface immediately:
1. visible proof reasons still came through in English because they were rendered straight from `state_machine.py`
2. the provenance summary and observation count had small grammar seams (`Lecture actif`, `observation(s)`)

Both were fixed in the product-layer helpers before closing the task.

## Verification

Automated dashboard/dashboard-cli coverage passed, then browser checks on the S04 demo DB confirmed the new hierarchy on desktop and mobile, successful proof disclosure, preserved context actions, and clean console/network state.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py` | 0 | PASS | 1.08s |
| 2 | Browser open + detail flow at `http://127.0.0.1:8784/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12` | n/a | PASS | interactive |
| 3 | Browser assertion: detail headings/text visible + `no_console_errors` + `no_failed_requests` | n/a | PASS | interactive |
| 4 | Mobile overflow check `document.documentElement.scrollWidth <= window.innerWidth` | n/a | PASS | interactive |

## Diagnostics

Use `/listings/<id>` against `data/vinted-radar-s04.db` as the authoritative visual proof path. If the detail route regresses, check `tests/test_dashboard.py` first, then inspect the browser-visible sections `Ce que le radar voit d’abord`, `Repères et limites visibles`, and `Preuves techniques et détails`.

## Deviations

The task ended up translating visible proof reasons and factor labels as part of the HTML work. The written plan only required progressive disclosure structure, but the browser QA showed that leaving the proof copy in mixed English/French would undercut the slice’s plain-language promise.

## Known Issues

README and slice-level UAT still need to be updated so the richer explorer → detail → proof flow is documented and repeatable for future agents/testers.

## Files Created/Modified

- `vinted_radar/dashboard.py` — rebuilt the detail HTML hierarchy, added disclosure panels, translated visible proof copy, and tightened provenance text.
- `tests/test_dashboard.py` — updated detail-route assertions to match the new narrative-first structure and proof affordances.
