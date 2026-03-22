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

### R011 — The pipeline and product must continue to function when public signals are missing, partial, or inconsistent, while making those gaps explicit.
- Class: quality-attribute
- Status: active
- Description: The pipeline and product must continue to function when public signals are missing, partial, or inconsistent, while making those gaps explicit.
- Why it matters: Public web data is incomplete by nature; fragility would break trust and usefulness.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S01, M001/S02, M001/S04, M001/S05, M001/S06
- Validation: mapped
- Notes: M002/S01 now keeps inferred states, unknown states, partial/thin signals, estimated-publication gaps, low-support comparison modules, and recent acquisition failures visible in `/` and `/api/dashboard` instead of smoothing them away. The requirement remains active because broader degraded-mode runtime truth and acquisition hardening still depend on later M002 slices.

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

## Validated

### R004 — The product must visibly show what the radar has covered, over which time window, with what revisit freshness, and with what confidence.
- Class: failure-visibility
- Status: validated
- Description: The product must visibly show what the radar has covered, over which time window, with what revisit freshness, and with what confidence.
- Why it matters: A market read is only trustworthy if the user can see its evidence base and blind spots.
- Source: user
- Primary owning slice: S01
- Supporting slices: S02,S05,S06
- Validation: S01 proof: `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`, `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765`, and live checks against `/`, `/api/dashboard`, `/api/runtime`, `/api/explorer`, `/api/listings/9101`, and `/health` confirmed visible coverage, freshness, confidence, comparison support thresholds, honesty notes, recent acquisition failures, and drill-down diagnostics on the SQL-backed French overview home.
- Notes: M002/S01 validated this requirement at the overview-home layer by surfacing tracked inventory, state mix, confidence counts, latest successful scan time, latest runtime-cycle status, recent acquisition failures, and thin-support honesty notes directly on `/` and `/api/dashboard`. Later slices can deepen detail/runtime wording without reopening the core visibility requirement.

### R005 — The product must rank listings and market segments by real demand and sell-through signals rather than by simplistic popularity proxies such as likes or recency alone.
- Class: primary-user-loop
- Status: validated
- Description: The product must rank listings and market segments by real demand and sell-through signals rather than by simplistic popularity proxies such as likes or recency alone.
- Why it matters: The user wants to know what really moves now, not what merely looks popular.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S05, M001/S06
- Validation: S04+S05 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s05.db --kind demand --limit 10`, and `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` plus browser verification confirmed a demand-led ranking table and listing-detail score explanations on the main product surface.
- Notes: Demand ranking remains grounded in state/history evidence, follow-up misses, confidence, and freshness rather than recency-only sorting, and the dashboard now renders that ranking without adding separate client-side scoring logic.

### R006 — The product must provide a separate premium ranking that rewards items that perform well while remaining relatively expensive in their context.
- Class: differentiator
- Status: validated
- Description: The product must provide a separate premium ranking that rewards items that perform well while remaining relatively expensive in their context.
- Why it matters: The user wants to distinguish cheap fast movers from items that sustain strong demand without collapsing in price.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S05, M001/S06
- Validation: S04+S05 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s05.db --kind premium --limit 10`, and `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` plus browser verification confirmed that premium remains a separate ranking surface with contextual-price explanations available in listing detail.
- Notes: Premium ranking still starts from demand and adds only a modest contextual price boost when the chosen peer sample is strong enough; S05 now exposes that distinction directly in the product surface.

### R008 — The main product surface must summarize which sub-categories are performing, which are rising recently, and which segments appear to move quickly or hold price well.
- Class: primary-user-loop
- Status: validated
- Description: The main product surface must summarize which sub-categories are performing, which are rising recently, and which segments appear to move quickly or hold price well.
- Why it matters: The user wants a market read first, not just raw listing tables.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S05, M001/S06
- Validation: S05 proof: `python -m pytest`, `python -m vinted_radar.cli market-summary --db data/vinted-radar-s05.db --limit 6 --format json`, and `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` plus browser verification confirmed performing/rising segment modules on the main product surface.
- Notes: S04 introduced the segment-summary payloads, and S05 now renders them as the first view in the local dashboard while keeping the underlying CLI output available for diagnostics.

### R009 — The main screen must combine a market summary with concrete ranking tables, support useful filters, and allow drill-down into a listing detail view with history, signals, and inference basis.
- Class: primary-user-loop
- Status: validated
- Description: The main screen must combine a market summary with concrete ranking tables, support useful filters, and allow drill-down into a listing detail view with history, signals, and inference basis.
- Why it matters: The product promise depends on linking macro market reading to micro evidence quickly.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: M001/S03, M001/S04, M001/S06
- Validation: S05 proof: `python -m pytest`, `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765`, and browser verification at `http://127.0.0.1:8765` confirmed a mixed dashboard with segment summaries, demand/premium ranking tables, root/state/catalog/search filters, and listing-detail drill-down into history, score factors, transitions, and state reasons.
- Notes: The delivered dashboard is server-rendered and backed by the same repository/state/scoring payloads exposed through `/api/dashboard` and `/api/listings/<id>` for truthful diagnostics.

### R010 — The system must run locally in both a simple batch mode and a continuous mode that keeps the radar alive through repeated discovery and revisits.
- Class: operability
- Status: validated
- Description: The system must run locally in both a simple batch mode and a continuous mode that keeps the radar alive through repeated discovery and revisits.
- Why it matters: Batch mode supports quick testing and controlled reruns; continuous mode is required for real temporal value.
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S01, M001/S02, M001/S03, M001/S04, M001/S05
- Validation: S06 proof: `python -m pytest`, `python -m vinted_radar.cli batch --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --request-delay 0.0`, `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s06.db --format json`, and `python -m vinted_radar.cli continuous --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8766` plus browser verification at `http://127.0.0.1:8766` and direct checks against `/api/runtime`, `/api/dashboard`, and `/health` confirmed both operator modes and persisted runtime diagnostics.
- Notes: Runtime truth now lives in SQLite `runtime_cycles`, with batch/continuous orchestration exposed through the CLI and mirrored on the dashboard runtime card plus `/api/runtime`.

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
| R004 | failure-visibility | validated | S01 | S02,S05,S06 | S01 proof: `python -m pytest tests/test_overview_repository.py tests/test_dashboard.py tests/test_dashboard_cli.py`, `python -m vinted_radar.cli dashboard --db data/vinted-radar-s01.db --host 127.0.0.1 --port 8765`, and live checks against `/`, `/api/dashboard`, `/api/runtime`, `/api/explorer`, `/api/listings/9101`, and `/health` confirmed visible coverage, freshness, confidence, comparison support thresholds, honesty notes, recent acquisition failures, and drill-down diagnostics on the SQL-backed French overview home. |
| R005 | primary-user-loop | validated | M001/S04 | M001/S05, M001/S06 | S04+S05 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s05.db --kind demand --limit 10`, and `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` plus browser verification confirmed a demand-led ranking table and listing-detail score explanations on the main product surface. |
| R006 | differentiator | validated | M001/S04 | M001/S05, M001/S06 | S04+S05 proof: `python -m pytest`, `python -m vinted_radar.cli rankings --db data/vinted-radar-s05.db --kind premium --limit 10`, and `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` plus browser verification confirmed that premium remains a separate ranking surface with contextual-price explanations available in listing detail. |
| R007 | quality-attribute | active | M001/S04 | M002 (provisional) | S04 proof: `python -m pytest tests/test_scoring.py` verified support-threshold-based context selection and graceful fallback when no trustworthy peer group exists. |
| R008 | primary-user-loop | validated | M001/S04 | M001/S05, M001/S06 | S05 proof: `python -m pytest`, `python -m vinted_radar.cli market-summary --db data/vinted-radar-s05.db --limit 6 --format json`, and `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765` plus browser verification confirmed performing/rising segment modules on the main product surface. |
| R009 | primary-user-loop | validated | M001/S05 | M001/S03, M001/S04, M001/S06 | S05 proof: `python -m pytest`, `python -m vinted_radar.cli dashboard --db data/vinted-radar-s05.db --host 127.0.0.1 --port 8765`, and browser verification at `http://127.0.0.1:8765` confirmed a mixed dashboard with segment summaries, demand/premium ranking tables, root/state/catalog/search filters, and listing-detail drill-down into history, score factors, transitions, and state reasons. |
| R010 | operability | validated | M001/S06 | M001/S01, M001/S02, M001/S03, M001/S04, M001/S05 | S06 proof: `python -m pytest`, `python -m vinted_radar.cli batch --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 4 --state-refresh-limit 6 --request-delay 0.0`, `python -m vinted_radar.cli runtime-status --db data/vinted-radar-s06.db --format json`, and `python -m vinted_radar.cli continuous --db data/vinted-radar-s06.db --page-limit 1 --max-leaf-categories 2 --state-refresh-limit 4 --interval-seconds 5 --request-delay 0.0 --dashboard --host 127.0.0.1 --port 8766` plus browser verification at `http://127.0.0.1:8766` and direct checks against `/api/runtime`, `/api/dashboard`, and `/health` confirmed both operator modes and persisted runtime diagnostics. |
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

- Active requirements: 10
- Mapped to slices: 10
- Validated: 6 (R004, R005, R006, R008, R009, R010)
- Unmapped active requirements: 0
