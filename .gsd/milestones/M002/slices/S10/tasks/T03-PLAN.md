---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T03: Event envelopes + outbox/manifests

Define the durable event, outbox, and manifest contracts that future slices will write once and project many times. Add versioned event envelope dataclasses/serializers, deterministic event IDs, evidence manifest IDs/checksums, and PostgreSQL outbox tables/interfaces that make multi-sink delivery idempotent instead of ad hoc.

## Inputs

- `vinted_radar/models.py`
- `vinted_radar/repository.py`
- `vinted_radar/parsers/api_catalog_page.py`

## Expected Output

- `vinted_radar/domain/events.py`
- `vinted_radar/platform/outbox.py`
- `tests/test_event_envelope.py`
- `tests/test_outbox.py`

## Verification

python -m pytest tests/test_event_envelope.py tests/test_outbox.py -q
