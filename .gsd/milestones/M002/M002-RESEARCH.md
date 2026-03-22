# M002 — Research

**Date:** 2026-03-22

## Summary

M002 is not blocked by missing raw data fields; it is blocked by product-shape and scaling boundaries. The codebase already has three strong foundations: SQL-backed explorer paging/filtering in `repository.py`, enriched listing metadata in the `listings` schema/parser path, and persisted runtime truth in `runtime_cycles`. The biggest gap is that the home/dashboard path still behaves like an M001 truth screen: it loads all listing state inputs, scores everything in Python, filters in memory, and renders English technical copy. That is acceptable at ~500 tracked listings, but it is not the right shape for the milestone scale target.

Key surprise: the explorer is already architecturally closer to M002 than the dashboard home. `build_explorer_payload()` delegates filtering/sorting/paging to `RadarRepository.listing_explorer_page()` and only enriches the current page with observation/probe context. `build_dashboard_payload()` does the opposite: `load_listing_scores()` -> `repository.listing_state_inputs()` across the full corpus -> in-memory filtering -> Python scoring -> HTML rendering. M002 should reuse the explorer posture, not expand the current dashboard posture.

Second surprise: many “richer card” fields are already present end-to-end. `favourite_count`, `view_count`, `user_id`, `user_login`, `user_profile_url`, and `created_at_ts` already exist in the schema, parser, repository, tests, and payloads. So richer listing detail is now primarily a product/narrative/paging problem, not a raw-ingestion problem.

Third surprise: the runtime/admin acceptance bar in the milestone context cannot be met by polish alone. The persisted runtime model has `running/completed/failed/interrupted` plus phase, interval, counts, and last error, but no notion of paused state, pause start, elapsed pause, next resume, or operator control/event history. That is a data-contract gap, not a wording gap.

Finally, remote access is only partly productized. The app remains a server-rendered WSGI callable, which is good to keep, but the current serving path uses `wsgiref.simple_server`, and the install script binds the dashboard to `127.0.0.1` by default. That is a safe operational default, but it means M002 still needs an explicit VPS serving story for phone/desktop access.

## Current verification baseline

- `python -m pytest -q` currently passes with **100 passing tests**.
- Local browser verification confirmed that both `/` and `/explorer` render against a real SQLite DB.
- Mobile browser verification confirmed that the current layout is only partially responsive: the pages stack, but large tables remain desktop-shaped and are not yet a genuinely consultative phone experience.

## Recommendation

Keep the existing Python + SQLite + server-rendered WSGI architecture for M002. Do not spend the milestone on a framework rewrite. Instead:

- keep `RadarRepository` as the durable query boundary
- evolve the UI by replacing full-corpus dashboard payload assembly with SQL-backed overview/comparison queries
- split product work into explicit slices: query/payload scaling, runtime truth, remote serving, French-first IA, explorer/comparison UX, and listing-detail narrative
- treat acquisition hardening as a parallel support slice, especially for item-page probing, rather than the main product slice

The best M002 posture is: **SSR product shell + SQL-backed payloads + explicit evidence/provenance labels + production-style VPS serving**. That delivers the milestone’s intended usability without destabilizing the codebase.

## What should be proven first?

1. **Scalable product payloads before visual polish**
   - The current home path materializes full-corpus state inputs and scores on each request.
   - M002 should first prove that overview, explorer, and detail can be served against a realistically large DB without global Python recomputation.

2. **Runtime truth before runtime UI**
   - The milestone wants pause state, elapsed pause time, and next resume timing.
   - None of these are represented today in `runtime_cycles` or `RadarRuntimeService`, so the product cannot simply “surface” them yet.

3. **Reliable VPS remote access before phone-first claims**
   - Current code is reverse-proxy friendly at the route level, but not yet productized for real remote serving.
   - The serving/deployment boundary needs to be explicit before M002 promises phone + desktop utility.

If these three proofs fail, a polished M002 UI would still be analytically weak, operationally incomplete, or remote-unfriendly.

## Implementation Landscape

### `vinted_radar/dashboard.py`

Current UI delivery lives here end-to-end: route handling, payload assembly, and HTML rendering. This is the file that most strongly expresses the current M001/M002 boundary.

What already helps:
- separate routes already exist for `/`, `/explorer`, `/api/dashboard`, `/api/explorer`, `/api/runtime`, `/api/listings/<id>`, and `/health`
- overview and explorer are already separate surfaces, which is exactly the information-architecture direction M002 wants
- detail drill-down exists and already includes history, seller info, engagement signals, estimated publication, and score/state explanations

What constrains M002:
- the main UI is still English-first (`<html lang="en">`, English hero copy, English filters, English state/basis/confidence vocabulary)
- `build_dashboard_payload()` loads all listing scores, then filters in Python
- the listing detail panel leads with technical evidence and pills, not with a plain-language reading
- mobile responsiveness is mostly stacking, not true rethinking; ranking tables still use large minimum widths (`760px` dashboard, `1320px` explorer), so phone consultation remains weak
- the explorer page lacks the same embedded favicon handling as the dashboard and produces a small 404 asset warning in browser verification

Natural M002 takeaway:
- keep the route split
- refactor payload assembly and rendering responsibilities
- do not keep expanding this file as one giant string-builder without extracting clearer product sections

### `vinted_radar/repository.py`

This is the real reuse anchor for M002.

What already helps:
- `listing_explorer_page()` performs SQL-backed filtering, sorting, paging, then enriches only the current page with observation summary and latest probe context
- `explorer_filter_options()` already exposes roots, catalogs, brands, conditions, and sort options
- `listing_state_inputs()` and `listing_history()` preserve the evidence-first model and progressive drill-down
- `runtime_status()` and `coverage_summary()` already give server-readable operational truth

What constrains M002:
- overview/home still depends on full-corpus `listing_state_inputs()` + Python scoring
- explorer does not yet filter by sold state or price band, even though these are core M002 dimensions
- comparison queries are not yet first-class; current market summary groups only by primary catalog
- search currently relies on `%query%` `LIKE` filters over multiple text fields, which may become expensive on large corpora

Key surprise:
- the explorer path is already the pattern M002 should generalize across the product: **SQL first, targeted enrichment second**.

### `vinted_radar/scoring.py`

The scoring model is honest and already aligned with M001 decisions.

What already helps:
- demand and premium remain separate
- context selection already reasons over catalog / brand / condition / root support thresholds
- market summary already computes performing and rising segments

What constrains M002:
- score computation is still an on-demand Python pass over all evaluated listings
- market summary only groups by catalog, not brand / price band / condition / sold state lenses
- explanations are still technical; they are trustworthy, but not yet plain-language product copy

Natural M002 takeaway:
- preserve the scoring posture
- do not rewrite scoring semantics unless live evidence forces it
- add server-side aggregate/query paths around it, and add a separate narrative layer above it

### `vinted_radar/state_machine.py`

This remains a strong asset.

What already helps:
- state taxonomy is cautious and evidence-led
- confidence labeling and reasons are explicit
- direct probe evidence is correctly prioritized over weaker inference

What constrains M002:
- the emitted reasons are still technical and English-first
- there is no separate “plain French explanation” field distinct from the technical reasoning

M002 should reuse this as the proof layer, not the primary user-facing language layer.

### `vinted_radar/services/runtime.py`

This is where the biggest hidden product gap lives.

What already helps:
- runtime cycles are persisted in SQLite
- mode / phase / last error / tracked counts / freshness snapshot are durable
- batch and continuous modes already share one truth model

What constrains M002:
- no paused state
- no pause_started_at
- no elapsed pause duration
- no next_resume_at
- no operator action log or scheduler truth beyond a simple sleep-based loop

This means the milestone’s runtime acceptance bar is currently impossible without schema and service changes.

### `vinted_radar/services/state_refresh.py`

This is a meaningful support-slice target for M002 hardening.

What already helps:
- item-page probes are targeted, not default
- probe selection already prioritizes stale or ambiguous cases
- probe results feed the cautious state machine correctly

What constrains M002:
- item-page probing is sequential and synchronous
- unlike discovery, it does not accept a proxy pool
- if anti-bot pressure increases on item pages, this path becomes the weaker half of the acquisition spine

Key surprise:
- the proxy/runtime review fix only fully covered discovery; item-page refresh is still the asymmetric weak spot.

### `vinted_radar/services/discovery.py` + `vinted_radar/http.py`

This is the strongest part of the current hardening story.

What already helps:
- catalog discovery already uses async requests
- `VintedHttpClient` supports warm-up, retry, proxy rotation, and async fetches
- discovery already supports min-price, target catalogs, target brands, and concurrency
- rich card fields are already parsed and persisted

What constrains M002:
- current defaults are conservative (`concurrency=1` from CLI/runtime), which is safer but means the real throughput posture still needs live tuning on the VPS
- the current architecture is intentionally tied to the private Vinted catalog API, so anti-bot and contract drift remain live risks
- fallback strategy remains advisory, not implemented

M002 should harden this path, but should not casually commit to a new acquisition channel unless live failure rates force it.

### `vinted_radar/db.py`

The SQLite posture is broadly right for M002.

What already helps:
- WAL mode is already enabled
- enriched fields are already in schema
- runtime, history, discovery, and probes already share one durable boundary
- the schema already supports many of the enriched UI needs

What constrains M002:
- compatibility/migration handling remains intentionally light after past DB issues
- runtime schema is not yet rich enough for pause/resume semantics

The right M002 move is to deepen SQL query patterns and runtime truth, not replace SQLite.

### `install_services.sh`

This file is useful for understanding what “deployment” means today.

What already helps:
- separate scraper and dashboard services
- safer default binding to localhost
- continuous mode rather than restart-loop batch mode
- systemd service hardening basics (`NoNewPrivileges`, `PrivateTmp`)

What constrains M002:
- remote phone/desktop access is still outside the app itself; the script explicitly expects SSH tunneling or a reverse proxy when bound to localhost
- there is no integrated production WSGI/reverse-proxy story in repo
- there is no auth or route-base configuration for public exposure

## Boundary Contracts That Matter

### 1. Repository contract
M002 should continue to treat `RadarRepository` as the durable business boundary. New UI surfaces should consume explicit repository/query results, not ad-hoc SQL from rendering code.

Recommended contract direction:
- overview aggregates by dimension and time window
- explorer pages with additional filters (sold state, price band)
- comparison modules returning top groups plus supporting counts/confidence
- listing detail narrative + proof inputs

### 2. Evidence contract
M002 must preserve the boundary between:
- observed facts
- inferred state
- estimated publication timing
- radar first-seen / last-seen timestamps

Today the data model already supports this; the gap is mainly the user-facing language layer.

### 3. Runtime truth contract
If pause/resume matters, the persisted runtime contract must grow to include:
- status enum that can distinguish `running`, `paused`, `scheduled`, `failed`, `interrupted`
- pause_started_at
- paused_elapsed_seconds
- next_resume_at
- current interval / scheduler basis
- recent operator/runtime events

Without this, the runtime surface will remain explanatory theater.

### 4. Remote serving contract
The app routes are stable enough for reverse proxying at the domain root, but M002 should define:
- how the app is served on VPS
- what process/server runs the WSGI callable
- whether dashboard/admin share one origin
- health/readiness expectations for long-lived remote access

### 5. Acquisition contract
The current split remains sound:
- catalog API = primary discovery throughput path
- item pages = targeted evidence path
- SQLite = durable product truth

M002 should keep this split, while hardening observability and proxy use rather than blurring the boundaries.

## Natural Slice Boundaries and Suggested Order

### Slice 1 — Query and payload scaling backbone
Goal: remove full-corpus request paths from the main product surfaces.

Build:
- SQL-backed overview aggregates
- explorer filter expansion (sold state, price band)
- comparison queries by category / brand / condition / sold state / price band
- targeted detail fetches rather than global recomputation

Why first:
- this is the main scalability blocker
- it directly supports R007, R004, R009, and R012

### Slice 2 — Runtime truth and operability model
Goal: make runtime/admin acceptance actually representable.

Build:
- richer runtime status model
- pause/resume timing persistence
- next-resume calculation
- clearer runtime JSON contract

Why second:
- current schema cannot express the milestone’s runtime claims
- it directly supports R010 and R004

### Slice 3 — VPS remote-serving path
Goal: make phone/desktop access against the live VPS trustworthy.

Build:
- production-serving plan around the existing WSGI app
- reverse-proxy/systemd documentation or implementation path
- stable remote health/readiness checks

Why third:
- the user’s main consumption mode is remote VPS access
- this must be proven before heavy UI iteration

### Slice 4 — French-first product shell and information architecture
Goal: turn the current truth screen into a product surface.

Build:
- overview as default home
- French-first copy and labels
- navigation between overview / explorer / listing detail / runtime
- responsive shell and layout system

Why after 1–3:
- this slice can then sit on stable payloads and runtime truth instead of papering over gaps

### Slice 5 — Explorer and comparative intelligence UX
Goal: make the corpus genuinely explorable and comparable.

Build:
- first-class filters and sorts across category, brand, price band, condition, sold state
- comparative modules and summary blocks that stay backed by counts/confidence
- mobile-friendly explorer interaction patterns

Why here:
- it depends on the query backbone and product shell, but is the core day-to-day utility slice

### Slice 6 — Listing detail narrative + progressive disclosure
Goal: plain-language first, proof second.

Build:
- French summary of why the listing matters
- explicit provenance labels
- collapsible or secondary technical proof sections
- richer history / state / score explanation flow

Why here:
- the data already exists, but the product language and hierarchy need to be redesigned carefully

### Slice 7 — Acquisition spine hardening (parallel support slice)
Goal: keep the product honest under live anti-bot pressure.

Build:
- proxy support for state refresh
- better observability for degraded acquisition
- measured concurrency tuning
- explicit degraded-mode surfacing in product/runtime

Why parallel:
- this supports R011 and the milestone’s honesty standard, but does not need to block all UI work

## Requirements Readback

### Table stakes from active requirements and milestone context
These already look binding for M002:
- **R007**: contextual comparison must become materially stronger
- **R011**: degraded or partial signals must remain explicit
- **R012**: user-facing utility must deepen beyond the current summary/ranking surface
- **R004**: coverage/freshness/confidence must stay visible, but in broader-audience language
- **R009**: clearer information architecture across overview / explorer / detail
- **R010**: runtime remains part of the real product experience

### Candidate requirements that should likely be added
These feel missing as explicit requirements, even though the milestone context makes them important:

1. **Responsive VPS remote access requirement**
   - The main product UI must remain usable from phone and desktop browsers against the live VPS-served runtime.

2. **French-first progressive disclosure requirement**
   - The default product path must present plain French explanations first and technical evidence second.

3. **Runtime pause/resume truth requirement**
   - The product must persist and surface pause state, elapsed pause time, and next resume timing as runtime truth, not inferred UI copy.

4. **Scalable server-side payload requirement**
   - Overview and explorer surfaces must avoid full-corpus in-memory recomputation on each request and remain server-side paged/aggregated.

These should be treated as candidate requirements, not silently assumed.

### Behaviors that are probably optional for M002
These remain useful but should not displace core work:
- exports
- saved views
- richer operator controls beyond status clarity
- automatic hybrid acquisition fallback unless live failure rates force it

### Overbuilt risks
The codebase is especially at risk of these wrong turns:
- rewriting to a client-heavy SPA/React stack instead of reusing the current SSR pattern
- building a giant operator cockpit instead of a clear runtime/status surface
- adding decorative AI-style summaries before plain-language evidence-backed explanations exist
- promising new acquisition channels instead of hardening the existing split
- expanding R012 into export/share/workflow breadth before the core overview/explorer/detail loop is genuinely strong

## Constraints and Known Failure Modes

- `build_dashboard_payload()` currently recomputes full-corpus listing scores per request; this is the largest direct scale risk.
- Explorer search currently uses broad `LIKE '%query%'` matching. That is fine now, but if free-text search becomes a primary workflow at much larger scale, SQLite FTS may be needed. Even then, SQLite’s FTS5 trigram path has caveats: patterns without a 3-character non-wildcard run fall back to linear scan, so FTS should be added only when profiling proves it is worth the complexity.
- The app is currently served via `wsgiref.simple_server`, which is a reference/simple WSGI server, not a production serving story by itself.
- SQLite WAL mode is already enabled, which is good for same-machine reader/writer concurrency, but it reinforces the current architectural assumption that the live DB remains local to the VPS/process host, not on a network filesystem.
- The current phone layout is only partially responsive. Ranking and explorer tables still rely on wide desktop tables, so the mobile experience is not yet a real consultative product surface.
- Acquisition hardening is asymmetric: discovery has async transport + proxy rotation; item-page state refresh does not.

## Reuse, Don’t Replace

| Need | Existing pattern to reuse | Why |
|---|---|---|
| SQL-backed browsing | `RadarRepository.listing_explorer_page()` | Already proves server-side filtering, sorting, paging, and page-local enrichment. |
| Enriched listing fields | `listings` schema + `parse_api_catalog_page()` + tests | Likes/views/seller/publication estimate are already captured and validated. |
| Honest state reasoning | `state_machine.py` | Already preserves observed vs inferred vs unknown boundaries. |
| Runtime persistence | `runtime_cycles` + `runtime_status()` | Best starting point for clearer runtime/admin truth. |
| HTTP hardening | `VintedHttpClient` | Warm-up, retry, async, and proxy rotation already exist for discovery. |
| SSR delivery | `DashboardApplication` routes + JSON endpoints | Keeps M002 dependency-light and truthful without a frontend rewrite. |

## Skills Discovered

These were the only non-installed skills that looked directly relevant to M002’s core technologies:

| Technology | Skill | Why it may help | Install |
|---|---|---|---|
| SQLite | `martinholovsky/claude-skills-generator@sqlite database expert` | Helpful if M002 query work grows into FTS/aggregate/index tuning. Highest install count among SQLite matches. | `npx skills add martinholovsky/claude-skills-generator@sqlite database expert` |
| systemd / VPS services | `chaterm/terminal-skills@systemd` | Relevant for the remote-serving/systemd slice. Highest install count among systemd matches. | `npx skills add chaterm/terminal-skills@systemd` |
| web scraping hardening | `jamditis/claude-skills-journalism@web-scraping` | Potentially useful if acquisition hardening becomes a deeper slice, though it is less directly aligned than the code already present. Highest install count among scraping matches. | `npx skills add jamditis/claude-skills-journalism@web-scraping` |

No additional UI or Python framework skills were necessary because the codebase is plain Python SSR, not React/Vue/Next.

## Sources

### Internal code and project sources
- `vinted_radar/dashboard.py`
- `vinted_radar/repository.py`
- `vinted_radar/scoring.py`
- `vinted_radar/state_machine.py`
- `vinted_radar/services/runtime.py`
- `vinted_radar/services/state_refresh.py`
- `vinted_radar/services/discovery.py`
- `vinted_radar/http.py`
- `vinted_radar/db.py`
- `install_services.sh`
- `tests/test_dashboard.py`
- `tests/test_repository.py`
- `tests/test_runtime_service.py`
- `tests/test_runtime_cli.py`
- `tests/test_scoring.py`
- `tests/test_discovery_service.py`
- `README.md`

### External references
- Search query: `site:docs.python.org wsgiref simple_server not for production documentation`
  - Python `wsgiref` documentation: https://docs.python.org/3/library/wsgiref.html
- Search query: `site:sqlite.org wal.html readers do not block writers SQLite`
  - SQLite WAL documentation: https://www.sqlite.org/wal.html
- Search query: `site:sqlite.org FTS5 LIKE leading wildcard performance SQLite docs`
  - SQLite FTS5 documentation: https://www.sqlite.org/fts5.html
