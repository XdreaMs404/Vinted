# S05: Listing Detail Narrative + Progressive Proof

**Goal:** Turn `/listings/<id>` into a French narrative-first reading surface that explains why a listing matters before exposing the state/score proof, while preserving explorer context, provenance boundaries, and truthful drill-down access.
**Demo:** Run `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8784`, open a listing from `/explorer`, and verify that the detail page leads with a plain-language reading, separates observed vs inferred vs estimated timing signals, and reveals deeper proof through progressive disclosure without losing `Retour aux résultats` behavior.

## Must-Haves

- Add a detail payload contract that produces plain-language narrative blocks from the existing state/score/history evidence without inventing unsupported claims.
- Rebuild the HTML detail page so the first screen answers "why this listing matters", then progressively reveals seller, engagement, timing, state, and scoring proof.
- Keep explorer-context preservation, JSON diagnostics, and evidence/provenance access intact while documenting and browser-verifying the richer detail flow.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
- `python -m vinted_radar.cli dashboard --db data/vinted-radar-s04.db --host 127.0.0.1 --port 8784`
- Browser verification at `http://127.0.0.1:8784/explorer?root=Femmes&state=active&price_band=40_plus_eur&sort=view_desc&page_size=12` confirms narrative-first listing detail, progressive proof sections, preserved explorer context, and clean console/network behavior.

## Observability / Diagnostics

- Runtime signals: listing-detail JSON now exposes narrative/provenance sections alongside the existing proof payload, and the HTML page keeps explicit state/confidence/provenance badges plus explorer-context diagnostics.
- Inspection surfaces: `/listings/<id>`, `/api/listings/<id>`, `tests/test_dashboard.py`, and the S05 UAT/browser proof flow.
- Failure visibility: if narrative translation or provenance separation drifts, route tests fail on missing sections/labels and the detail JSON/HTML surfaces show the mismatch directly.
- Redaction constraints: keep all detail copy limited to public listing metadata, inferred state/scoring evidence, and preserved route diagnostics; do not introduce secrets or hidden operator-only data into the detail payload.

## Integration Closure

- Upstream surfaces consumed: `vinted_radar/dashboard.py`, `vinted_radar/scoring.py`, `vinted_radar/state_machine.py`, S03 shared shell, and S04 explorer-context/query helpers.
- New wiring introduced in this slice: a narrative-first detail payload/readout, progressive-disclosure proof panels, and documentation/UAT for the richer explorer-to-detail workflow.
- What remains before the milestone is truly usable end-to-end: S06 still needs degraded acquisition truth on explorer/detail/runtime, and S07 still needs live VPS acceptance on the fully assembled product.

## Tasks

- [x] **T01: Add a narrative listing-detail contract on top of the proof payload** `est:1h30m`
  - Why: S05 only closes if the listing detail route can speak product language without forking away from the existing evidence model.
  - Files: `vinted_radar/dashboard.py`, `vinted_radar/scoring.py`, `vinted_radar/state_machine.py`, `tests/test_dashboard.py`
  - Do: derive French plain-language narrative blocks, provenance labels, confidence/risk cues, and score-context translation from the existing detail inputs; keep JSON detail truthful and explicit about observed vs inferred vs estimated timing.
  - Verify: `python -m pytest tests/test_dashboard.py -k detail`
  - Done when: `/api/listings/<id>` contains a usable narrative contract that a broader audience can read without losing access to the underlying proof.
- [x] **T02: Rebuild the HTML listing detail as a narrative-first page with progressive proof** `est:1h30m`
  - Why: the current detail page still leads with pills and debugger sections, so the route does not yet satisfy the milestone’s plain-language-first promise.
  - Files: `vinted_radar/dashboard.py`, `tests/test_dashboard.py`, `README.md`
  - Do: redesign the detail hero and section hierarchy around a clear market reading, then move proof into accessible progressive-disclosure sections (`details/summary` or equivalent) for state, timing, score, history, and transitions while keeping explorer return/context actions intact.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: the first visible part of `/listings/<id>` explains the listing in product language and the deeper proof remains reachable without overwhelming the main reading.
- [x] **T03: Document and prove the richer explorer-to-detail workflow** `est:1h`
  - Why: S05 is an integration slice, so it is not done until the richer detail flow is documented and browser-proven on the demo DB.
  - Files: `README.md`, `.gsd/milestones/M002/slices/S05/S05-UAT.md`, `tests/test_dashboard.py`, `tests/test_dashboard_cli.py`
  - Do: update route/docs where detail behavior changed, write the S05 UAT flow, and verify explorer → detail → back navigation plus progressive proof in a real browser session against `data/vinted-radar-s04.db`.
  - Verify: `python -m pytest tests/test_dashboard.py tests/test_dashboard_cli.py`
  - Done when: the richer detail flow is reproducible from docs/UAT and passes both route tests and browser proof on the demo DB.

## Files Likely Touched

- `vinted_radar/dashboard.py`
- `vinted_radar/scoring.py`
- `vinted_radar/state_machine.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_cli.py`
- `README.md`
- `.gsd/milestones/M002/slices/S05/S05-UAT.md`
