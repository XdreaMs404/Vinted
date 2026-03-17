# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R001 — The system must discover and ingest public Vinted listings across the Homme and Femme categories and all reachable sub-categories without requiring login.
- Class: core-capability
- Status: active
- Description: The system must discover and ingest public Vinted listings across the Homme and Femme categories and all reachable sub-categories without requiring login.
- Why it matters: The radar is only useful if it sees the real market surface it claims to analyze.
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: M001/S02, M001/S06
- Validation: S01 proof: `python -m pytest`, `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --request-delay 0.0`, and `python -m vinted_radar.cli coverage --db data/vinted-radar.db` verified public seed sync and live listing ingestion without login.
- Notes: S01 shipped a live public collector that syncs the full Homme/Femme seed tree, scans selected leaf categories from public SSR HTML, persists normalized listing cards plus raw evidence fragments, and reports observed coverage. Broader repeat-run coverage still depends on S02/S06.

### R002 — The system must revisit listings over time, preserve historical observations, and expose first seen, last seen, and revisit cadence instead of overwriting state.
- Class: continuity
- Status: active
- Description: The system must revisit listings over time, preserve historical observations, and expose first seen, last seen, and revisit cadence instead of overwriting state.
- Why it matters: Without time-series history, the product cannot infer sell velocity, state transitions, or rising market behavior.
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: M001/S03, M001/S05, M001/S06
- Validation: S02 proof: `python -m pytest`, two consecutive `python -m vinted_radar.cli discover --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0` runs, plus `python -m vinted_radar.cli freshness --db data/vinted-radar-s02.db`, `python -m vinted_radar.cli revisit-plan --db data/vinted-radar-s02.db --limit 5`, and `python -m vinted_radar.cli history --db data/vinted-radar-s02.db --listing-id 4176710128` verified persisted repeated observations and revisit history surfaces.
- Notes: S02 now persists one normalized observation per listing per run in `listing_observations`, backfills legacy S01 discovery rows forward, and exposes first seen, last seen, observation count, average revisit gap, and timeline inspection through the CLI. Continuous revisit cadence still waits for S06.

### R003 — The system must classify listings with a cautious, traceable state machine that covers at least active, sold (observed or probable depending on signal quality), unavailable non-conclusive, deleted when the signal is distinct enough, and unknown.
- Class: core-capability
- Status: active
- Description: The system must classify listings with a cautious, traceable state machine that covers at least active, sold (observed or probable depending on signal quality), unavailable non-conclusive, deleted when the signal is distinct enough, and unknown.
- Why it matters: Overconfident status claims would make the radar analytically misleading.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S05, M001/S06
- Validation: S03 proof: `python -m pytest`, `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --limit 10 --request-delay 0.0`, `python -m vinted_radar.cli state-summary --db data/vinted-radar-s02.db`, and `python -m vinted_radar.cli state --db data/vinted-radar-s02.db --listing-id 4176710128` verified the cautious state taxonomy and explanation surfaces against live data plus fixture coverage for sold/deleted/unavailable paths.
- Notes: S03 shipped a cautious state engine over `listing_observations`, `catalog_scans`, and optional `item_page_probes`. Current state codes are `active`, `sold_observed`, `sold_probable`, `unavailable_non_conclusive`, `deleted`, and `unknown`, each with explicit basis kind, confidence, and reasons surfaced through the CLI.

### R004 — The product must visibly show what the radar has covered, over which time window, with what revisit freshness, and with what confidence.
- Class: failure-visibility
- Status: active
- Description: The product must visibly show what the radar has covered, over which time window, with what revisit freshness, and with what confidence.
- Why it matters: A market read is only trustworthy if the user can see its evidence base and blind spots.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S05, M001/S06
- Validation: Current proof is CLI-level only: `coverage`, `freshness`, `state-summary`, and per-listing `state` show what was covered, how fresh it is, and how confident the current state engine is.
- Notes: S02 and S03 now expose coverage, freshness, state confidence, and basis visibility through CLI surfaces (`coverage`, `freshness`, `state-summary`, `state`). These are durable inspection surfaces, but the requirement is not fully validated until they reach the main product experience in S05.

### R005 — The product must rank listings and market segments by real demand and sell-through signals rather than by simplistic popularity proxies such as likes or recency alone.
- Class: primary-user-loop
- Status: active
- Description: The product must rank listings and market segments by real demand and sell-through signals rather than by simplistic popularity proxies such as likes or recency alone.
- Why it matters: The user wants to know what really moves now, not what merely looks popular.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S05, M001/S06
- Validation: S04 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind demand --limit 10`, and `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693` verified the demand ranking surface and its explanation payloads.
- Notes: S04 now exposes a demand ranking surface grounded in state/history evidence, follow-up misses, confidence, and freshness rather than recency-only sorting. The score remains explainable through per-listing factor payloads.

### R006 — The product must provide a separate premium ranking that rewards items that perform well while remaining relatively expensive in their context.
- Class: differentiator
- Status: active
- Description: The product must provide a separate premium ranking that rewards items that perform well while remaining relatively expensive in their context.
- Why it matters: The user wants to distinguish cheap fast movers from items that sustain strong demand without collapsing in price.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S05, M001/S06
- Validation: S04 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind premium --limit 10`, and `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693` verified that premium ranking stays separate and shows its contextual price basis.
- Notes: S04 now exposes a separate premium ranking that starts from demand score and adds only a modest contextual price boost when the chosen peer sample is strong enough.

### R007 — The scoring model must contextualize comparisons inside the right market context when there is enough support, starting lightly in M001 and becoming much stronger in M002.
- Class: quality-attribute
- Status: active
- Description: The scoring model must contextualize comparisons inside the right market context when there is enough support, starting lightly in M001 and becoming much stronger in M002.
- Why it matters: Naive cross-context comparisons would distort both the demand and premium readings.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M002 (provisional)
- Validation: S04 proof: `python -m pytest tests/test_scoring.py` verified support-threshold-based context selection and graceful fallback when no trustworthy peer group exists.
- Notes: S04 applies lightweight contextualization opportunistically through explicit peer tiers (`catalog_brand_condition`, `catalog_condition`, `catalog_brand`, `catalog`, `root_condition`, `root`) with minimum support thresholds and a no-context fallback when support is too thin.

### R008 — The main product surface must summarize which sub-categories are performing, which are rising recently, and which segments appear to move quickly or hold price well.
- Class: primary-user-loop
- Status: active
- Description: The main product surface must summarize which sub-categories are performing, which are rising recently, and which segments appear to move quickly or hold price well.
- Why it matters: The user wants a market read first, not just raw listing tables.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S05, M001/S06
- Validation: Current S04 proof is CLI-level: `python -m vinted_radar.cli market-summary --db data/vinted-radar-s02.db --limit 8` produces performing and rising segment summaries tied to tracked listing counts and score aggregates.
- Notes: S04 adds a CLI-level market summary showing performing and rising segments with evidence counts, demand/premium aggregates, and recent-arrival / visible-delta signals. The requirement is still not fully validated until this reaches the main product surface in S05.

### R009 — The main screen must combine a market summary with concrete ranking tables, support useful filters, and allow drill-down into a listing detail view with history, signals, and inference basis.
- Class: primary-user-loop
- Status: active
- Description: The main screen must combine a market summary with concrete ranking tables, support useful filters, and allow drill-down into a listing detail view with history, signals, and inference basis.
- Why it matters: The product promise depends on linking macro market reading to micro evidence quickly.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: M001/S03, M001/S04, M001/S06
- Validation: mapped
- Notes: The dashboard should be visually rich and comfortable to use, but analytical clarity matters more than decorative complexity.

### R010 — The system must run locally in both a simple batch mode and a continuous mode that keeps the radar alive through repeated discovery and revisits.
- Class: operability
- Status: active
- Description: The system must run locally in both a simple batch mode and a continuous mode that keeps the radar alive through repeated discovery and revisits.
- Why it matters: Batch mode supports quick testing and controlled reruns; continuous mode is required for real temporal value.
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S01, M001/S02, M001/S03, M001/S04, M001/S05
- Validation: mapped
- Notes: A single user should be able to operate the local system without excessive setup complexity.

### R011 — The pipeline and product must continue to function when public signals are missing, partial, or inconsistent, while making those gaps explicit.
- Class: quality-attribute
- Status: active
- Description: The pipeline and product must continue to function when public signals are missing, partial, or inconsistent, while making those gaps explicit.
- Why it matters: Public web data is incomplete by nature; fragility would break trust and usefulness.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S01, M001/S02, M001/S04, M001/S05, M001/S06
- Validation: mapped
- Notes: Missing fields should degrade confidence and inference strength, not crash the pipeline.

### R012 — The product should add richer user-facing utility features such as comparisons, exports, and other helpful workflows that make the tool more complete beyond the core market read.
- Class: differentiator
- Status: active
- Description: The product should add richer user-facing utility features such as comparisons, exports, and other helpful workflows that make the tool more complete beyond the core market read.
- Why it matters: The long-term goal is not only analytical correctness but also a richer, more capable product.
- Source: user
- Primary owning slice: M002 (provisional)
- Supporting slices: none
- Validation: mapped
- Notes: These enrichments matter, but they should not displace M001’s credibility work.

### R013 — The system must move beyond individual listings and group related listings into product or article-level entities that better reflect what the market is buying.
- Class: core-capability
- Status: active
- Description: The system must move beyond individual listings and group related listings into product or article-level entities that better reflect what the market is buying.
- Why it matters: The long-term value of the radar improves when it can reason about products, not only isolated listings.
- Source: user
- Primary owning slice: M003 (provisional)
- Supporting slices: none
- Validation: mapped
- Notes: Grouping should combine deterministic and probabilistic evidence rather than rely on brittle rules alone.

### R014 — The product must use AI to generate grounded inline insights and periodic market summaries that are tied back to observed data, time windows, and confidence levels.
- Class: differentiator
- Status: active
- Description: The product must use AI to generate grounded inline insights and periodic market summaries that are tied back to observed data, time windows, and confidence levels.
- Why it matters: The user wants the radar to evolve into an intelligence layer, not remain a collection of static tops.
- Source: user
- Primary owning slice: M003 (provisional)
- Supporting slices: none
- Validation: mapped
- Notes: AI must not act like an oracle; it must stay grounded in collected evidence and be allowed to say when support is insufficient.

### R015 — The product should support an AI-assisted exploration mode that helps the user ask analytical questions of the collected market data.
- Class: differentiator
- Status: active
- Description: The product should support an AI-assisted exploration mode that helps the user ask analytical questions of the collected market data.
- Why it matters: This creates a more powerful intelligence workflow once the underlying data and evidence model are mature enough.
- Source: user
- Primary owning slice: M003 (provisional)
- Supporting slices: none
- Validation: mapped
- Notes: The copilote is in scope, but it must remain grounded and evidence-linked.

### R016 — The product must eventually support the operational hardening, product polish, and commercialization needs of a real SaaS offering.
- Class: launchability
- Status: active
- Description: The product must eventually support the operational hardening, product polish, and commercialization needs of a real SaaS offering.
- Why it matters: The project starts as a personal prototype, but it is intended to become commercial later.
- Source: user
- Primary owning slice: M004 (provisional)
- Supporting slices: none
- Validation: mapped
- Notes: Commercialization must preserve the radar’s credibility rather than turn it into a shallow dashboard.

## Deferred

### R020 — The product could notify the user when segments accelerate, weaken, or cross notable confidence thresholds.
- Class: admin/support
- Status: deferred
- Description: The product could notify the user when segments accelerate, weaken, or cross notable confidence thresholds.
- Why it matters: Alerts would make the radar more proactive once the core reading is trusted.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred until the core radar loop is credible enough that proactive notifications would be worth trusting.

### R021 — Multiple users could share analyses, saved views, and team workflows in the future.
- Class: admin/support
- Status: deferred
- Description: Multiple users could share analyses, saved views, and team workflows in the future.
- Why it matters: Collaboration may matter later if the product expands beyond a single operator.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Out of the immediate path because the product starts as a personal tool.

### R022 — The product could later add a mobile-first or native companion experience for monitoring market movement away from the desktop.
- Class: differentiator
- Status: deferred
- Description: The product could later add a mobile-first or native companion experience for monitoring market movement away from the desktop.
- Why it matters: Mobility may matter later for product breadth, but not for proving the radar’s value.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred behind the core local and web-based workflow.

## Out of Scope

### R030 — The project will not cover other Vinted verticals or unrelated marketplaces in the initial vision.
- Class: constraint
- Status: out-of-scope
- Description: The project will not cover other Vinted verticals or unrelated marketplaces in the initial vision.
- Why it matters: This preserves focus and prevents the market model from diluting early.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Scope can be reopened later only with an explicit new decision.

### R031 — The system must not rely centrally on undocumented private APIs as its primary long-term data acquisition strategy.
- Class: constraint
- Status: out-of-scope
- Description: The system must not rely centrally on undocumented private APIs as its primary long-term data acquisition strategy.
- Why it matters: A fragile backbone would undermine robustness, longevity, and maintainability.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Public collection may still observe public web behavior; the constraint is against making private undocumented APIs the main pillar.

### R032 — The product must not present inferred or weakly supported conclusions as certain facts.
- Class: anti-feature
- Status: out-of-scope
- Description: The product must not present inferred or weakly supported conclusions as certain facts.
- Why it matters: This would directly violate the credibility standard that defines the product.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: This is a product-level anti-feature, not just a scoring preference.

### R033 — The project will not automate purchases, listings, or transactional actions on Vinted.
- Class: anti-feature
- Status: out-of-scope
- Description: The project will not automate purchases, listings, or transactional actions on Vinted.
- Why it matters: The product is for market intelligence, not marketplace automation.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Keeps the product aligned with research and analysis rather than automation risk.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | active | M001/S01 | M001/S02, M001/S06 | S01 proof: `python -m pytest`, `python -m vinted_radar.cli discover --db data/vinted-radar.db --page-limit 1 --max-leaf-categories 6 --request-delay 0.0`, and `python -m vinted_radar.cli coverage --db data/vinted-radar.db` verified public seed sync and live listing ingestion without login. |
| R002 | continuity | active | M001/S02 | M001/S03, M001/S05, M001/S06 | S02 proof: `python -m pytest`, two consecutive `python -m vinted_radar.cli discover --db data/vinted-radar-s02.db --page-limit 1 --max-leaf-categories 4 --request-delay 0.0` runs, plus `python -m vinted_radar.cli freshness --db data/vinted-radar-s02.db`, `python -m vinted_radar.cli revisit-plan --db data/vinted-radar-s02.db --limit 5`, and `python -m vinted_radar.cli history --db data/vinted-radar-s02.db --listing-id 4176710128` verified persisted repeated observations and revisit history surfaces. |
| R003 | core-capability | active | M001/S03 | M001/S05, M001/S06 | S03 proof: `python -m pytest`, `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --limit 10 --request-delay 0.0`, `python -m vinted_radar.cli state-summary --db data/vinted-radar-s02.db`, and `python -m vinted_radar.cli state --db data/vinted-radar-s02.db --listing-id 4176710128` verified the cautious state taxonomy and explanation surfaces against live data plus fixture coverage for sold/deleted/unavailable paths. |
| R004 | failure-visibility | active | M001/S03 | M001/S05, M001/S06 | Current proof is CLI-level only: `coverage`, `freshness`, `state-summary`, and per-listing `state` show what was covered, how fresh it is, and how confident the current state engine is. |
| R005 | primary-user-loop | active | M001/S04 | M001/S05, M001/S06 | S04 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind demand --limit 10`, and `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693` verified the demand ranking surface and its explanation payloads. |
| R006 | differentiator | active | M001/S04 | M001/S05, M001/S06 | S04 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s02.db --kind premium --limit 10`, and `python -m vinted_radar.cli score --db data/vinted-radar-s02.db --listing-id 8305280693` verified that premium ranking stays separate and shows its contextual price basis. |
| R007 | quality-attribute | active | M001/S04 | M002 (provisional) | S04 proof: `python -m pytest tests/test_scoring.py` verified support-threshold-based context selection and graceful fallback when no trustworthy peer group exists. |
| R008 | primary-user-loop | active | M001/S04 | M001/S05, M001/S06 | Current S04 proof is CLI-level: `python -m vinted_radar.cli market-summary --db data/vinted-radar-s02.db --limit 8` produces performing and rising segment summaries tied to tracked listing counts and score aggregates. |
| R009 | primary-user-loop | active | M001/S05 | M001/S03, M001/S04, M001/S06 | mapped |
| R010 | operability | active | M001/S06 | M001/S01, M001/S02, M001/S03, M001/S04, M001/S05 | mapped |
| R011 | quality-attribute | active | M001/S03 | M001/S01, M001/S02, M001/S04, M001/S05, M001/S06 | mapped |
| R012 | differentiator | active | M002 (provisional) | none | mapped |
| R013 | core-capability | active | M003 (provisional) | none | mapped |
| R014 | differentiator | active | M003 (provisional) | none | mapped |
| R015 | differentiator | active | M003 (provisional) | none | mapped |
| R016 | launchability | active | M004 (provisional) | none | mapped |
| R020 | admin/support | deferred | none | none | unmapped |
| R021 | admin/support | deferred | none | none | unmapped |
| R022 | differentiator | deferred | none | none | unmapped |
| R030 | constraint | out-of-scope | none | none | n/a |
| R031 | constraint | out-of-scope | none | none | n/a |
| R032 | anti-feature | out-of-scope | none | none | n/a |
| R033 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 16
- Mapped to slices: 16
- Validated: 0
- Unmapped active requirements: 0
