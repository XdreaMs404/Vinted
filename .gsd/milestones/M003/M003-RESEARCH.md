# M003 Research — Product-Level Intelligence + Grounded AI Layer

**Date:** 2026-03-31  
**Status:** Research complete  
**Scope:** roadmap-planning guidance for cautious product grouping, grounded AI insights, weekly synthesis, and an analytical copilote.

## Executive Summary

M003 should **not** start with chat UI or free-form AI text. The first proof should be a **cautious product-grouping substrate** that can show, for a small but meaningful set of cases, that multiple listings resolve into the same market object **without contaminating the market read through false merges**.

The codebase is already unusually well-prepared for grounded intelligence work in three ways:

1. **Evidence and provenance are first-class** across events, manifests, warehouse marts, detail payloads, and UI honesty notes.
2. **Repository-shaped parity contracts** already exist between SQLite/repository reads and ClickHouse-backed reads.
3. **AI-ready feature marts and evidence packs already exist** as a machine-facing seam, even though no app-level AI integration exists yet.

The main constraint is that the current system is still fundamentally **listing-level**. There is no product entity, no group membership table, no group confidence contract, no group-aware marts, and no AI provider integration. That means M003 is best sliced in this order:

1. **Product grouping contract + proof-first heuristics**
2. **Persisted group projection + warehouse/group query support**
3. **Grouped product views in dashboard/explorer/detail**
4. **Grounded inline insights + weekly synthesis**
5. **Analytical copilote with explicit answer contract**

This milestone should reuse the project’s strongest existing pattern: **show uncertainty instead of hiding it**.

## What Exists Today

### 1. Listing-level truth is already normalized and traceable

Relevant files:
- `vinted_radar/models.py`
- `vinted_radar/card_payload.py`
- `vinted_radar/domain/events.py`
- `vinted_radar/services/evidence_lookup.py`
- `vinted_radar/services/evidence_export.py`

Key findings:
- `ListingCard` is still the base acquisition contract: listing id, title, brand, size, condition, prices, image URL, seller fields, and raw card payload.
- `normalize_card_snapshot()` in `vinted_radar/card_payload.py` is the compatibility seam that reconstructs canonical card fields from both newer evidence envelopes and older flat payloads.
- Event/manifests/evidence lookup already support traceability from a product surface back to concrete source fragments.
- `vinted_radar/services/evidence_lookup.py` and feature-mart evidence packs already give the project a grounded drill-down path that M003 can reuse.

Implication for M003:
- The factual substrate is good enough to support grounded grouping/AI work.
- But the captured listing-card evidence is still relatively thin, so grouping quality must start conservative.

### 2. Current identity is listing-level, not product-level

Relevant files:
- `vinted_radar/repository.py`
- `vinted_radar/platform/postgres_repository.py`

Key findings:
- SQLite and Postgres both center their current truth around `listing_id`.
- Postgres mutable truth currently has listing-focused seams such as identity, presence summary, and current state projection.
- There is **no existing product entity or grouping seam** in the app/runtime data model.
- No `product_group`, `group_id`, canonical product entity table, or group-membership projector exists today.

Implication for M003:
- Product grouping is a real new subsystem, not just a UI enhancement.
- The cleanest persistence seam is likely **Postgres mutable truth**, not ad-hoc SQLite-only grouping.

### 3. The project already has a cautious comparison pattern worth reusing

Relevant file:
- `vinted_radar/scoring.py`

Key findings:
- The scoring layer already uses explicit support-threshold context tiers:
  - `catalog_brand_condition`
  - `catalog_condition`
  - `catalog_brand`
  - `catalog`
  - `root_condition`
  - `root`
- It refuses to overclaim when support is too thin and falls back gracefully.
- Requirement `R007` explicitly validates this support-threshold posture.

Implication for M003:
- This is the nearest existing pattern for grouping.
- M003 should reuse the same philosophy: **high-confidence group**, **probable group**, **insufficient support / do not merge**.
- False splits are acceptable; false merges are not.

### 4. The dashboard already knows how to separate fact, inference, and caveat

Relevant file:
- `vinted_radar/dashboard.py`

Key findings:
- Listing detail payloads already include deterministic `narrative` and `provenance` sections.
- `_build_detail_provenance()` explicitly separates:
  - state signal
  - publication timing
  - radar window
- `_build_honesty_notes()` already exposes thin signal, partial signal, inferred states, unknown states, degraded probes, and acquisition failures as user-facing warnings.
- The detail surface already handles degraded-probe fallback honestly (`historique radar après probe dégradée`).

Implication for M003:
- AI should be added as an **extension of this honesty model**, not a replacement for it.
- The dashboard already has the presentation pattern M003 needs: interpretation layered on top of proof, not mixed into proof.

### 5. ClickHouse already exposes AI-ready, evidence-linked marts

Relevant files:
- `vinted_radar/query/feature_marts.py`
- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/platform/clickhouse_schema/__init__.py`
- `infra/clickhouse/migrations/V002__serving_warehouse.sql`
- `tests/test_feature_marts.py`

Key findings:
- `ClickHouseProductQueryAdapter.feature_marts_export()` already returns:
  - `listing_day`
  - `segment_day`
  - `price_change`
  - `state_transition`
  - `evidence_packs`
- The ClickHouse schema explicitly describes daily listing aggregates as suitable for **AI-facing listing cadence features**.
- Current marts already carry trace surfaces: manifest ids, event ids, run ids, and inspect examples.
- Tests already lock the JSON export contract and evidence-pack traceability.

Implication for M003:
- The best near-term AI input seam already exists.
- M003 does **not** need a vector database or embeddings-first architecture to begin.
- Start with retrieval over feature marts + evidence packs + group facts.

### 6. Repository ↔ ClickHouse parity is an existing product law

Relevant files:
- `tests/test_clickhouse_parity.py`
- `vinted_radar/query/overview_clickhouse.py`
- `vinted_radar/dashboard.py`

Key findings:
- Dashboard, explorer, detail, and health payloads already have repository-vs-ClickHouse parity tests.
- The project already treats ClickHouse as a repository-shaped serving backend, not just a separate analytics sidecar.

Implication for M003:
- Any user-visible grouped-product read contract must respect this parity story.
- If grouped views are added, the planner should assume parity work from the beginning rather than as a cleanup task.

### 7. There is no app-level AI integration yet

Verification:
- `rg -n "openai|anthropic|gemini|llm|embedding|vector|copilot|copilote|ai_" vinted_radar tests README.md pyproject.toml -g '!gsd/**'`

Finding:
- No meaningful in-product AI integration was found in the app code.
- Current project dependencies in `pyproject.toml` are Python/serving/data-platform oriented (`beautifulsoup4`, `boto3`, `clickhouse-connect`, `curl_cffi`, `psycopg`, `pyarrow`, `typer`) with no LLM SDK yet.

Implication for M003:
- M003 must introduce a provider seam deliberately.
- This is good news: the project is not constrained by a bad early AI abstraction.

## What Should Be Proven First

### First proof target

**Prove that cautious product grouping can improve the market read without creating obvious false merges.**

That should happen before:
- inline AI insight generation
- weekly synthesis generation
- copilote/chat UX
- broader reasoning layers

### Why this should be first

If grouping is weak, then:
- weekly syntheses will summarize contaminated entities,
- inline insights will sound smarter than the substrate deserves,
- copilote answers will become unsupported very quickly.

### What a good first proof looks like

A slice should show all of the following on real project data:
- a deterministic or hybrid grouping pass that groups only strong cases,
- explicit non-merge outcomes for ambiguous cases,
- a confidence contract such as **high confidence / probable / uncertain-not-merged**,
- provenance showing *why* a group exists,
- at least one grouped product view that reveals a market pattern not obvious from isolated listing inspection,
- operator/debug surfaces for bad merges, conflicts, and low-support groups.

## Recommended Slice Boundaries

### Slice 1 — Product grouping contract and conservative matcher

Goal:
- Introduce the first product-level entity model and grouping evidence contract.

Likely work:
- define a `product_group` / `group_membership` contract,
- compute conservative grouping candidates from listing identity fields and history,
- preserve provenance and disagreements instead of over-normalizing them,
- expose confidence bands and explicit non-merge outcomes.

Why first:
- This retires the highest-risk unknown in the milestone.

Proof to require:
- strong-case merges work,
- ambiguous cases stay split,
- provenance explains the merge basis.

### Slice 2 — Persisted projection + warehouse/group marts

Goal:
- Make grouping stable, queryable, and cheap enough to power the product.

Likely work:
- persist group entities or memberships in Postgres mutable truth,
- project group-level facts into ClickHouse,
- add group-aware marts/views rather than doing expensive ad-hoc grouping at request time.

Why second:
- It prevents M003 from becoming a slow SQLite-only experiment.
- It aligns with the repo’s post-M002 platform direction.

Proof to require:
- group data survives refresh/cutover,
- ClickHouse-backed grouped reads are truthful and traceable,
- tests cover parity and projection behavior.

### Slice 3 — Grouped product views in dashboard/explorer/detail

Goal:
- Let the user actually inspect products/articles instead of only listings.

Likely work:
- grouped product cards or drill-down views,
- grouped evidence/provenance panels,
- conflict and survivorship surfaces when listings disagree,
- links back down to member listings and raw evidence.

Why third:
- It turns the grouping substrate into real user value before AI text is added.

Proof to require:
- grouped view reveals at least one market winner/pattern not obvious from listing-only read,
- drill-down remains truthful and reversible back to listings.

### Slice 4 — Grounded inline insights + weekly synthesis

Goal:
- Add interpretation only after grouped evidence is stable.

Likely work:
- structured prompt input from marts + evidence packs + groups,
- JSON-shaped model output with explicit confidence and evidence references,
- dashboard inline insight blocks,
- weekly synthesis as the primary narrative artifact,
- short briefs only when meaningful change thresholds trigger.

Why fourth:
- This keeps AI downstream of stable grouped facts.

Proof to require:
- outputs add non-trivial value beyond restating tops,
- every claim links to evidence/time window/confidence,
- “insufficient support” is a valid output.

### Slice 5 — Analytical copilote

Goal:
- answer analytical questions grounded in radar data and grouped entities.

Likely work:
- retrieval/query layer over group facts, listing facts, transitions, and evidence packs,
- answer contract with separate sections for observation / inference / interpretation / hypothesis,
- follow-up drill-down links and explicit support windows.

Why fifth:
- The copilote depends on all earlier contracts.

Proof to require:
- concrete user questions return answers with cited support,
- unsupported questions degrade gracefully,
- the tool does not behave like an oracle.

## Boundary Contracts That Matter

### 1. `listing_state_inputs()` remains the normalized listing base row

Relevant files:
- `vinted_radar/repository.py`
- `vinted_radar/query/detail_clickhouse.py`
- `vinted_radar/platform/postgres_repository.py`

Why it matters:
- This is the current normalized row that already threads state, freshness, follow-up misses, probe outcomes, and basic identity.
- Grouping should build on top of this contract rather than bypassing it.

### 2. Postgres mutable truth is the natural persistence seam for group state

Relevant file:
- `vinted_radar/platform/postgres_repository.py`

Why it matters:
- M002 already moved mutable control-plane/current-state truth toward Postgres.
- Group membership is mutable projected truth; it fits this boundary better than isolated SQLite-only request-time logic.

### 3. ClickHouse marts/evidence packs are the natural AI retrieval seam

Relevant files:
- `vinted_radar/query/feature_marts.py`
- `vinted_radar/platform/clickhouse_schema/__init__.py`

Why it matters:
- They already capture time windows, changes, and traceability.
- M003 should extend them with group-aware facts rather than inventing a parallel retrieval stack first.

### 4. Dashboard provenance/honesty must be extended, not bypassed

Relevant file:
- `vinted_radar/dashboard.py`

Why it matters:
- The project already has a trustworthy UI language for uncertainty and degraded evidence.
- AI surfaces should plug into the same contract and vocabulary.

### 5. Repository/ClickHouse parity matters for grouped product reads too

Relevant file:
- `tests/test_clickhouse_parity.py`

Why it matters:
- Grouped routes and detail payloads should enter with parity expectations from day one.

## Constraints That Should Shape Slice Ordering

### False merges are the top milestone risk

Grouping errors are more damaging than missing some valid groups. This is already stated in milestone context and is consistent with the codebase’s cautious philosophy.

### Evidence is useful but not rich

Current hot-path listing-card evidence is enough for conservative grouping, but not enough to justify aggressive semantic clustering early.

### Request-time fuzzy grouping in SQLite is a trap

The product already works hard to push serving truth into repository/warehouse shapes. Expensive on-the-fly grouping would create latency and parity problems.

### Degraded acquisition must propagate into AI outputs

The existing runtime/acquisition honesty surfaces mean M003 cannot summarize the market as if degraded probes and partial signals do not exist.

### Weekly synthesis should be primary; shorter briefs should be eventful only

This is explicit in milestone scope and matches the product’s anti-noise posture.

## Failure Modes To Plan Around

1. **False merges across similar but distinct items**  
   The most dangerous failure mode; requires confidence bands and non-merge outcomes.

2. **Group survivorship conflicts hidden from the user**  
   If grouped members disagree on brand/size/condition/price timing, the UI must show that conflict rather than silently flatten it.

3. **AI paraphrasing existing tops instead of adding analysis**  
   Weekly synthesis must prove higher-order signal, not better wording.

4. **AI claims detached from evidence windows**  
   Every answer/synthesis should expose the time window and evidence scope used.

5. **Degraded runtime truth silently treated as clean truth**  
   Existing honesty note patterns should flow into insights and copilote answers.

6. **Parity drift between repository and ClickHouse grouped surfaces**  
   If grouped contracts are only implemented on one side first, product truth can split.

## Requirement Analysis

Relevant active requirements:
- `R013` — product/article grouping
- `R014` — grounded inline AI insights and periodic summaries
- `R015` — AI-assisted analytical exploration
- continuity requirements that M003 must preserve: `R007`, `R008`, `R009`, `R011`

### Table stakes for M003

These look mandatory, not optional:
- explicit group-confidence contract,
- explicit non-merge/uncertain outcome,
- evidence-backed grouped drill-down,
- time-windowed/cited AI outputs,
- graceful “insufficient support” answer behavior,
- honesty propagation from degraded/partial/thin signals into grouped and AI surfaces.

### Likely missing candidate requirements

These should be considered as **candidate requirements**, not silently auto-added:

1. **Candidate requirement — group provenance and conflict visibility**  
   The system should expose why listings were grouped and when member evidence conflicts instead of silently collapsing disagreements.

2. **Candidate requirement — unsupported AI refusal/abstention behavior**  
   The system should explicitly abstain or downscope when grouping confidence or evidence support is insufficient.

3. **Candidate requirement — AI output attribution contract**  
   The system should label answer sections as observed fact, calculated inference, AI interpretation, and broader hypothesis.

4. **Candidate requirement — synthesis versioning/traceability**  
   Weekly syntheses and briefs should retain generation metadata: source window, group/query scope, and evidence references.

5. **Candidate requirement — operator/debug audit for grouping quality**  
   Operators should be able to inspect merge reasons, low-confidence candidates, and obvious false-merge corrections.

### Things that are probably advisory only, not requirements yet

- embeddings/vector search as a mandatory architecture choice,
- web-enriched/general-internet reasoning,
- real-time streaming copilote responses,
- rich conversational memory beyond grounded retrieval context.

## Technology Choices That Matter

### 1. Keep the AI provider seam provider-agnostic at first

Reasoning:
- no AI SDK exists in the repo yet,
- the highest-risk work is data/grouping, not model API plumbing,
- the first useful contract is likely **structured JSON output**, not streaming chat.

Recommendation:
- introduce a narrow internal interface for structured insight/synthesis/copilote outputs,
- defer provider lock-in until after the answer contract exists.

### 2. Do not start with embeddings-first grouping

Reasoning:
- the project already has strong structured identity fields and time-window marts,
- false merges are the main risk,
- deterministic + probabilistic hybrid grouping is already aligned with milestone intent.

Recommendation:
- start with deterministic signatures plus cautious probabilistic support for ambiguous cases,
- only revisit embeddings if the simpler approach proves too weak.

### 3. Prefer persisted group facts over request-time recomputation

Reasoning:
- this codebase has already paid the cost to move serving/query truth into Postgres + ClickHouse,
- grouped reads will likely need the same treatment.

Recommendation:
- use Postgres for mutable group state/projection and ClickHouse for grouped analytical reads.

## Skill Discovery Suggestions

No directly relevant preinstalled professional skill list was exposed in the prompt context for this repo, so I ran quick external discovery for core M003 technologies.

Commands used:
- `npx --yes skills find "clickhouse"`
- `npx --yes skills find "postgresql"`
- `npx --yes skills find "openai"`

Promising results:
- **ClickHouse best practices**  
  `npx skills add clickhouse/agent-skills@clickhouse-best-practices`
- **ClickHouse IO skill**  
  `npx skills add affaan-m/everything-claude-code@clickhouse-io`
- **PostgreSQL table design**  
  `npx skills add wshobson/agents@postgresql-table-design`
- **PostgreSQL best practices**  
  `npx skills add mindrally/skills@postgresql-best-practices`

OpenAI search returned mostly generic OpenAI-owned skills unrelated to grounded analytics contracts, so there is no obvious must-install AI skill recommendation from that quick pass.

## Recommended Decisions For The Planner To Consider

These are advisory, not auto-binding:

1. **Decide early that false merges are a release-blocking quality issue for M003.**
2. **Decide that grouped entity state is projected truth, not raw truth.**
3. **Decide that all AI outputs must cite evidence/time windows and expose abstention.**
4. **Decide that weekly synthesis is primary and shorter briefs are event-triggered only.**
5. **Decide that M003 reuses the existing honesty/provenance language instead of inventing a parallel AI explanation style.**

## Minimal Verification Performed

- Targeted code inspection of:
  - `pyproject.toml`
  - `vinted_radar/scoring.py`
  - `vinted_radar/dashboard.py`
  - `vinted_radar/query/feature_marts.py`
  - `vinted_radar/query/overview_clickhouse.py`
  - `vinted_radar/platform/postgres_repository.py`
  - `vinted_radar/platform/clickhouse_schema/__init__.py`
  - `infra/clickhouse/migrations/V002__serving_warehouse.sql`
  - `tests/test_feature_marts.py`
  - `tests/test_clickhouse_parity.py`
  - `.gsd/REQUIREMENTS.md`
- Targeted codebase search confirming no app-level AI integration exists yet.
- Quick skill discovery for ClickHouse/PostgreSQL/OpenAI.
- No code changes were made.

## Planner Takeaway

If the roadmap planner does only one thing with this research, it should order M003 so that **grouping quality and grouped evidence contracts are proven before AI interpretation surfaces are allowed to become user-facing**. The codebase already has excellent provenance, warehouse, and parity foundations; M003 should capitalize on those strengths instead of jumping straight to copilote UX.
