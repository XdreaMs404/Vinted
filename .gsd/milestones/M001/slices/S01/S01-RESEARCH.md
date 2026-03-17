# M001/S01 — Research

**Date:** 2026-03-17

## Summary

S01 is the first hard-risk slice because the repository still has no runtime code: at the project root, only `.gitignore` and GSD planning artifacts exist. This slice directly owns **R001** and supports **R010** and **R011**, so the first implementation must do two things at once: prove that public Vinted discovery is technically viable without login, and choose a storage/ingestion shape that can grow into later revisit/history work instead of painting S02 into a corner.

Live probing shows the safest backbone is **public `vinted.com` HTML**, not undocumented APIs. Plain HTTP GETs to `https://www.vinted.com/catalog/...` and `https://www.vinted.com/items/...` returned server-rendered HTML containing escaped JSON fragments inside `self.__next_f.push(...)` scripts. Catalog pages expose both sub-category links and an escaped payload shaped like `\"items\":{\"items\":[...],\"pagination\":...}`. Sample pages for Men, Women, and first-level subcategories consistently exposed **96 items per page** and **`total_pages=10` / `total_entries=960`**. Item pages expose a main `item` object plus separate `breadcrumbs`, `attributes`, and `favourite` fragments. That is enough for S01 normalized ingestion without a browser, but it requires targeted extraction utilities and explicit null handling because not all useful fields live in one fragment.

The planner should therefore treat S01 as two proofs: **(1) extractor proof** — reliably decode catalog and item payloads from live HTML with fixtures; **(2) coverage/storage proof** — crawl Men/Women catalog trees, persist canonical listing identities plus first observations and raw evidence fragments, and emit an honest coverage artifact saying exactly which catalog IDs/pages were scanned. The implementation must stay explicit about partial fields, page caps, and observed-versus-inferred boundaries so later slices can build confidence surfaces on top of real evidence instead of assumptions.

## Recommendation

Bootstrap **a Python collector package** first. Use a persistent HTTP session (`httpx` or `requests`) for fetching, **BeautifulSoup** for category link discovery, targeted escaped-JSON extraction for the `self.__next_f.push(...)` fragments, and **SQLite** for local persistence. This matches the repo’s blank-slate state, keeps the collector easy to run locally, and avoids committing to a browser-first stack before there is evidence it is necessary.

Do **not** build S01 around undocumented internal Vinted APIs. External research and live probing both point the same way: the internal web API is where anti-bot/authorization friction appears, while the public HTML pages already expose enough SSR data for discovery and first-pass normalization. That aligns with **D002** (“Public collection only, no login required, and no central dependency on undocumented private APIs”). If the HTML path later breaks, Playwright can be added as a fallback collector, but it should not be the primary dependency for the first slice.

Model the data boundary now so S02 can extend it cleanly:

- **catalog registry** — canonical category identity by numeric catalog ID, parent/root relationships, label, URL, and last seen timestamp
- **listing identity** — stable listing ID, canonical item URL, current catalog/root catalog IDs, seller ID when known
- **observation row** — append-only snapshot with `observed_at`, normalized public fields, null-tolerant optional fields, and extractor version
- **raw evidence fragment** — targeted JSON/HTML snippets (catalog item block, item block, breadcrumbs block, favourite block, key meta tags), not full-page archives by default
- **coverage/run reporting** — discovery run, catalog/page scan counters, duplicate counts, errors, and stop reasons

That structure is the minimum needed to satisfy S01 honestly while also unblocking S02 history and S03 confidence work.

## Implementation Landscape

### Key Files

- `.gitignore` — extend ignores for local runtime state created by the collector (`data/`, `artifacts/`, `.pytest_cache/`, etc.); current root ignore file only covers generic Node/Python outputs, not a project DB or run artifacts.
- `pyproject.toml` — bootstrap the Python package, dependencies, test tooling, and CLI entrypoint.
- `src/vinted_radar/cli.py` — batch entrypoint for S01, e.g. `discover` command with flags like `--root`, `--max-pages-per-catalog`, `--db-path`, `--artifacts-dir`, `--item-details`.
- `src/vinted_radar/config.py` — base URL (`https://www.vinted.com`), pacing, timeouts, default headers, and configurable limits.
- `src/vinted_radar/vinted/flight_extract.py` — high-risk seam: functions such as `extract_catalog_payload(html: str)` and `extract_item_fragments(html: str)` that locate escaped JSON inside `self.__next_f.push(...)` scripts and decode it safely.
- `src/vinted_radar/vinted/catalog_tree.py` — crawl category pages from root seeds (`/catalog/5-men`, `/catalog/1904-women`), extract sub-category links, canonicalize by numeric catalog ID, and persist the Homme/Femme tree.
- `src/vinted_radar/vinted/discovery.py` — paginate catalog pages, dedupe listing IDs, normalize listing stubs from the catalog payload, and produce coverage counters per catalog/page.
- `src/vinted_radar/vinted/item_detail.py` — fetch item pages and merge the main `item` block with supporting fragments such as `breadcrumbs`, `attributes`, and `favourite`; keep missing fields nullable.
- `src/vinted_radar/models.py` — dataclasses or typed models for `CatalogNode`, `DiscoveryRun`, `ListingIdentity`, `ListingObservation`, and `RawEvidenceFragment`.
- `src/vinted_radar/storage/db.py` — SQLite connection/bootstrap and schema creation.
- `src/vinted_radar/storage/repository.py` — `upsert_catalog_node`, `upsert_listing_identity`, `append_observation`, `save_raw_evidence`, and `record_scan_coverage`.
- `tests/fixtures/vinted/catalog-men.html` — saved live HTML fixture for catalog extraction tests.
- `tests/fixtures/vinted/catalog-leaf.html` — saved live HTML fixture for a deeper subcategory page proving tree depth and pagination extraction.
- `tests/fixtures/vinted/item-sample.html` — saved live HTML fixture for item-detail fragment extraction.
- `tests/test_flight_extract.py` — decoder tests for escaped JSON extraction and regression protection when markup changes.
- `tests/test_catalog_tree.py` — tests for numeric catalog ID parsing, parent/child relationships, and slug-agnostic canonicalization.
- `tests/test_discovery_normalization.py` — tests for pagination stop conditions, null-tolerant normalization, and coverage counting.

### Build Order

1. **Bootstrap the collector stack** (`pyproject.toml`, package layout, runtime ignores) because there is no existing application code to extend.
2. **Prove the HTML extractor first** with saved fixtures from one catalog page and one item page. This is the highest-risk unknown and everything else depends on it.
3. **Implement catalog-tree discovery** from Men/Women roots and persist numeric catalog IDs plus parent/root relationships. This creates the seed registry S01 must hand to S02.
4. **Implement catalog-page pagination + listing-stub normalization** using the extracted `items` payload and first-page `pagination.total_pages`; stop strictly at reported bounds.
5. **Implement item-detail enrichment** to fetch a subset or all discovered listings and merge supporting fragments into a fuller normalized observation.
6. **Add SQLite persistence + coverage artifacts** so a single batch run leaves durable evidence: discovered catalogs, listing identities, first observations, raw evidence fragments, and per-run scan coverage.
7. **Expose one CLI smoke path** (`discover`) that proves S01 end to end for a limited page budget before scaling breadth.

This order retires the main uncertainty early and creates clean seams for S02: stable listing identity, append-only observations, and coverage/run metadata.

### Verification Approach

- **Fixture tests first**
  - `python -m pytest tests/test_flight_extract.py tests/test_catalog_tree.py tests/test_discovery_normalization.py`
  - Required proofs:
    - catalog fixture yields a decoded payload with `items` and `pagination`
    - item fixture yields main item data plus supporting fragments
    - numeric catalog IDs parse correctly from mixed-language slugs
    - null/missing fields do not crash normalization
- **Batch smoke run**
  - Example target command: `python -m vinted_radar.cli discover --root men --root women --max-pages-per-catalog 2 --item-details sample --db-path data/radar.db --artifacts-dir artifacts/s01-smoke`
  - Observable proof:
    - DB exists and contains non-zero rows for catalogs, listing identities, observations, and coverage/run tables
    - `artifacts/s01-smoke/coverage.json` lists scanned catalog IDs, pages scanned, unique listings seen, duplicates, errors, and stop reasons
    - observed currency codes are stored as observed, not hardcoded
    - optional fields such as favourites/size/description can be null without aborting the run
- **Manual artifact check**
  - Confirm roots `5` (Men) and `1904` (Women) are present in catalog registry.
  - Confirm at least one deeper leaf exists (example from live probing: Men → Accessories → Jewelry → Necklaces; Women → Clothing → Tops & T-shirts → Blouses/T-shirts/etc.).
  - Confirm page requests do not continue after reported `total_pages`; live probing showed pages `> total_pages` return empty items and undefined pagination.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| HTML link extraction and DOM traversal | `beautifulsoup4` | Catalog tree discovery is regular anchor parsing; a DOM parser is safer than regex and cheaper than a browser. |
| Local-first persistence | SQLite (`sqlite3`) | Zero external service, easy local operation, and a good fit for append-only observations plus coverage tables. |
| CLI ergonomics | `typer` | Gives S01 a fast batch entrypoint and leaves a clean path to S06 local operator commands. |

## Constraints

- The root project currently has **no application code, no package manifest, no tests, and no lockfile**. S01 must begin by choosing and scaffolding its own runtime stack.
- Plain HTTP requests to **`vinted.fr` returned 403** during live probing, while **`vinted.com` catalog and item pages returned 200** with usable SSR payloads. The collector should therefore default to `vinted.com`, keep base URL configurable, and record observed locale/currency instead of assuming FR/EUR.
- Catalog URLs appear with **mixed English/French slugs** (`/catalog/5-men`, `/catalog/5-hommes`, `/catalog/2050-clothing`, `/catalog/2050-vetements`). Canonical identity must come from the numeric catalog ID, not the slug text.
- Sample catalog pages exposed **`total_pages=10` / `total_entries=960`** repeatedly. Discovery coverage must report the scanned window honestly rather than implying global market completeness.
- The architecture must preserve **observed vs inferred separation** from day one per **D003**; S01 should store facts and raw evidence only, not premature lifecycle/state conclusions.

## Common Pitfalls

- **Canonicalizing by slug instead of numeric ID** — slugs vary by locale/language; use the `/catalog/<id>-...` numeric part as the stable key.
- **Trying to decode the whole React Flight protocol** — S01 only needs targeted escaped JSON fragments from known script blocks; keep the parser narrow and defend it with fixtures.
- **Assuming one item payload contains every field** — live probing showed breadcrumbs, attributes, favourites, and core item data are split across fragments; merge what is available and allow nulls.
- **Paginating optimistically past the reported bound** — pages beyond `total_pages` returned empty items and undefined pagination in live probing; stop from first-page metadata.
- **Hardcoding market assumptions** — observed pages returned USD in this environment; store `currency_code` as observed and defer market normalization to later slices.

## Open Risks

- Vinted may stop embedding the useful catalog/item fragments in SSR HTML, forcing a Playwright fallback or a different public-surface strategy.
- The public catalog window may be popularity- or freshness-limited; S01 can prove broad discovery mechanics, but not complete market exhaustiveness, from the sampled 10-page cap alone.
- Anti-bot behavior may change by geography/IP; the collector needs pacing, session reuse, and clear error accounting even if the first smoke runs succeed.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Browser fallback / Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | available, not installed (`npx skills add currents-dev/playwright-best-practices-skill@playwright-best-practices`) |
| SQLite schema design | `martinholovsky/claude-skills-generator@sqlite database expert` | available, not installed (`npx skills add "martinholovsky/claude-skills-generator@sqlite database expert"`) |

## Sources

- Public `vinted.com` catalog pages returned SSR HTML containing category links plus escaped item/pagination payloads during live probing on 2026-03-17 (source: [Men catalog](https://www.vinted.com/catalog/5-men), [Women catalog](https://www.vinted.com/catalog/1904-women))
- `vinted.com/robots.txt` allows `/` for general user agents while disallowing selected utility/admin paths, and marks `ai-train=no` (source: [Vinted robots.txt](https://www.vinted.com/robots.txt))
- The web internal API is a poor primary dependency because it is tied to auth cookies / anti-bot protections, while public HTML already exposes enough SSR data for S01 (source: [THE LAB #82: How to scrape Vinted using their internal APIs](https://substack.thewebscraping.club/p/how-to-scrape-vinted))
- The official Vinted Pro API is seller-upload oriented, not a replacement for public market discovery (source: [Vinted Pro Integrations](https://pro-docs.svc.vinted.com/))
