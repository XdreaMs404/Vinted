---
id: T03
parent: S05
milestone: M002
provides:
  - README guidance for the richer listing-detail workflow
  - A repeatable S05 UAT flow for explorer → detail → proof → return verification
key_files:
  - README.md
  - .gsd/milestones/M002/slices/S05/S05-UAT.md
  - tests/test_dashboard.py
  - tests/test_dashboard_cli.py
key_decisions:
  - Treat the filtered explorer URL on `data/vinted-radar-s04.db` as the authoritative local proof path for S05, because it exercises context preservation, narrative reading, proof disclosures, and return-to-results in one loop.
patterns_established:
  - Slice UAT for detail work should prove the full explorer-context loop, not just open `/listings/<id>` in isolation.
observability_surfaces:
  - README.md
  - .gsd/milestones/M002/slices/S05/S05-UAT.md
  - browser assertions on the local 8784 server
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: Document and prove the richer explorer-to-detail workflow

**Documented the new detail workflow, wrote slice-level UAT, and re-proved the full explorer → detail → proof → return loop on the S04 demo DB in desktop and mobile conditions.**

## What Happened

I updated `README.md` so the listing detail route is no longer described as a bare HTML endpoint. The docs now explain the actual behavior: explorer-context preservation, `Retour aux résultats`, narrative-first reading, visible prudence/provenance, and proof disclosures.

I then wrote `.gsd/milestones/M002/slices/S05/S05-UAT.md` around the real flow this slice owns:
- open a filtered explorer slice
- drill into a listing detail page
- verify narrative-first reading
- verify provenance/prudence before proof
- open proof panels
- return to the same explorer context
- confirm mobile consultability

Finally, I re-ran the automated suite and completed the browser proof on `http://127.0.0.1:8784` against `data/vinted-radar-s04.db`. That browser pass explicitly covered:
- explorer → detail navigation with preserved query state
- narrative detail headings and translated proof copy
- no console errors or failed requests
- mobile no-overflow verification
- `Retour aux résultats` taking the user back to the same filtered explorer URL

## Verification

Automated dashboard coverage passed again after the doc-aligned assertions, and browser verification confirmed the real user flow end to end on the demo DB.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py && test -s README.md && test -s .gsd/milestones/M002/slices/S05/S05-UAT.md` | 0 | PASS | 1.01s |
| 2 | Browser verification on `http://127.0.0.1:8784/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12` | n/a | PASS | interactive |
| 3 | Browser assertion: detail texts visible + `no_console_errors` + `no_failed_requests` | n/a | PASS | interactive |
| 4 | Browser assertion: `Retour aux résultats` returns to the same explorer URL | n/a | PASS | interactive |
| 5 | Mobile overflow check via `document.documentElement.scrollWidth <= window.innerWidth` | n/a | PASS | interactive |

## Diagnostics

For future verification, start the local server on port `8784` against `data/vinted-radar-s04.db` and follow `.gsd/milestones/M002/slices/S05/S05-UAT.md`. That file now documents the strongest local proof path for this slice.

## Deviations

None.

## Known Issues

The slice is documented and locally proven, but final mounted/VPS acceptance for the fully assembled M002 product still belongs to S07.

## Files Created/Modified

- `README.md` — documented the actual narrative/proof listing-detail workflow rather than only the route path.
- `.gsd/milestones/M002/slices/S05/S05-UAT.md` — added repeatable UAT instructions for the richer detail flow.
- `tests/test_dashboard.py` — remained aligned with the final detail-route structure and wording.
- `tests/test_dashboard_cli.py` — stayed green after the detail-route/documentation changes.
