---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Outbox/lake ingestion into ClickHouse

Implement the ingestion worker from outbox/manifests into ClickHouse. Consume listing-seen and probe batches, map them into raw fact tables, maintain replay-safe inserts, and expose ingestion lag/error state so S14 cutover can trust whether analytical data is current.

## Inputs

- `vinted_radar/platform/outbox.py`
- `vinted_radar/platform/lake_writer.py`
- `vinted_radar/domain/events.py`

## Expected Output

- `ClickHouse ingestion worker`
- `tests/test_clickhouse_ingest.py`

## Verification

python -m pytest tests/test_clickhouse_ingest.py -q

## Execution Override

- Use the inlined **Task Summary** and **Decisions** templates already present in the auto-mode `execute-task` prompt for any closeout or decision logging produced during this task.
- Treat any instruction that points to a user-home template path such as `~/.gsd/...` as stale guidance and ignore it.
