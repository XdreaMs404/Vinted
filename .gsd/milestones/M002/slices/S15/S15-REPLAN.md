# S15 Replan

**Milestone:** M002
**Slice:** S15
**Blocker Task:** T03
**Created:** 2026-03-31T15:11:05.697Z

## Blocker Description

S15/T03 proved that the warehouse schema defines change-fact tables, but the active cutover/backfill path only ingests listing-seen and state-refresh probe batches, so price-change and state-transition marts cannot be populated truthfully.

## What Changed

Replaced the old single operational-closure task with a staged recovery plan: first add a truthful live-and-backfilled change-fact derivation path, then build the AI-ready feature/evidence marts on top of populated change facts, then finish docs/audit/acceptance against the corrected warehouse contract. Requirement coverage is preserved, and the security posture stays materially unchanged aside from added observability for the new change-fact path.
