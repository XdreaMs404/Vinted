---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Projectors for current-state truth

Implement PostgreSQL repositories and projectors for current-state truth. Add adapters that consume outbox events and update runtime/controller rows, discovery bookkeeping, catalog rows, listing current-state rows, and presence rollups in PostgreSQL without duplicating raw evidence blobs.

## Inputs

- `vinted_radar/platform/outbox.py`
- `vinted_radar/domain/events.py`
- `vinted_radar/repository.py`

## Expected Output

- `vinted_radar/platform/postgres_repository.py`
- `projector services`
- `tests/test_postgres_projectors.py`

## Verification

python -m pytest tests/test_postgres_projectors.py -q
