# Project Knowledge

Append-only register of project-specific rules, patterns, and lessons learned.
Agents read this before every unit. Add entries when you discover something worth remembering.

## Rules

| # | Scope | Rule | Why | Added |
|---|-------|------|-----|-------|
| 1 | acquisition | Keep raw evidence at the card-fragment level by default (`overlay_title`, visible subtitle/price texts, canonical URL, image alt) rather than archiving full pages. | It preserves explainability for listing normalization without ballooning local storage or diff noise. | 2026-03-17 |

## Patterns

| # | Pattern | Where | Notes |
|---|---------|-------|-------|
| 1 | The public `/catalog` HTML embeds the full Homme/Femme catalog tree inside `self.__next_f.push(...)`, and listing cards are already server-rendered under `div.new-item-box__container`. | `vinted_radar/parsers/catalog_tree.py`, `vinted_radar/parsers/catalog_page.py` | Seed discovery and listing ingestion can stay browserless until Vinted removes or materially reshapes these SSR surfaces. |
| 2 | Keep per-run listing history in `listing_observations` and retain `listing_discoveries` as the lower-level per-sighting debug layer. | `vinted_radar/repository.py`, `vinted_radar/db.py` | This split keeps cadence/freshness queries cheap without losing page/category-level evidence when debugging collection behavior. |
| 3 | Public item pages expose `can_buy`, `is_closed`, `is_hidden`, and `is_reserved` inside escaped script text; normalizing escaped quotes before matching keeps item probes browserless. | `vinted_radar/parsers/item_page.py`, `vinted_radar/services/state_refresh.py` | Distinct 404s plus these buy-state flags are the current direct evidence surface for S03 state resolution. |
| 4 | Keep premium scoring demand-led and only apply a contextual price boost when the selected peer group clears explicit support thresholds. | `vinted_radar/scoring.py` | This avoids fake precision from thin peer groups while still surfacing contextually expensive fast movers. |

## Lessons Learned

| # | What Happened | Root Cause | Fix | Scope |
|---|--------------|------------|-----|-------|
| 1 | Live discovery needed both broad seed coverage and low request volume for smoke verification. | Homme/Femme contain 405 leaf catalogs, so a full one-page sweep is real but heavier than a quick verification pass. | Keep the batch CLI default conservative and use `--max-leaf-categories` for smoke runs while still syncing the full seed registry every run. | S01+ |
| 2 | Live CLI output can fail on real titles even when the data pipeline is correct. | Public item titles can contain characters unsupported by the active terminal encoding. | Sanitize display output on the CLI boundary; keep JSON output lossless for machine inspection. | S02+ |
| 3 | Narrow fixture-only probe parsing left real 200 item pages unresolved. | The buy-state block on live item pages is embedded as escaped JSON text, not always in the same unescaped field order as the fixture. | Normalize escaped quotes before matching and keep unmatched pages as `unknown` instead of forcing a guess. | S03+ |
| 4 | Premium ranking becomes noisy fast when price context is too sparse. | Thin peer groups make percentile-based price boosts look precise even when they are effectively random. | Require explicit minimum support for each context tier and drop back to demand-led scoring when no trustworthy peer group exists. | S04+ |
