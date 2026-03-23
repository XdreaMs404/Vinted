---
estimated_steps: 6
estimated_files: 4
skills_used:
  - agent-browser
  - test
---

# T02: Re-prove the assembled product on a realistic mounted corpus across desktop and mobile

**Slice:** S07 — Live VPS End-to-End Acceptance Closure
**Milestone:** M002

## Description

Once the mounted large-corpus path is fast enough again, S07 must re-run the assembled product proof from the mounted `/radar` entrypoint on the realistic `m001-closeout.db` corpus. This task is the browser/UAT proof for overview, explorer, detail, runtime, degraded acquisition, and responsive shell behavior.

## Steps

1. Serve `data/m001-closeout.db` locally behind `/radar` with the mounted/public-base-url contract.
2. Pick a real listing id from the realistic DB and run the mounted smoke verifier against that listing.
3. Browser-check overview, explorer, detail, and runtime on desktop with explicit assertions and screenshots.
4. Switch to mobile viewport and re-check overview, runtime, and detail readability/navigation on the same mounted shell.
5. Persist browser artifacts (timeline / trace) under `.artifacts/browser/...`.
6. Write the repeatable UAT flow for this mounted realistic proof.

## Must-Haves

- [x] Mounted smoke passes on `data/m001-closeout.db` for overview, explorer, runtime, detail HTML, detail JSON, and health.
- [x] Desktop and mobile browser proof both pass with no app console or failed-network noise on the mounted shell.

## Verification

- `MSYS_NO_PATHCONV=1 python -m vinted_radar.cli dashboard --db data/m001-closeout.db --host 127.0.0.1 --port 8790 --base-path /radar --public-base-url http://127.0.0.1:8790/radar`
- `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428`
- Browser assertions against `http://127.0.0.1:8790/radar/`, `/radar/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12`, `/radar/listings/64882428?...`, and `/radar/runtime` on desktop + mobile.

## Observability Impact

- Signals added/changed: none in product runtime state; this task adds high-value acceptance artifacts instead.
- How a future agent inspects this: use `.artifacts/browser/2026-03-23T16-41-39-152Z-session/`, the mounted smoke command, and the screenshot/assertion flow in `S07-UAT.md`.
- Failure state exposed: route-level smoke failures, browser console/network errors, or broken responsive navigation on the mounted shell.

## Inputs

- `data/m001-closeout.db` — realistic large local proof corpus.
- `scripts/verify_vps_serving.py` — mounted smoke harness.
- `vinted_radar/dashboard.py` — served HTML/JSON shell under test.
- `README.md` — mounted operator flow and commands.

## Expected Output

- `.gsd/milestones/M002/slices/S07/S07-UAT.md` — repeatable mounted realistic UAT.
- `.gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md` — recorded browser/smoke proof.
- `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-browser-timeline-final.json` — final browser timeline.
- `.artifacts/browser/2026-03-23T16-41-39-152Z-session/s07-mounted-local.trace.zip` — browser trace artifact.
