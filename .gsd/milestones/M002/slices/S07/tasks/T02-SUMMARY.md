---
id: T02
parent: S07
milestone: M002
provides:
  - Mounted realistic-corpus desktop/mobile proof for overview, explorer, detail, runtime, and the shared `/radar` route contract
key_files:
  - .gsd/milestones/M002/slices/S07/S07-UAT.md
  - .gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md
  - .artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json
  - .artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip
key_decisions:
  - Treat the mounted localhost `/radar` proof over `data/m001-closeout.db` as the strongest available pre-closeout evidence until the true public VPS URL is provided.
patterns_established:
  - Use a realistic proof DB (`data/m001-closeout.db`) plus the mounted `/radar` contract to catch issues that seeded slice DBs never expose: route latency, browser readability on dense surfaces, and product-layer text fidelity.
observability_surfaces:
  - MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428
  - http://127.0.0.1:8790/radar/
  - http://127.0.0.1:8790/radar/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12
  - http://127.0.0.1:8790/radar/listings/64882428?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12
  - http://127.0.0.1:8790/radar/runtime
  - .artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json
  - .artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: Re-prove the assembled product on a realistic mounted corpus across desktop and mobile

**Re-proved the assembled M002 product on the mounted `/radar` shell over the 49,759-listing `m001-closeout.db` corpus, including overview, explorer, detail, runtime, mounted smoke, and desktop/mobile browser verification.**

## What Happened

With the large-corpus regressions removed, I reran S07 at the assembled product level instead of stopping at tests.

I served `data/m001-closeout.db` through the mounted contract:

```bash
MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard \
  --db data/m001-closeout.db \
  --host 127.0.0.1 \
  --port 8790 \
  --base-path /radar \
  --public-base-url http://127.0.0.1:8790/radar
```

I picked real listing id `64882428` from the large DB and ran the mounted smoke harness. It passed for overview, explorer, runtime, detail HTML, detail JSON, and health.

I then browser-verified the assembled shell on desktop:

- overview: `Ce qui bouge maintenant sur le radar Vinted.`, `acquisition dégradée`, 49,759 tracked listings, no console or network errors
- explorer: `Parcourir, comparer et filtrer le corpus réel.`, `635 annonces`, mounted filters, degraded acquisition badge, no console or network errors
- detail: `Poncho d'été`, `Lecture radar : encore visible`, preserved explorer context (`Vue active — Racine : Femmes ...`), no console or network errors
- runtime: `Le contrôleur vivant du radar`, `au repos`, `acquisition dégradée`, `Santé d’acquisition`, no console or network errors

Then I switched to mobile viewport and re-ran the core phone-proof routes:

- overview: hero, pills, and stacked navigation stayed readable on 390×844
- runtime: hero, pills, and shell navigation remained readable on the same mobile width
- detail: post-fix mobile detail proof confirmed the cleaned `Femmes > Vêtements > ...` category path and preserved explorer context

I persisted the browser artifacts under `.artifacts/browser/2026-03-23T16-41-39-152Z-session/`, including a final timeline and trace zip.

## Verification

Mounted smoke passed on the realistic corpus, the full test suite remained green, and browser assertions passed across desktop + mobile without app console or network failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428` | 0 | PASS | realistic mounted smoke |
| 2 | `browser_assert` on desktop overview | n/a | PASS | route + text + no console/network errors |
| 3 | `browser_assert` on desktop explorer | n/a | PASS | route + text + no console/network errors |
| 4 | `browser_assert` on desktop detail | n/a | PASS | route + title + context + no console/network errors |
| 5 | `browser_assert` on desktop runtime | n/a | PASS | route + text + acquisition/runtime truth + no console/network errors |
| 6 | `browser_assert` on mobile overview | n/a | PASS | route + hero + nav + no console/network errors |
| 7 | `browser_assert` on mobile runtime | n/a | PASS | route + hero + nav + no console/network errors |
| 8 | `browser_assert` on post-fix mobile detail` | n/a | PASS | route + `Poncho d'été` + cleaned `Vêtements` context |

## Diagnostics

The authoritative mounted realistic proof now lives in:

- `.gsd/milestones/M002/slices/S07/S07-UAT.md`
- `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json`
- `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip`

If the mounted shell later looks wrong, first rerun `verify_vps_serving.py` on `http://127.0.0.1:8790/radar`, then compare the four HTML routes before assuming the repository contract drifted.

## Deviations

The first browser proof exposed visible mojibake strongly enough that I added one more post-fix mobile detail verification after T01. That stayed inside slice scope because it verified the corrected user-facing HTML on the same mounted acceptance path.

## Known Issues

This task still does not prove the true public VPS URL. It proves the strongest local mounted equivalent available from the current environment.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S07/S07-UAT.md` — recorded the repeatable mounted realistic UAT path.
- `.gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md` — captured the mounted realistic browser/smoke proof.
- `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json` — final browser action timeline.
- `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip` — browser trace artifact for the mounted proof.
