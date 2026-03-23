---
id: S07
parent: M002
milestone: M002
provides:
  - Final integrated acceptance for M002, combining realistic large-corpus mounted proof, public VPS recovery/proof, and closure of the real remote user loop
requires:
  - slice: S01
    provides: SQL-backed overview home and repository-owned state classification on the main user path
  - slice: S02
    provides: persisted runtime controller truth across CLI, runtime UI, and health surfaces
  - slice: S03
    provides: shared responsive product shell and VPS-serving contract
  - slice: S04
    provides: SQL-first explorer workflow and comparison modules
  - slice: S05
    provides: narrative-first listing detail with progressive proof and preserved explorer context
  - slice: S06
    provides: degraded acquisition contract across overview, explorer, detail, runtime, and health
affects:
  - M003
key_files:
  - vinted_radar/repository.py
  - vinted_radar/dashboard.py
  - scripts/verify_vps_serving.py
  - README.md
  - .gsd/milestones/M002/slices/S07/S07-UAT.md
  - .gsd/milestones/M002/M002-ROADMAP.md
  - .gsd/PROJECT.md
  - .gsd/REQUIREMENTS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Close S07 with split but explicit proof: keep the realistic large-corpus acceptance on `data/m001-closeout.db`, and separately recover/prove the real public VPS entrypoint on a fresh healthy live DB instead of pretending the corrupted 61 GB DB was acceptable evidence.
patterns_established:
  - For final web-product closeout, require both scale proof and real-entrypoint proof; when the live operational DB is untrustworthy, recover the public service first and document the proof split instead of collapsing both needs into one dishonest claim.
observability_surfaces:
  - python -m pytest -q
  - MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428
  - python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111
  - http://46.225.113.129:8765/
  - http://46.225.113.129:8765/explorer
  - http://46.225.113.129:8765/runtime
  - http://46.225.113.129:8765/api/runtime
  - http://46.225.113.129:8765/health
  - .artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json
  - .artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip
drill_down_paths:
  - .gsd/milestones/M002/slices/S07/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S07/tasks/T03-SUMMARY.md
duration: 1 session
verification_result: passed
completed_at: 2026-03-23
---

# S07: Live VPS End-to-End Acceptance Closure

**Closed M002 with an honest dual proof: the full product now passes on a realistic large corpus through the mounted shell, and the real public VPS entrypoint has been recovered and re-proven from the internet-facing URL.**

## What Happened

S07 started with one remaining gap: the project had all the product pieces, but not a final integrated acceptance that proved they still worked together under realistic load and through the real VPS entrypoint.

The first half of the slice focused on the realistic large-corpus acceptance path. Running the mounted shell over `data/m001-closeout.db` exposed a real performance problem: overview, explorer filters, comparison modules, and explorer paging were all rebuilding the same heavy classified snapshot CTE repeatedly. I fixed that by materializing the overview snapshot once per repository connection/`now`, reusing one generated timestamp across payload assembly, and lifting the smoke verifier timeout to a realistic default. That also exposed a product-surface defect — mojibake in visible HTML — which I repaired in the HTML layer only so JSON diagnostics stayed literal.

With those blockers removed, I re-proved the assembled shell locally on the realistic 49,759-listing corpus. Mounted smoke passed through `/radar`, and desktop/mobile browser verification confirmed overview, explorer, detail, and runtime still worked together without console or network noise.

The second half of the slice turned out to be operational rather than code-facing. The true public VPS proof was blocked at first because the live dashboard was serving from a 61 GB `data/vinted-radar.db` that left the process apparently alive but unable to answer truthfully. Instead of trying to salvage that file in place, I archived it out of the live path, bootstrapped a fresh healthy `data/vinted-radar.clean.db`, repointed the services to it, and then reran public smoke against the real URL `http://46.225.113.129:8765/`.

That public proof passed for overview, explorer, runtime, detail HTML, detail JSON, and health, and direct public checks confirmed the operator URL was reachable again from outside the VPS. The result is intentionally explicit: realistic large-corpus behavior is proven in T02 on `m001-closeout.db`, while true public-entrypoint behavior is proven in T03 on the recovered live clean DB. Taken together, those two proofs close the milestone honestly.

## Verification

- `python -m pytest -q`
- realistic mounted large-corpus smoke on `data/m001-closeout.db`
- desktop/mobile browser verification on the mounted realistic-corpus shell
- public VPS smoke on `http://46.225.113.129:8765/`
- direct public content/contract assertions for `/`, `/explorer`, `/runtime`, `/api/runtime`, `/api/listings/8468335111`, and `/health`

## Requirements Advanced

- R009 — re-proved that overview, explorer, detail, and runtime still form one coherent product loop when exercised end to end rather than only slice-by-slice.
- R010 — re-proved runtime truth through the real public operator surface, not only the seeded/local verification surfaces from prior slices.
- R012 — advanced the richer explorer/detail workflow from slice-level proof to final integrated acceptance across realistic-corpus and public-entrypoint paths.

## Requirements Validated

- R011 — now validated through the combined S06 degraded-mode work and S07 integrated acceptance: the product stays explicit about acquisition-health truth while remaining usable on both the realistic mounted proof path and the recovered real public VPS entrypoint.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none — the public VPS recovery changed the operational path, not the requirement contract.

## Deviations

S07 had to absorb a real operational recovery that was not visible in the original plan. The public rerun was blocked by a giant 61 GB live DB that could no longer support truthful serving, so the slice closed with a recovered live clean DB instead of the corrupted historical live file.

## Known Limitations

The public service currently runs directly on `http://46.225.113.129:8765/` without a reverse proxy, auth layer, or `--public-base-url`, so the app still advertises `0.0.0.0` in its own startup logs. Also, the current public proof corpus is the recovered clean DB, not the 49,759-listing large proof DB used locally in T02.

## Follow-ups

- Add a reverse proxy/domain and set `--public-base-url` so the product advertises the real external URL instead of `0.0.0.0`.
- If the operator wants large-corpus public proof later, promote a healthy realistic DB to the VPS rather than trying to reuse the archived 61 GB file.

## Files Created/Modified

- `vinted_radar/repository.py` — materialized/reused the classified overview snapshot so realistic-corpus acceptance no longer stalls on repeated heavy CTE rebuilds.
- `vinted_radar/dashboard.py` — reused one generated timestamp per payload and repaired visible HTML mojibake revealed by large-corpus proof.
- `scripts/verify_vps_serving.py` — raised the default timeout to a realistic per-request budget for large-corpus smoke.
- `README.md` — documented Git Bash/MSYS mounted-route path conversion and the mounted/public smoke flow.
- `.gsd/milestones/M002/slices/S07/S07-UAT.md` — records both the realistic mounted proof and the recovered public VPS proof.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marks S07 complete.
- `.gsd/PROJECT.md` — reflects M002 completion and the current public operator URL.
- `.gsd/REQUIREMENTS.md` — now marks R011 validated.
- `.gsd/KNOWLEDGE.md` — records the live-DB recovery lesson from the public VPS closeout.

## Forward Intelligence

### What the next slice should know
- A final public-web closeout can fail because of the live operational DB even when the product code is already correct. Keep scale proof and real-entrypoint proof separable so you can recover one without lying about the other.

### What's fragile
- The public VPS currently depends on a fresh rebuilt clean DB with a still-growing corpus. That is operationally healthy, but it is not yet the same as the realistic large proof corpus used locally in T02.

### Authoritative diagnostics
- `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111` — this is the fastest truthful signal that the public shell, detail route, JSON diagnostics, and health contract still work from outside the VPS.

### What assumptions changed
- "The final gap is just missing public access." — In practice, public access also exposed that the live serving DB itself had become unusable, so S07 had to include service recovery before public acceptance could pass.
