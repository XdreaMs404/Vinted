---
estimated_steps: 4
estimated_files: 5
skills_used:
  - agent-browser
  - review
---

# T03: Close S07 on the true public VPS base URL

**Slice:** S07 — Live VPS End-to-End Acceptance Closure
**Milestone:** M002

## Description

The mounted large-corpus proof is now ready, but the roadmap’s S07 contract still asks for the true public VPS entrypoint. This task is the final external closeout: rerun the smoke/UAT flow against the real public base URL (or via read-only VPS access if that is the only available path), then update roadmap/project/slice artifacts with the real remote result.

## Steps

1. Obtain the real public VPS base URL (or read-only VPS access that exposes it).
2. Pick a live listing id from the public instance and run `verify_vps_serving.py` against that public base URL.
3. Browser-check overview, explorer, detail, and runtime against the real public endpoint on desktop and mobile.
4. Update `S07-SUMMARY.md`, `M002-ROADMAP.md`, and `.gsd/PROJECT.md` with the true remote result.

## Must-Haves

- [ ] The final proof references the real public VPS base URL, not only localhost `/radar`.
- [ ] The roadmap/project state changes only after the real public proof exists.

## Verification

- `python scripts/verify_vps_serving.py --base-url <public-vps-url> --listing-id <live-id>`
- Browser/UAT against `<public-vps-url>/`, `/explorer`, `/listings/<live-id>`, and `/runtime`

## Inputs

- `.gsd/milestones/M002/slices/S07/S07-UAT.md` — mounted realistic proof flow to replay remotely.
- `.gsd/milestones/M002/slices/S07/tasks/T01-SUMMARY.md` — large-corpus serving hardening already landed.
- `.gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md` — mounted desktop/mobile proof already landed.
- `README.md` — mounted operator commands and smoke harness usage.
- `scripts/verify_vps_serving.py` — public VPS smoke harness.

## Expected Output

- `.gsd/milestones/M002/slices/S07/tasks/T03-SUMMARY.md` — final remote VPS proof or explicit blocker report.
- `.gsd/milestones/M002/slices/S07/S07-SUMMARY.md` — slice closeout once the real public proof exists.
- `.gsd/milestones/M002/M002-ROADMAP.md` — S07 checked only after true public proof.
- `.gsd/PROJECT.md` — living project state updated with the final S07 result.
- `.gsd/milestones/M002/slices/S07/S07-UAT.md` — augmented with the public VPS run details.
