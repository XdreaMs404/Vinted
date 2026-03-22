# M002: Enriched Market Intelligence Experience

**Gathered:** 2026-03-22
**Status:** Ready for planning

## Project Description

Turn the current M001 proof-oriented dashboard into a real market-intelligence product surface that is French-first on the main UI, much more understandable, visually more polished, and substantially more useful in daily practice.

M002 should deliver a market overview home, a full explorer over the tracked corpus, richer listing detail with plain-language explanation plus progressive disclosure into proof, and a separate runtime / administration surface that is much clearer without becoming a giant operator cockpit.

This milestone is still anchored in the evidence-first radar model, but it is no longer only a local debug-shaped surface. The user wants the tool to be genuinely usable from the VPS on both phone and PC, with a responsive remote web experience and much stronger day-to-day utility.

## Why This Milestone

The current M001 dashboard is still valuable as an evidence-first truth surface, but the user does not want to continue treating it as the real product shape. It is too dense, too technical, too compact, too hard to understand for a broad audience, and too limited for serious exploration of a very large listing corpus.

This milestone needs to happen now because the user wants the radar to become a real workspace: understandable, useful, consultable from phone and PC, and strong enough to judge whether the tool is truly valuable. The user explicitly wants M002 to go **à fond** on quality here: not a cosmetic pass, but the best useful version of the tool that this milestone can credibly support.

## User-Visible Outcome

### When this milestone is complete, the user can:

- open the radar from a phone or a PC against the VPS-served runtime, in a French-first product UI, and immediately understand what is moving now, what deserves attention, and what the radar is currently doing
- explore the full tracked corpus with scalable filters, sorting, paging, and comparative views across category, brand, price band, condition, and sold state, then open a listing detail that explains the reading in plain language before exposing deeper evidence

### Entry point / environment

- Entry point: responsive web dashboard served from the radar runtime, with market overview as the default home and explorer / listing detail / runtime views alongside existing CLI operator entrypoints
- Environment: browser / production-like VPS first, local dev second
- Live dependencies involved: Vinted web catalog API, public item pages for targeted state evidence, SQLite database, VPS runtime/process supervision, remote phone and desktop browsers

## Completion Class

- Contract complete means: the French-first market overview, full explorer, richer listing detail, clearer runtime surface, targeted data enrichments, and responsive remote access all exist with substantive implementation and verifiable behavior rather than placeholder UI.
- Integration complete means: collector, repository, scoring/state logic, runtime persistence, dashboard/explorer/detail surfaces, and VPS-served remote access work together on the same live evidence-backed database.
- Operational complete means: the radar can run on the VPS over time, remain consultable from phone and PC, show pause/running/error/resume timing clearly, and stay usable without depending on lucky one-off local dashboard access.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- on a live VPS-backed radar, the user can open the market overview from a phone, read a clear French-first summary of what is working now, and understand runtime state, pause state, elapsed pause time, and next resume timing without reading internal jargon
- on a desktop browser against the same live radar, the user can use the explorer over the real tracked corpus, filter and compare listings by category, brand, price band, condition, and sold state, then drill into a listing detail that explains the score/state in plain language with evidence available behind progressive disclosure
- this must be exercised against real remote VPS access, real live acquisition/runtime behavior, and a realistically large corpus; fixtures alone cannot prove remote accessibility, collector usefulness under anti-bot pressure, or broad-corpus usability

## Risks and Unknowns

- Cloudflare / Turnstile challenge rate can swing sharply — weak or degraded collection would distort the market read and make a polished UI misleading
- Remote dashboard access from the VPS is currently unreliable or slow from the user’s browsers — this directly blocks the intended phone + PC workflow
- The product could become visually richer but analytically weaker — the user explicitly does not want a polished but shallow dashboard
- Some desired fields remain only partially proven or estimated, especially publication timing and certain rich card fields — presenting them too strongly would damage trust
- Large-corpus scale into the hundreds of thousands and eventually millions of listings will punish monolithic payloads and broad in-memory recomputation — explorer and summary surfaces must respect the scale target
- The current acquisition backbone is acceptable for M002 only if it is materially hardened on performance, reliability, observability, and VPS usability — otherwise the experience layer will sit on fragile ground

## Existing Codebase / Prior Art

- `vinted_radar/dashboard.py` — current server-rendered dashboard plus the early SQL-backed explorer; it already proves some M002 directions, but the main surface still reads like an M001 truth screen more than a broad-audience product
- `vinted_radar/repository.py` — contains SQL-backed explorer filters, sorts, paging, history aggregation, and runtime-facing query patterns that M002 should deepen rather than replace casually
- `README.md` — documents the current local/VPS entrypoints, explorer URL, runtime JSON surfaces, and the still-local-feeling access model that M002 needs to evolve into a more reliable remote workflow
- `amélioration/review_approfondie_2026-03-22.md` — explicitly calls out richer data, acquisition/runtime improvements, and unresolved dashboard/scoring scalability debt that now matters directly for M002

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R007 — M002 is where contextual comparison becomes much stronger and more useful instead of staying light and provisional
- R011 — the enriched product must continue to function honestly when signals are partial, degraded, estimated, or inconsistent
- R012 — M002 is the primary milestone for richer user-facing utility features and more complete workflows
- R004 — coverage, freshness, confidence, and uncertainty still need to stay visible, but in language a broader audience can understand
- R009 — the existing mixed dashboard pattern evolves into clearer information architecture across overview, explorer, listing detail, and runtime surfaces
- R010 — the runtime remains part of the real product experience because the user must understand what the living radar is doing over time

## Scope

### In Scope

- French-first main product UI with market overview as the default home
- a much clearer, more polished product surface that remains evidence-backed and understandable to a broad audience
- a scalable full explorer over the tracked corpus with server-side filtering, sorting, and paging/cursor-like navigation patterns as needed
- first-class comparative market analysis across category, brand, price band, condition, sold state, and similarly meaningful business dimensions
- richer listing cards / listing detail that explain why a listing is interesting in plain language before exposing deeper evidence and calculation detail
- targeted data/model enrichments when they materially improve the experience, such as visible likes/views/seller context/publication estimate and other proven useful fields
- clearer runtime / administration visibility focused on status, pause state, elapsed pause time, next resume timing, and recent errors
- stronger VPS usability and responsive remote web access from phone and PC
- hardening the current collector spine for better performance, reliability, observability, and VPS operation without pretending acquisition risk has disappeared

### Out of Scope / Non-Goals

- a native mobile app
- a fully public SaaS product, account system, or commercialization stack
- promising a radical new acquisition channel as a required M002 deliverable
- replacing evidence-backed product behavior with decorative summaries or opaque AI-style wording
- treating internal scoring/debug vocabulary as the primary user-facing language
- turning runtime/admin into a huge operator cockpit if that would dilute the market-facing experience
- product-level grouping or grounded AI copilote work that belongs to M003

## Technical Constraints

- French-first applies to the main product UI; lower-level diagnostics may remain more technical if needed, but the primary user path must not read like an internal debugger.
- Market overview is the default home surface.
- The product must preserve progressive disclosure: plain-language first, technical evidence second.
- The system must preserve the explicit boundary between observed facts, inferred states, estimated publication timing, and radar first-seen/last-seen timestamps.
- Catalog-first remains the preferred scaling posture; item pages stay targeted evidence/fallback, not the default per-listing path.
- SQLite remains the durable runtime boundary for this milestone; M002 should deepen its server-side query/use patterns rather than assume a whole new platform.
- Remote access from phone and PC against the VPS-served radar is part of the acceptance bar, not a nice-to-have.
- The current acquisition spine should be hardened strongly in M002, but planning should avoid casually committing to a brand-new collection channel unless reality forces it.
- The product must not become visually rich but analytically weak.

## Integration Points

- Vinted `/api/v2/catalog/items` — primary discovery surface to harden for throughput, field capture, observability, and runtime usefulness
- public Vinted item pages — targeted state-evidence surface and limited fallback when catalog data is insufficient
- SQLite database / repository layer — durable boundary for listing corpus, history, runtime truth, and scalable explorer queries
- VPS runtime + dashboard serving path — the real operating environment for continuous collection and remote consultation from phone and PC
- responsive browser UI on mobile and desktop — the main user-facing consumption layer for M002

## Open Questions

- Does reality force a true hybrid/fallback acquisition strategy during M002, or can a strongly hardened current spine carry the milestone — current thinking: plan for strong hardening first, while keeping fallback strategy as a live risk if challenge rate stays unacceptable
- Which rich fields are stable enough to deserve default product placement versus secondary disclosure — current thinking: only elevate fields that are proven useful and reliable enough, and label estimates honestly
- How far should the phone experience go beyond responsive remote access — current thinking: responsive web access is required; a native mobile app is not
- How much admin control belongs in M002 beyond readability — current thinking: clear status/pause/resume/error visibility first, not a sprawling operations cockpit
- Which comparative modules should feel most first-class on the overview home versus the explorer — current thinking: category / brand / price band / condition / sold-state analysis are the first priority, while exports and saved views can wait unless planning proves they unlock more value than expected
