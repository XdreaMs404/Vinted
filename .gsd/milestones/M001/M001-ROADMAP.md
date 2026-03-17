# M001: Listing-Level Market Radar

**Vision:** Build a local-first listing-level radar that tracks public Vinted Homme/Femme listings over time and turns imperfect public signals into an evidence-backed market read through cautious states, explicit confidence, and explainable “demande pure” and “premium” rankings.

## Success Criteria

- A local user can run the radar and see a mixed dashboard that combines market summary, listing rankings, coverage, freshness, and confidence surfaces.
- The system preserves historical observations for listings and exposes first seen, last seen, revisit cadence, and listing evolution over time.
- Listing states are cautious, traceable, and explicit about what was observed versus inferred.
- The “demande pure” and “premium” rankings are explainable and backed by visible listing evidence rather than simplistic likes or recency sorting.
- After several days of real local runtime, the product provides a market read that is already useful for judging which sub-categories and listings are moving now.

## Key Risks / Unknowns

- Broad public coverage may be incomplete or unstable under real collection conditions — if the radar cannot see enough of the market, every ranking becomes suspect.
- Public disappearance signals may be ambiguous — sold, unavailable, deleted, and unknown must not be collapsed too aggressively.
- Missing or inconsistent public signals may weaken inference quality — the product must degrade gracefully while preserving trust.
- The first scoring layer may look analytically rich without being defensible — scores must remain explainable and tied to evidence.
- The assembled system crosses multiple runtime boundaries — collection, storage, scheduler, scoring, and UI all have to work together in live local conditions.

## Proof Strategy

- Broad public coverage may be incomplete or unstable under real collection conditions → retire in S01 by proving that the radar can discover and normalize substantial Homme/Femme listing coverage with explicit visibility into what was seen.
- Public disappearance signals may be ambiguous → retire in S03 by proving that the state machine can represent ambiguity explicitly and justify each state classification.
- Missing or inconsistent public signals may weaken inference quality → retire in S03 by proving that missing data lowers confidence and leaves uncertainty visible without breaking the pipeline.
- The first scoring layer may look analytically rich without being defensible → retire in S04 by proving that market summaries and rankings can be explained through underlying observations and lightweight contextualization.
- The assembled system crosses multiple runtime boundaries → retire in S06 by proving that a single local user can run batch and continuous modes end to end over real public data and obtain a credible market read after multiple days.

## Verification Classes

- Contract verification: schema checks, artifact checks, field-presence validation, state-transition tests, ranking invariants, and CLI/dashboard smoke verifiers.
- Integration verification: live collection against public Vinted pages, persisted history updates, score recomputation, and dashboard rendering against real locally collected data.
- Operational verification: local batch mode and local continuous mode both start, persist, revisit, and recover cleanly enough for multi-day use.
- UAT / human verification: verify that the market summary feels credible, the dashboard is easy to read, and the explanatory surfaces support trust rather than confusion.

## Milestone Definition of Done

This milestone is complete only when all are true:

- all slice deliverables are complete with substantive implementation rather than placeholders
- discovery, history, cautious state logic, scoring, and UI surfaces are actually wired together
- the real local entrypoints for batch mode, continuous mode, and dashboard access exist and are exercised
- success criteria are re-checked against live behavior and persisted runtime evidence, not only artifacts or fixtures
- final integrated acceptance scenarios pass against real public Vinted observations gathered over time

## Requirement Coverage

- Covers: R001, R002, R003, R004, R005, R006, R008, R009, R010, R011
- Partially covers: R007
- Leaves for later: R012, R013, R014, R015, R016, R020, R021, R022
- Orphan risks: none

## Slices

- [x] **S01: Public Discovery + Normalized Ingestion** `risk:high` `depends:[]`
  > After this: a batch run discovers Homme/Femme listings from seeded public entry points, stores normalized listing records plus useful raw evidence, and shows the observed coverage footprint.

- [x] **S02: Intelligent Revisits + Observation History** `risk:high` `depends:[S01]`
  > After this: the radar revisits listings over time, preserves multiple timestamped observations per listing, and exposes first seen, last seen, revisit frequency, and freshness of follow-up.

- [x] **S03: Prudent State Machine + Confidence Surfaces** `risk:high` `depends:[S02]`
  > After this: each listing shows a cautious state (`active`, sold observed/probable, unavailable non-conclusive, deleted when distinct, `unknown`) with visible justification, observed/inferred separation, and confidence.

- [x] **S04: Market Scores + Lightweight Contextualization** `risk:medium` `depends:[S02,S03]`
  > After this: the product computes explainable “demande pure” and “premium” rankings plus a market summary of performing and rising segments, all backed by observed data and lightweight contextualization where it is robust.

- [ ] **S05: Mixed Dashboard + Filters + Listing Detail** `risk:medium` `depends:[S03,S04]`
  > After this: the local dashboard shows market summary first and listing proof immediately underneath, with useful filters and a detail view that reveals timeline, transitions, signals, and inference basis.

- [ ] **S06: Local Batch + Continuous End-to-End Loop** `risk:medium` `depends:[S01,S02,S03,S04,S05]`
  > After this: one local user can run a simple batch workflow or leave the radar running continuously, and after multiple days the assembled system yields a credible, explainable market read end to end.

## Boundary Map

### S01 → S02

Produces:
- Homme/Femme seed catalogue and sub-category entry-point registry
- canonical listing identity model with source URL, listing ID, category/sub-category, and raw/normalized field separation
- initial normalized listing records with `observed_at` timestamps and retained raw trace/debug evidence where useful
- coverage counters showing which category paths were actually scanned in the run

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- observation history model with `first_seen_at`, `last_seen_at`, `observation_count`, and revisit interval data
- revisit priority inputs that distinguish recently seen, high-signal, and stale listings
- per-listing timeline records that preserve missing fields rather than masking them
- freshness surfaces that quantify how recent follow-up observations are

Consumes:
- Homme/Femme seed catalogue and canonical listing identities from S01
- normalized discovery records and retained raw trace/debug evidence from S01

### S02 + S03 → S04

Produces:
- cautious listing lifecycle states with explanation payloads and confidence levels
- observed-versus-inferred attribution model that downstream score views can display
- demand signal bundle per listing that combines freshness, observed interest signals, state evidence, and time-based changes
- lightweight contextual baselines by sub-category and other supported dimensions when sample support is sufficient
- first score outputs for “demande pure” and “premium” plus market-summary aggregates

Consumes:
- listing observation history, revisit cadence, and freshness data from S02
- cautious state outputs, confidence, and ambiguity surfaces from S03

### S03 + S04 → S05

Produces:
- mixed dashboard contract with market summary modules, listing ranking tables, visible coverage/freshness/confidence surfaces, and filterable query state
- listing detail contract showing timeline, signals, status transitions, and inference basis
- drill-down links from market summaries to the supporting listing evidence

Consumes:
- state explanations, observed/inferred separation, and confidence payloads from S03
- score outputs, contextual baselines, and market-summary aggregates from S04

### S01 + S02 + S03 + S04 + S05 → S06

Produces:
- local batch workflow that collects, updates, recomputes, and serves the current radar state
- local continuous workflow that keeps discovery, revisits, state updates, and score recomputation running over time
- assembled end-to-end proof that the radar remains usable, understandable, and evidence-backed after multiple days of real local runtime

Consumes:
- ingestion and coverage footprint from S01
- revisit history and freshness data from S02
- cautious state and confidence surfaces from S03
- ranking and market-summary outputs from S04
- dashboard and drill-down contracts from S05
