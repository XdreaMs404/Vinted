---
estimated_steps: 7
estimated_files: 4
---

# T01: Add item-page probe persistence and parser contracts

**Slice:** S03 — Prudent State Machine + Confidence Surfaces
**Milestone:** M001

## Description

Add the direct item-page probe layer that lets the state machine rely on distinct public evidence, while keeping every probe outcome inspectable after execution.

## Steps

1. Add SQLite storage for item-page probes with response status, parsed outcome, and diagnostic detail.
2. Implement a parser for active, sold, unavailable, and unknown 200-page outcomes plus 404 deletion evidence.
3. Keep the parser narrow and explicit so unsupported page shapes degrade to `unknown` rather than guess.
4. Add fixtures for the supported probe outcomes.
5. Write parser tests that assert on the extracted public evidence flags.
6. Expose repository helpers for writing and reading the latest probe per listing.
7. Run the parser-focused test target before wiring the state engine.

## Must-Haves

- [x] Probe outcomes persist durably in SQLite.
- [x] The parser covers the supported public page shapes and distinct 404 deletion evidence.
- [x] Unsupported or changed page shapes degrade to `unknown`.

## Verification

- `python -m pytest tests/test_item_page_parser.py`
- `python -m vinted_radar.cli state-refresh --db data/vinted-radar-s02.db --limit 3`

## Observability Impact

- Signals added/changed: `item_page_probes` rows with HTTP status, parse outcome, and diagnostic detail.
- How a future agent inspects this: repository queries or `state --listing-id <id>` after refresh.
- Failure state exposed: HTTP failures and parser misses remain explicit as probe outcomes instead of disappearing into the derived state.

## Inputs

- `vinted_radar/repository.py` — existing SQLite boundary and history queries.
- `vinted_radar/http.py` — public HTTP client already used by the collector.

## Expected Output

- `vinted_radar/db.py` — probe table schema.
- `vinted_radar/parsers/item_page.py` — item-page outcome parser.
- `vinted_radar/repository.py` — probe persistence helpers.
- `tests/test_item_page_parser.py` — parser and persistence proof.
