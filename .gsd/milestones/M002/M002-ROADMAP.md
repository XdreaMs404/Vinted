# M002: Enriched Market Intelligence Experience

**Vision:** Turn the M001 evidence-first dashboard into a French-first remote market-intelligence workspace that stays explainable, scales to a large tracked corpus, remains honest under degraded data, and is genuinely usable from the live VPS on phone and desktop.

## Success Criteria

- The default home on the live radar is a market overview that tells a broad audience, in French, what is moving now, what deserves attention, and how trustworthy the read currently is.
- The home, explorer, and detail surfaces stop depending on full-corpus request-time Python recomputation for their primary user paths and instead serve scalable SQL-backed payloads.
- A desktop user can explore the real tracked corpus with server-side filtering, sorting, and paging across category, brand, price band, condition, and sold state.
- A listing detail explains why the listing matters in plain language before exposing technical proof, while preserving the boundary between observed facts, inferred state, estimated publication timing, and radar first-seen/last-seen timestamps.
- The runtime/admin surface can truthfully show running, paused, scheduled, failed, elapsed pause time, next resume timing, and recent errors from persisted runtime state rather than inferred UI wording.
- The live VPS-served radar is consultable from both phone and desktop through a responsive web experience rather than an only-local workflow.
- When acquisition weakens or signals become partial, the product stays explicit about degraded coverage, freshness, confidence, and uncertainty instead of implying false precision.

## Key Risks / Unknowns

- The current home/dashboard path still materializes listing state inputs across the full corpus and scores in Python on each request, which will break the milestone's scale target if carried forward.
- The persisted runtime model does not yet represent paused state, pause start, elapsed pause, or next resume timing, so the milestone's runtime promises are currently unrepresentable.
- The app is reverse-proxy friendly but not yet productized for stable remote VPS access from phone and desktop.
- The product could become prettier but analytically weaker if comparative intelligence remains shallow or if evidence/provenance gets buried.
- Item-page refresh remains the weaker acquisition flank; if anti-bot pressure rises there, the product could silently drift unless degraded mode becomes visible.
- Explorer search and wide corpus filtering will become more expensive as the corpus grows if M002 keeps broad `%LIKE%` scanning and oversized page payloads without stronger query discipline.

## Proof Strategy

- Retire the full-corpus home-path risk in **S01** by shipping a real SQL-backed overview home that answers the user's first question through the actual product surface.
- Retire the runtime-truth gap in **S02** by making pause/resume/scheduling state first-class in persistence, API, CLI, and runtime UI.
- Retire the remote-access risk in **S03** by shipping the real VPS-serving path and responsive French shell through the production-style entrypoint the user will actually use.
- Retire the contextual-comparison and corpus-usability risk in **S04** by shipping the full explorer and comparative intelligence over the real database, not fixture-only cards.
- Retire the plain-language/progressive-disclosure gap in **S05** by shipping a real listing detail that leads with narrative utility and keeps proof accessible underneath.
- Retire the degraded-data honesty risk in **S06** by hardening the weak acquisition flank and surfacing degraded/partial conditions directly in the live product.
- Retire the assembled-system risk in **S07** by proving the fully integrated product on the live VPS from both phone and desktop against a realistically large corpus.

## Verification Classes

- **Contract verification:** repository aggregate/query tests, runtime schema/service transition tests, payload contract tests, serving/readiness checks, and provenance-label assertions.
- **Integration verification:** overview/explorer/detail/runtime routes exercised against a real SQLite database, live runtime cycles, reverse-proxy or production-style serving, and acquisition degradation paths.
- **Operational verification:** long-lived VPS runtime behavior, restart/recovery behavior, health/readiness visibility, pause/resume timing truth, and phone/desktop remote consultation.
- **UAT / human verification:** French clarity, information architecture, comparison usefulness, detail readability, mobile consultability, and perceived honesty when signals are partial.

## Milestone Definition of Done

This milestone is complete only when all are true:

- every slice below is complete with substantive implementation rather than placeholder UI or documentation-only claims
- overview, explorer, detail, runtime, collector hardening, and VPS serving all operate on the same live evidence-backed SQLite runtime boundary
- the primary user loop works through the real remote web entrypoint on the VPS, not only through local CLI or fixture-driven views
- the product remains explicit about coverage, freshness, confidence, estimates, and degraded conditions in broader-audience language
- the final integrated acceptance is re-proven from both phone and desktop against live remote runtime behavior and a realistically large corpus

## Requirement Coverage

### Coverage summary

- Mapped: **R004, R007, R009, R010, R011, R012**
- Deferred from the preloaded M002 table-stakes set: **none**
- Blocked from the preloaded M002 table-stakes set: **none**
- Orphan risk: **none visible from the preloaded milestone requirement readback**

### Requirement ownership map

| Requirement | Disposition | Primary owner | Supporting slices | Credible path in M002 |
|---|---|---|---|---|
| R004 | mapped | S01 | S02,S05,S06 | Overview, detail, and degraded-mode surfaces keep coverage/freshness/confidence visible in broader-language product copy. |
| R007 | mapped | S04 | S01,S05 | Comparative intelligence becomes first-class across category, brand, price band, condition, and sold state. |
| R009 | mapped | S03 | S01,S02,S04,S05 | The product shell clarifies overview vs explorer vs detail vs runtime instead of keeping one mixed dashboard posture. |
| R010 | mapped | S02 | S03,S06,S07 | Runtime truth becomes persisted product data, then gets surfaced remotely and exercised end to end on the live VPS. |
| R011 | mapped | S06 | S01,S02,S05,S07 | Partial, degraded, estimated, or inconsistent signals stay explicit in acquisition telemetry and user-facing product language. |
| R012 | mapped | S04 | S01,S05 | The explorer, comparisons, and richer detail deepen day-to-day utility beyond the current summary/ranking surface. |

## Slices

- [x] **S01: SQL-Backed Overview Home + First Comparative Modules** `risk:high` `depends:[]`
  > After this: `/` is a real market-overview home rather than an M001 truth screen, powered by SQL-backed aggregates and plain-language coverage/freshness/confidence cues instead of full-corpus Python recomputation.

- [ ] **S02: Runtime Truth + Pause/Resume Surface** `risk:high` `depends:[S01]`
  > After this: the product can truthfully show running, paused, scheduled, failed, elapsed pause time, next resume timing, and recent errors through the runtime page, API, and CLI on the same live DB.

- [ ] **S03: Responsive French Product Shell + VPS Serving Path** `risk:high` `depends:[S01,S02]`
  > After this: the live radar is served through a production-style VPS path and opens as a coherent French-first responsive product on phone and desktop, with clear navigation across overview, explorer, detail, and runtime.

- [ ] **S04: Full Explorer + Comparative Intelligence** `risk:high` `depends:[S01,S03]`
  > After this: a user can explore the real tracked corpus with server-side filters, sorts, paging, and comparison modules across category, brand, price band, condition, and sold state without leaving the live product.

- [ ] **S05: Listing Detail Narrative + Progressive Proof** `risk:medium` `depends:[S01,S03,S04]`
  > After this: opening a listing yields a French plain-language reading first, then richer seller, engagement, timing, state, and evidence detail behind progressive disclosure rather than leading with debugger vocabulary.

- [ ] **S06: Acquisition Hardening + Degraded-Mode Visibility** `risk:high` `depends:[S02,S03,S04,S05]`
  > After this: proxy-aware state refresh, degraded acquisition telemetry, and explicit partial-signal messaging keep the product honest when live collection weakens instead of hiding uncertainty behind polished screens.

- [ ] **S07: Live VPS End-to-End Acceptance Closure** `risk:medium` `depends:[S01,S02,S03,S04,S05,S06]`
  > After this: the assembled radar is proven through the real VPS entrypoint on phone and desktop with live overview, explorer, detail, runtime, and degraded-mode behavior all working together on a realistically large corpus.

## Boundary Map

### S01 → S02

Produces:
- SQL-backed overview aggregate/query contract for the default home
- stable segment lens vocabulary for category, brand, price band, condition, and sold state
- broader-audience coverage/freshness/confidence summary blocks that later runtime/detail surfaces can align with
- a scalable replacement for the current full-corpus home payload posture

Consumes:
- existing listings, observations, scores, and evidence-state repository data from M001
- current server-rendered route split (`/`, `/explorer`, `/api/...`) as the brownfield delivery seam

### S01 + S02 → S03

Produces:
- coherent French-first product-shell contract across overview, explorer, detail, and runtime
- responsive layout/navigation primitives for phone and desktop consultation
- production-style VPS serving contract, health/readiness expectations, and safe remote access posture
- shared runtime/overview navigation entrypoints for the real user workflow

Consumes:
- scalable overview payload contract from S01
- persisted runtime truth contract from S02

### S01 + S03 → S04

Produces:
- explorer query contract with stronger server-side filtering, sorting, and paging
- comparison modules backed by counts, support levels, and visible uncertainty
- first-class filters for category, brand, price band, condition, and sold state
- deep-linkable explorer states that the shell and overview can reference

Consumes:
- overview aggregate/lens vocabulary from S01
- responsive shell/navigation and VPS entrypoint from S03

### S01 + S03 + S04 → S05

Produces:
- listing-detail narrative contract with plain-language summary first and proof second
- provenance labels that preserve observed vs inferred vs estimated vs radar-timestamp boundaries
- drill-down links from overview/explorer comparisons into supporting listing detail
- richer listing cards/detail hierarchy that broadens daily product utility

Consumes:
- overview framing/language from S01
- navigation/layout conventions from S03
- explorer filters, comparison context, and drill-in flows from S04

### S02 + S03 + S04 + S05 → S06

Produces:
- proxy-aware item-page/state-refresh hardening and stronger acquisition observability
- degraded-mode telemetry contract for product and runtime surfaces
- user-visible warnings and partial-signal language across overview, explorer, detail, and runtime
- clearer distinction between healthy, degraded, paused, and failing live radar states

Consumes:
- runtime truth model from S02
- live shell/serving path from S03
- explorer/detail surfaces from S04 and S05 where degraded-mode signals must appear

### S01 + S02 + S03 + S04 + S05 + S06 → S07

Produces:
- assembled live VPS market-intelligence product usable from phone and desktop
- end-to-end proof that overview, explorer, detail, runtime, and degraded-mode honesty all work together against live data
- final operational closure for the milestone's real remote user loop

Consumes:
- all prior slice contracts and live runtime behavior across the same evidence-backed SQLite boundary
