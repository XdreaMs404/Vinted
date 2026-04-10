# M003: 

## Vision
Turn the collector into an empirically tuned, benchmark-led acquisition system that maximizes net new listing discoveries per VPS day, supports multiple Vinted market domains safely, and keeps hot storage growth bounded without sacrificing evidence, diagnostics, or live product health.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Acquisition Benchmark Scorecards + VPS Experiment Harness | high | — | ✅ | After this: one command can run comparable VPS acquisition experiments and produce a leaderboard ranking profiles by net new listings/hour, duplicate ratio, challenge rate, bytes/new listing, and resource footprint. |
| S02 | Start-to-Start Multi-Lane Runtime Control | high | S01 | ✅ | After this: the runtime can execute named lanes such as frontier and expansion start-to-start, and `/runtime` / CLI surfaces show truthful per-lane state, timers, errors, and current config. |
| S03 | Market-Aware Identity + Domain Adapters | high | S01, S02 | ⬜ | After this: the collector can ingest more than one Vinted market domain into separated market partitions without ID collisions, mixed catalogs, or ambiguous diagnostics, while existing FR reads remain truthful. |
| S04 | Transport Optimizer + Empirical Concurrency/Session Tuning | high | S01, S02, S03 | ⬜ | After this: operators can benchmark proxy/session/concurrency profiles per market on the VPS and the system can explain which transport recipe wins on real useful yield rather than only on request speed. |
| S05 | Adaptive Frontier Depth + Cross-Market Acquisition Strategies | high | S02, S03, S04 | ⬜ | After this: FR and selected extra markets can run adaptive frontier plans that allocate page depth and lane budget where marginal new-listing yield is actually highest, with benchmark proof that the strategy beats the old fixed page-1 loop. |
| S06 | Hot-Store Compaction + Bounded Live History | medium | S03, S05 | ⬜ | After this: the chosen high-throughput acquisition profile can run repeatedly without ballooning hot storage, and operators can inspect bytes/new listing, retained history policy, and evidence-preservation diagnostics. |
| S07 | Best-Profile VPS Rollout + Acceptance Closure | medium | S04, S05, S06 | ⬜ | After this: the VPS runs the measured winning acquisition profile, public surfaces stay healthy, and a final acceptance bundle shows baseline-vs-production throughput, stability, and storage outcomes with no hand-wavy gaps. |
