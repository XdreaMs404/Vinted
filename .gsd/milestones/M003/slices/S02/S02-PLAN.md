# S02: Stable grouped reads via Postgres + ClickHouse parity

**Goal:** Make grouped product truth durable, fast, and parity-safe by persisting group projection, extending ClickHouse with group-aware marts, and shipping grouped analytical reads that survive refreshes without splitting product truth across backends.
**Demo:** After this: After refreshes and backend cutover, a user can still browse grouped leaders/comparisons/detail and see the same grouped truth, with grouped reads powered by persisted projection and parity-checked analytical marts rather than request-time fuzzy grouping.

## Tasks
