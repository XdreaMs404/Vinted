# S07: Live VPS End-to-End Acceptance Closure

**Goal:** Re-prove the assembled M002 product on a realistic large corpus through the mounted serving path, remove the performance and presentation regressions that appear only at that scale, and close the remaining gap to the true public VPS entrypoint with one explicit live acceptance step.
**Demo:** 1) Run `MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard --db data/m001-closeout.db --host 127.0.0.1 --port 8790 --base-path /radar --public-base-url http://127.0.0.1:8790/radar`; 2) run `python -m pytest -q`; 3) run `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428`; 4) browser-verify desktop and mobile on `/radar/`, `/radar/explorer?...`, `/radar/listings/64882428?...`, and `/radar/runtime`; 5) once the real public VPS URL is available, rerun the same smoke/UAT flow against that public base URL and record the result.

## Must-Haves

- Large-corpus mounted serving must stay usable enough to support S07 acceptance; obvious route-level performance regressions found only on the realistic DB must be fixed before claiming closeout.
- The mounted shell must stay truthful and French-first on overview, explorer, detail, and runtime across desktop and mobile, including degraded acquisition visibility and context-preserving detail navigation.
- The repo must retain one explicit final acceptance step for the true public VPS base URL instead of pretending local mounted proof is identical to real remote proof.

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest -q`
- `MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard --db data/m001-closeout.db --host 127.0.0.1 --port 8790 --base-path /radar --public-base-url http://127.0.0.1:8790/radar`
- `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428`
- Browser verification at `http://127.0.0.1:8790/radar/`, `/radar/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`, `/radar/listings/64882428?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`, and `/radar/runtime` on desktop + mobile.
- Final external closeout: rerun `python scripts/verify_vps_serving.py --base-url <public-vps-url> --listing-id <live-id>` plus browser/UAT against the real public VPS URL once access is provided.

## Observability / Diagnostics

- Runtime signals: realistic route timings on `data/m001-closeout.db`, persisted runtime/acquisition status from `/api/runtime` and `/health`, and the mounted smoke verifier over `/radar`.
- Inspection surfaces: `scripts/verify_vps_serving.py`, `http://127.0.0.1:8790/radar/*`, `.artifacts/browser/2026-03-23T16-41-39-152Z-session/`, and the large local proof DB `data/m001-closeout.db`.
- Failure visibility: slow route timings, mounted-route mismatches, browser console/network failures, and mojibake in visible HTML all stay inspectable and reproducible.
- Redaction constraints: do not expose proxy credentials, SSH secrets, or external VPS secrets in logs, docs, or summaries.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/repository.py`, `vinted_radar/dashboard.py`, `scripts/verify_vps_serving.py`, `README.md`, the M002 S03/S05/S06 serving/detail/runtime contracts, and `data/m001-closeout.db` as the realistic local proof corpus.
- New wiring introduced in this slice: connection-local materialized overview snapshot reuse for mounted large-corpus pages, one generated-at contract per payload, visible-text mojibake repair in HTML, and a Windows-safe mounted serving/operator note in the README.
- What remains before the milestone is truly usable end-to-end: true public VPS proof is still blocked until the public base URL or read-only VPS access is provided.

## Tasks

- [x] **T01: Harden mounted large-corpus serving for realistic S07 acceptance** `est:3h`
  - Why: the first realistic mounted proof on `data/m001-closeout.db` surfaced route latencies that were still too high for credible closeout, plus a Git Bash `/radar` path-conversion trap and visible mojibake in HTML.
  - Files: `vinted_radar/repository.py`, `vinted_radar/dashboard.py`, `scripts/verify_vps_serving.py`, `README.md`, `tests/test_repository.py`, `tests/test_dashboard.py`
  - Do: materialize the classified overview snapshot once per repository connection/`now` instead of recomputing the full CTE on every overview/explorer subquery, pass one generated timestamp through each assembled payload, repair common UTF-8 mojibake in visible HTML only, and document the `MSYS_NO_PATHCONV=1` mounted-command workaround plus a realistic verifier timeout.
  - Verify: `python -m pytest -q` and route timing checks against `data/m001-closeout.db`.
  - Done when: overview/explorer/detail/runtime stay mounted and truthful on the realistic large DB, the mounted smoke verifier becomes stable again, and visible HTML no longer leaks the obvious category-path mojibake seen during first proof.
- [x] **T02: Re-prove the assembled product on a realistic mounted corpus across desktop and mobile** `est:2h`
  - Why: S07 is not a unit-test-only slice; it must re-exercise the assembled shell, explorer workflow, narrative detail, runtime truth, and degraded-mode messaging on a large corpus from the real mounted entrypoint.
  - Files: `.gsd/milestones/M002/slices/S07/S07-UAT.md`, `.gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md`, `.artifacts/browser/2026-03-23T16-41-39-152Z-session/`
  - Do: serve `data/m001-closeout.db` behind `/radar`, run the mounted smoke verifier, browser-check overview/explorer/detail/runtime on desktop, then switch to mobile viewport and re-check overview/runtime/detail readability and navigation on the same mounted shell.
  - Verify: `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428` plus browser assertions/screenshots.
  - Done when: mounted smoke passes and the browser proof confirms overview/explorer/detail/runtime all work together on desktop + mobile over the realistic corpus.
- [ ] **T03: Close S07 on the true public VPS base URL** `est:1h`
  - Why: the roadmap’s S07 contract still requires proof from the real public VPS entrypoint, not only from the mounted localhost simulation backed by a copied realistic DB.
  - Files: `.gsd/milestones/M002/slices/S07/S07-UAT.md`, `.gsd/milestones/M002/slices/S07/tasks/T03-SUMMARY.md`, `.gsd/milestones/M002/slices/S07/S07-SUMMARY.md`, `.gsd/milestones/M002/M002-ROADMAP.md`, `.gsd/PROJECT.md`
  - Do: rerun the mounted smoke and browser/UAT flow against the true public VPS base URL (or via read-only VPS access if that is the only available path), then update the roadmap/project/slice artifacts with the real remote result instead of a local proxy-only claim.
  - Verify: `python scripts/verify_vps_serving.py --base-url <public-vps-url> --listing-id <live-id>` plus browser/UAT on the same public base URL.
  - Done when: the public VPS proof is recorded in the slice artifacts and the roadmap can truthfully mark S07 complete.

## Files Likely Touched

- `vinted_radar/repository.py`
- `vinted_radar/dashboard.py`
- `scripts/verify_vps_serving.py`
- `README.md`
- `tests/test_repository.py`
- `tests/test_dashboard.py`
- `.gsd/milestones/M002/slices/S07/S07-UAT.md`
- `.gsd/milestones/M002/slices/S07/tasks/T01-PLAN.md`
- `.gsd/milestones/M002/slices/S07/tasks/T02-PLAN.md`
- `.gsd/milestones/M002/slices/S07/tasks/T03-PLAN.md`
