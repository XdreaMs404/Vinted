# VPS benchmark bundle — vps-benchmark-baseline-fr-page1-2026-04-09T131336+0000

Generated at: `2026-04-09T13:13:36+00:00`

## Execution posture

- Host: `root@46.225.113.129`
- Remote repo: `/root/Vinted`
- Remote DB: `/root/Vinted/data/vinted-radar.clean.db`
- Remote Python: `/root/Vinted/venv/bin/python`
- Mode: `preserve-live`
- Destructive: `no`
- Preserve live services: `yes`
- Mode note: Create a temporary SQLite snapshot on the VPS, run the bounded experiment against the snapshot, and leave the live DB plus systemd services untouched.

## Profile

- Name: `baseline-fr-page1`
- Label: `Baseline FR page-limit=1`
- page_limit: `1`
- max_leaf_categories: `6`
- root_scope: `both`
- min_price: `30.0`
- max_price: `0.0`
- state_refresh_limit: `6`
- request_delay: `3.0`
- timeout_seconds: `20.0`

## Remote experiment window

- Started: `2026-04-09T13:11:17+00:00`
- Finished: `2026-04-09T13:13:36+00:00`
- Exported snapshot: `/root/Vinted/data/vinted-radar.clean.benchmark-work-20260409T131112Z.benchmark-export-20260409T131336Z.db`
- Cycles executed: `3`

## Cycle outcomes

| # | Started | Finished | Exit |
|---|---|---|---:|
| 1 | 2026-04-09T13:11:17+00:00 | 2026-04-09T13:12:05+00:00 | 0 |
| 2 | 2026-04-09T13:12:06+00:00 | 2026-04-09T13:12:51+00:00 | 0 |
| 3 | 2026-04-09T13:12:52+00:00 | 2026-04-09T13:13:35+00:00 | 0 |

## Resource snapshots

| Label | Captured at | CPU % | RAM MB |
|---|---|---:|---:|
| cycle-1-start | 2026-04-09T13:11:18+00:00 | 0.00 | 7.00 |
| cycle-1-sample-1 | 2026-04-09T13:11:34+00:00 | 16.20 | 122.23 |
| cycle-1-sample-2 | 2026-04-09T13:11:50+00:00 | 8.90 | 157.98 |
| cycle-1-finish | 2026-04-09T13:12:06+00:00 | 0.00 | 12.25 |
| cycle-2-start | 2026-04-09T13:12:07+00:00 | 0.00 | 7.12 |
| cycle-2-sample-1 | 2026-04-09T13:12:23+00:00 | 14.60 | 149.19 |
| cycle-2-sample-2 | 2026-04-09T13:12:39+00:00 | 8.20 | 165.94 |
| cycle-2-finish | 2026-04-09T13:12:52+00:00 | 0.00 | 12.25 |
| cycle-3-start | 2026-04-09T13:12:53+00:00 | 0.00 | 7.75 |
| cycle-3-sample-1 | 2026-04-09T13:13:09+00:00 | 14.20 | 132.32 |
| cycle-3-sample-2 | 2026-04-09T13:13:25+00:00 | 8.20 | 163.95 |
| cycle-3-finish | 2026-04-09T13:13:36+00:00 | 0.00 | 12.25 |

## Acquisition benchmark report

# Acquisition benchmark — acquisition-benchmark-2026-04-09T131336+0000

Generated at: `2026-04-09T13:13:36+00:00`

## Method

- Compared profiles: `1`
- Profiles: `baseline-fr-page1`
- Higher `net_new_listings_per_hour` wins.
- Ties break on lower duplicate ratio, lower challenge rate, lower degraded count, lower bytes per new listing, lower mean CPU, and lower peak RAM.
- Winner sort order: `net_new_listings_per_hour desc, duplicate_ratio asc, challenge_rate asc, degraded_count asc, bytes_per_new_listing asc, mean_cpu_percent asc, peak_ram_mb asc, experiment_id asc`

### Score formulas

- `net_new_listings` = max(listing_count_end - listing_count_start, 0) with discovery unique hits as a fallback when listing snapshots are absent
- `duplicate_ratio` = max(raw_listing_hits - net_new_listings, 0) / raw_listing_hits
- `challenge_rate` = challenge_count / (catalog_scan_count + state_probe_count)
- `bytes_per_new_listing` = storage_growth_bytes / net_new_listings

## Why the winner ranked first

- Winner: `baseline-fr-page1`
- Reason: Only one experiment was supplied, so it ranks first by default.

## Leaderboard

| Rank | Profile | Net new/h | Duplicate ratio | Challenge rate | Degraded | Bytes/new | Mean CPU % | Peak RAM MB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | baseline-fr-page1 🏆 | 1398.96 | 0.9688 | 0.0000 | 4 | 47938.37 | 5.86 | 165.94 |

## baseline-fr-page1 (rank 1)

- Label: `Baseline FR page-limit=1`
- Window: `2026-04-09T13:11:17+00:00` → `2026-04-09T13:13:36+00:00` (`0.04` hours)
- Discovery runs: `3` | raw hits `1728` | unique hits `1728`
- Catalog scans: `18` | scan challenges `0` | scan failures `0`
- Runtime cycles: `3` | degraded cycles `2` | degraded probes `2`
- Scorecard: net new/h `1398.96` | duplicate ratio `0.9688` | challenge rate `0.0000` | degraded `4`
- Storage growth: `2588672` bytes | bytes/new listing `47938.37`
- Resource snapshots: `12` | mean CPU `5.86` | peak RAM `165.94` MB
- Declared config: `{"profile": {"label": "Baseline FR page-limit=1", "max_leaf_categories": 6, "max_price": 0.0, "min_price": 30.0, "page_limit": 1, "request_delay": 3.0, "root_scope": "both", "state_refresh_limit": 6, "timeout_seconds": 20.0}, "remote": {"db_path": "/root/Vinted/data/vinted-radar.clean.db", "host": "46.225.113.129", "identity_file": "C:\\Users\\Alexis\\.ssh\\id_ed25519", "repo_root": "/root/Vinted", "ssh_port": 22, "ssh_target": "root@46.225.113.129", "vps_env_file": "C:\\Users\\Alexis\\Documents\\VintedScrap2\\.env.vps"}, "runner": {"description": "Create a temporary SQLite snapshot on the VPS, run the bounded experiment against the snapshot, and leave the live DB plus systemd services untouched.", "destructive": false, "duration_minutes": 2.0, "mode": "preserve-live", "preserves_live_service_posture": true, "sample_interval_seconds": 15.0, "wait_between_cycles_seconds": 0.0}}`
- Observed config: `{"max_leaf_categories": 6, "page_limit": 1, "request_delay_seconds": 3.0, "root_scope": "both", "runtime_config": {"concurrency": 24, "max_leaf_categories": 6, "max_price": 0.0, "min_price": 30.0, "page_limit": 1, "proxy_pool_size": 100, "request_delay": 3.0, "root_scope": "both", "state_refresh_limit": 6, "target_brands": [], "target_catalogs": [], "timeout_seconds": 20.0, "transport_mode": "proxy-pool"}, "runtime_mode": "batch", "state_probe_limit": 6}`

