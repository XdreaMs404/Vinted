---
estimated_steps: 4
estimated_files: 4
skills_used:
  - frontend-design
  - make-interfaces-feel-better
  - test
  - review
---

# T01: Add a narrative listing-detail contract on top of the proof payload

**Slice:** S05 — Listing Detail Narrative + Progressive Proof
**Milestone:** M002

## Description

Load `frontend-design`, `make-interfaces-feel-better`, `test`, and `review` before coding. The brownfield detail route already has the evidence; this task adds the missing product-language contract above it. The goal is to translate state, score, timing, seller, and engagement inputs into a French narrative layer that remains explicitly grounded in observed facts, inferred signals, and estimated publication timing.

## Steps

1. Audit the existing detail payload and identify which narrative claims can be grounded directly in current state/score/history fields without inventing new evidence.
2. Add helper builders that translate technical state/score explanations into plain-language summary, supporting bullets, provenance labels, and caution/risk notes.
3. Extend `build_listing_detail_payload()` so the JSON route exposes narrative-first sections alongside the underlying proof data instead of replacing it.
4. Expand dashboard tests to assert on the new narrative/provenance contract and guard against regressions in explorer-context preservation.

## Must-Haves

- [x] Narrative detail copy is generated from existing proof inputs rather than ad-hoc string duplication in HTML only.
- [x] Observed facts, inferred states, estimated publication timing, and radar timestamps remain clearly separated in the payload.
- [x] The existing proof sections stay available in JSON for drill-down and diagnostics.

## Verification

- `python -m pytest tests/test_dashboard.py -k detail`
- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`

## Inputs

- `vinted_radar/dashboard.py` — current detail payload and proof-first rendering seam.
- `vinted_radar/scoring.py` — current score explanation structure that needs product-language translation.
- `vinted_radar/state_machine.py` — current evidence-first state reasons that must remain the proof layer.
- `tests/test_dashboard.py` — existing detail payload/route assertions to expand.

## Expected Output

- `vinted_radar/dashboard.py` — narrative detail payload helpers and richer `/api/listings/<id>` contract.
- `tests/test_dashboard.py` — assertions for narrative sections, provenance boundaries, and preserved explorer context.
- `vinted_radar/scoring.py` — any small explanatory-contract adjustments needed to support narrative translation.
- `vinted_radar/state_machine.py` — only if a tiny proof-label seam is needed without changing state semantics.
