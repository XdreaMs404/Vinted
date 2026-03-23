---
id: M002
provides:
  - A closed M002 milestone with SQL-backed overview/explorer user paths, persisted runtime-controller truth, a responsive French product shell, narrative listing detail, degraded-acquisition honesty, realistic-corpus acceptance, public VPS proof, and API-side price bounds for discovery.
key_decisions:
  - D019 — keep the existing Python + SQLite + server-rendered WSGI architecture and deepen repository-owned SQL payloads instead of rewriting the product stack.
  - D025 — represent current runtime truth in a separate persisted controller snapshot while keeping runtime cycles as immutable history.
  - Close final web-product acceptance with explicit split proof: realistic-corpus mounted proof plus real public-entrypoint proof, rather than pretending one environment proves both.
patterns_established:
  - Keep primary user paths SQL-first and repository-owned, then enrich only the active page/detail context instead of recomputing the full corpus at request time.
  - Keep acquisition-health truth repository-owned and surface the same contract across overview, explorer, detail, runtime, and health without page-local heuristics.
  - Push supported filters upstream to the Vinted API when possible, but retain local persistence guards so correctness does not depend on upstream behavior being perfect.
observability_surfaces:
  - python -m pytest -q
  - MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428
  - python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111
  - Browser assertions on the mounted local shell for overview, detail, and runtime on desktop plus overview and runtime on mobile
  - data/m001-closeout.db
requirement_outcomes:
  - id: R004
    from_status: active
    to_status: validated
    proof: M002/S01 moved the default home to a French SQL-backed overview that keeps coverage, freshness, confidence, and honesty visible; current mounted desktop/mobile verification still shows those signals on the real product path.
  - id: R011
    from_status: active
    to_status: validated
    proof: M002/S06 made degraded acquisition explicit across product/runtime surfaces, S07 proved it end to end on realistic-corpus and public-VPS paths, and the current local/public smoke rerun still passes.
duration: 8 slices / multiple sessions
verification_result: passed
completed_at: 2026-03-23
---

# M002: Enriched Market Intelligence Experience

**M002 is now properly closed: the milestone delivers a French-first market-intelligence product over the same evidence-backed SQLite boundary, and its integrated acceptance still passes today on both the realistic mounted corpus and the public VPS entrypoint.**

## What Happened

M002 changed the project from an evidence-heavy M001 dashboard into a usable product surface without dropping the credibility model that made the radar worth building.

S01 retired the most obvious scale risk by moving the home path onto repository-owned SQL aggregates, keeping the overview honest about coverage, freshness, confidence, and support without doing full-corpus Python recomputation on each request. S02 then made runtime truth representable instead of theatrical: current controller state, pause/resume timing, heartbeat, and recent-cycle context now live in persisted runtime state rather than being guessed from the latest finished cycle.

With those two foundations in place, S03 rebuilt the web shell around the real product shape: French-first, mounted-path-safe, and consultable on phone and desktop through the same overview, explorer, detail, and runtime routes. S04 turned `/explorer` into the main browse-and-compare workspace with SQL-backed filters, paging, comparison modules, and context-preserving drill-down. S05 then reworked listing detail so the first thing the user sees is the product reading, not the raw proof machinery, while still keeping the technical evidence inspectable underneath.

S06 closed the remaining honesty gap by surfacing degraded acquisition truth directly in the product and runtime surfaces. That mattered because a polished shell would have been misleading if state-refresh probes or scans were quietly going soft behind it. S07 then proved the assembled product honestly in two parts: mounted large-corpus acceptance over `data/m001-closeout.db`, and separate public-entrypoint proof after recovering the live VPS from an unusable giant database. Finally, S08 tightened discovery efficiency by pushing price bounds into Vinted’s API while preserving the local price safety net.

The milestone now has the cross-slice story it was missing at the top level: one product, one evidence model, one runtime truth contract, one explorer/detail loop, one degraded-acquisition honesty layer, and one explicit acceptance path that separates local scale proof from public-entrypoint proof instead of collapsing them into a false single claim.

## Cross-Slice Verification

- **Automated regression coverage:** `python -m pytest -q` passes in the current tree (`137 passed`).
- **Realistic local mounted acceptance:** `data/m001-closeout.db` is present and queryable with `49,759` listings; serving it behind `/radar` on `127.0.0.1:8790` succeeded, and `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428` passed for overview, explorer, runtime, detail HTML, detail JSON, and health.
- **Desktop browser verification on the mounted shell:** explicit browser assertions passed for overview, detail, and runtime with zero console errors and zero failed requests; explorer also rendered cleanly at the real filtered URL with the expected mounted route, product H1, filters, and no console/network failures.
- **Mobile browser verification on the mounted shell:** overview and runtime assertions passed at mobile viewport with zero console errors and zero failed requests, and the shell remained readable without the desktop-only route breakage M002 was meant to remove.
- **Public VPS acceptance:** `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111` passed for overview, explorer, runtime, detail HTML, detail JSON, and health on the real public operator URL.

## Requirement Changes

- R004: active → validated — S01 made the home path a French SQL-backed overview with visible coverage/freshness/confidence honesty, and the current mounted browser rerun confirms that product path still holds.
- R011: active → validated — S06 introduced degraded-acquisition honesty, S07 proved it on realistic and public paths, and the current local/public smoke rerun confirms the contract still works.

## Forward Intelligence

### What the next milestone should know
- The right M003 posture is to build on the repository-owned overview/explorer/detail seams from M002, not to reintroduce request-time full-corpus Python assembly in the name of richer analytics or AI.
- The project now has a truthful split between current scheduler truth, immutable cycle history, raw proof JSON, and product-layer French narration. Keep those seams intact.
- Final web closeout proof is stronger when scale proof and public-entrypoint proof stay explicit as separate acceptance layers.

### What's fragile
- The public VPS is healthy again, but it is still a direct-IP service without reverse proxy, auth, or a stable public base URL contract. That matters because M003 should not quietly depend on startup-log URLs or IP-only operator access.
- Acquisition truth remains inherently unstable under anti-bot pressure. The product is honest about it now, but it is not magically immune to upstream challenge drift.

### Authoritative diagnostics
- `python scripts/verify_vps_serving.py --base-url http://46.225.113.129:8765 --listing-id 8468335111` — fastest truthful signal that the public overview/explorer/detail/runtime/health contract still works from the real external URL.
- `MSYS_NO_PATHCONV=1 python scripts/verify_vps_serving.py --base-url http://127.0.0.1:8790/radar --listing-id 64882428` — fastest truthful signal for mounted-path regressions on the realistic large corpus.
- `python -m pytest -q` — broad regression signal for the repository/runtime/dashboard/discovery seams M002 depends on.

### What assumptions changed
- “A nicer shell is the main M002 problem.” — In practice, the hard parts were query ownership, runtime truth, degraded-acquisition honesty, and explicit acceptance on both the realistic corpus and the public entrypoint.
- “Public closeout is just one more smoke run.” — In practice, public proof also depended on recovering the live service from an operationally unusable database before the smoke could mean anything.

## Files Created/Modified

- `.gsd/milestones/M002/M002-SUMMARY.md` — milestone-level closeout summary and current verification record.
- `.gsd/PROJECT.md` — updated to point at the new milestone summary and keep the current-state description consistent with the closeout artifact.
