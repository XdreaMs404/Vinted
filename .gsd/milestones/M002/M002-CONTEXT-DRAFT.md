---
depends_on: [M001]
draft: true
---

# M002: Enriched Market Intelligence Experience — Context Draft

**Gathered:** 2026-03-18
**Status:** Draft — preserve this discussion before M002 planning

## Seed From Current Discussion

Recent user feedback reframed M002 from “make the existing dashboard richer” into a broader product rethink. The current M001 dashboard is considered too technical, too compact, hard to understand, limited to a tiny ranking slice, and not usable as a serious workspace for exploring a very large listing corpus.

The user wants a dashboard that is understandable to a broad audience, available in French, visually more polished, and substantially more capable. It must support market analysis across hundreds of thousands and eventually millions of listings without collapsing into a debug surface.

The current dashboard is still valuable as an evidence-first proof surface, but it is not the product shape the user wants to continue with.

## Direct User Feedback To Preserve

### Current dashboard pain points

- too complex, too dense, and not understandable to a general audience
- not available in French as a first-class product surface
- visually too compact and insufficiently polished
- explanations expose internal scoring jargon rather than plain-language meaning
- does not let the user navigate through all discovered listings; it effectively exposes only a small ranking slice
- missing useful direct listing fields such as likes/favourites, better photo access, clearer publication timing, and clearer sold status
- does not explain clearly why a listing was rated well in language a non-technical operator can understand
- does not make it easy to inspect already sold listings or compare what is moving by category, price, brand, or other criteria
- runtime / administration information is unclear; the user wants to understand pause state, elapsed pause time, and when the process resumes

### Example of what the user found opaque

The user explicitly rejected detail language such as:

- inference basis labels that read like internal implementation vocabulary
- score factor lists such as `state`, `confidence`, `basis`, `freshness`, `history_depth`, `follow_up_miss`
- premium context labels such as `catalog_condition`, `pairs`, and raw percentile values without plain-language translation
- transition / evidence text that reads like diagnostics rather than usable market interpretation

### Product expectations the user stated explicitly

The future product should:

- default to a true market-facing dashboard rather than a compact technical proof screen
- remain powerful while being understandable to a broad audience
- support navigation across the full listing corpus, not just the top 20–24 ranking rows
- provide intelligent sorting and filtering, including by price and other useful business criteria
- expose useful listing information directly from the main interface when available
- support analysis by category, price, brand, condition, sold state, and other meaningful dimensions
- preserve the ability to justify scoring and state decisions, but behind clearer language and progressive disclosure
- offer a more refined and carefully designed UI

## High-Level Product Shape Emerging From This Discussion

The working product shape discussed during this thread is:

1. **Market overview home** — the main entry point, focused on what is moving now, what is rising, and what is worth attention
2. **Full listing explorer** — a scalable exploration surface over the whole listing corpus with search, pagination, sorting, filtering, and sold-state access
3. **Listing detail** — a richer card / detail view that explains a listing in plain language and then allows expert drill-down into evidence and calculation details
4. **Runtime / administration** — a separate operator surface for scraping state, pause/running status, error history, next resume timing, and operational controls / visibility

The user chose **market overview** as the preferred default home surface.

## Data Expectations Raised In This Discussion

The user believes that the catalog surface may expose more fields than the current parser persists today, including some combination of:

- likes / favourite count
- primary image and possibly additional photo metadata / thumbnails
- seller / user object
- promoted status
- total item price and buyer-visible fee components
- status / visibility / sold / reserved state hints
- size title and other normalized card fields
- possibly tracking / conversion metadata (though this should not become part of the default durable model unless it serves a clear product purpose)

The user highlighted one especially important field: **publication time**. If publication time or a strong proxy can be derived from catalog-only evidence, future work should strongly prefer that over opening every listing detail page.

## Research Findings From This Discussion To Preserve

### Dashboard and scale

- The current dashboard is server-rendered out of one monolithic payload and still behaves like an M001 truth surface rather than a scalable product workspace.
- The current ranking limit is intentionally small and unsuitable for the user’s desired “explore everything” workflow.
- A future listing explorer must move to server-side filtering, sorting, and pagination / cursoring rather than loading everything into one dashboard response.
- At current scale, the closeout DB already holds tens of thousands of listings. The user expects hundreds of thousands soon and eventually millions.

### Current catalog data model limitations

- The current persisted catalog-card payload is intentionally small and only retains a narrow set of fields.
- Today’s model reliably stores title, brand, size, condition, price, total displayed price, one main image URL, canonical URL, and card-fragment evidence.
- Therefore, some desired fields may exist on the live catalog surface without being captured by the current parser or storage model.

### Catalog-first vs detail-first

- The preferred acquisition posture for future scale remains **catalog-first**.
- Opening every listing detail page is not compatible with the target volume and should not become the default plan.
- Detail pages should remain a targeted fallback or validation surface only if a high-value field cannot be obtained from catalog evidence or a legitimate broader data channel.

### Publication-time reality

- Exact publication time was not proven from the current catalog evidence.
- The primary image URL contains a timestamp-like component that appears useful as a **publication estimate** for fresh items, but not as an exact truth across the full historical corpus.
- Future product language should distinguish clearly between:
  - exact observed facts
  - inferred states
  - estimated publication timing
  - first seen / last seen by the radar

### Acquisition reliability risk

- Live access from this environment currently encounters Cloudflare / Turnstile challenges on both catalog and item pages, including under Playwright and Selenium-driven Chromium / Chrome.
- Recent real runs in `data/m001-closeout.db` showed that discovery quality can swing from nearly clean coverage to heavy 403 degradation within hours.
- Future planning must treat acquisition challenge rate as a first-class product and architecture risk, not a temporary nuisance.

## Working Assumptions For Future Planning

Unless later evidence invalidates them, future planning should assume:

- French-first user-facing copy
- broad-audience readability as a hard product constraint
- progressive disclosure: plain-language first, technical evidence second
- market overview as the default home
- full explorer as a separate first-class surface
- listing detail and runtime administration should not be crammed into one compact dashboard column
- catalog-first acquisition remains the preferred scaling posture
- exact publication date is not available unless proven later; estimation may still be valuable if labeled honestly
- the current server-only scraping approach is not a stable enough foundation to assume infinite scaling without additional acquisition strategy work

## Candidate Capabilities This Discussion Now Pulls Into M002

- a French, more accessible, more polished product surface
- market overview modules that answer “what is working now?” before exposing implementation vocabulary
- a scalable listing explorer across the whole corpus
- richer listing cards / detail panels with clearer explanations
- sold-listing and sold-state exploration workflows
- category / brand / condition / price-band analysis that remains backed by evidence
- more useful runtime administration and operator visibility
- better information architecture between user-facing analysis and operator diagnostics

## Constraints To Preserve

- M002 must not turn the product into a visually rich but analytically weak dashboard
- any new summaries or comparisons must remain backed by listing-level evidence when possible
- the product must keep showing coverage, confidence, freshness, and uncertainty in ways the user can actually understand
- richer utility is welcome, but not at the cost of the radar’s credibility
- the future acquisition plan must acknowledge anti-bot / challenge risk instead of assuming the current HTTP path scales cleanly

## Open Questions For Future Discussion

- Which of the desired rich fields can be recovered reliably from the catalog surface once we have a trustworthy live capture again?
- If catalog-only cannot expose enough fields, what is the minimal fallback detail strategy that does not destroy scalability?
- Should the future acquisition architecture move toward a browser-local collector, a legitimate partner / vendor data channel, or some other sanctioned source?
- What exact explorer interactions matter most first: pagination, cursoring, saved views, exports, comparisons, or all of them in sequence?
- How much of the admin/runtime surface belongs in M002 versus later operational hardening?
- Which market slices should become the first-class comparative dimensions: category, brand, price band, condition, sold state, or time window?

## Why This Draft Matters

This thread changed the practical interpretation of M002. It is no longer enough to think of M002 as “the current dashboard but richer”. The user wants a product surface that:

- reads clearly
- works at far larger scale
- separates market analysis from operator diagnostics
- preserves evidence without exposing raw internal scoring language as the main UX
- and does not depend blindly on a brittle acquisition assumption

Future planning should start from this draft rather than from the older, lighter M002 framing.
