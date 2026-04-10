# VPS benchmark bundle — vps-benchmark-dual-lane-smoke-2026-04-10T090637+0000

Generated at: `2026-04-10T09:06:37+00:00`

## Execution posture

- Host: `root@46.225.113.129`
- Remote repo: `/root/Vinted`
- Remote DB: `/root/Vinted/data/vinted-radar.clean.db`
- Remote Python: `/root/Vinted/venv/bin/python`
- Mode: `live-db`
- Destructive: `yes`
- Preserve live services: `yes`
- Mode note: Run the bounded experiment directly against the live SQLite path on the VPS. This preserves service uptime but mutates the live database.

## Profile

- Name: `dual-lane-smoke`
- Label: `Dual-lane frontier + expansion smoke`
- execution_kind: `multi-lane-runtime`
- page_limit: `None`
- max_leaf_categories: `None`
- root_scope: `None`
- min_price: `None`
- max_price: `None`
- state_refresh_limit: `None`
- request_delay: `None`
- timeout_seconds: `None`

## Lane profile

| Lane | Interval s | Max cycles | Root scope | Page limit | State probes |
|---|---:|---:|---|---:|---:|
| frontier | 900.0 | auto | women | 1 | 1 |
| expansion | 900.0 | auto | men | 1 | 1 |

- Started: `2026-04-10T08:51:06+00:00`
- Finished: `2026-04-10T09:06:37+00:00`
- Exported snapshot: `None`
- Cycles executed: `4`

## Cycle outcomes

| # | Started | Finished | Exit |
|---|---|---|---:|
| 1 | 2026-04-10T08:51:06+00:00 | 2026-04-10T08:51:28+00:00 | 0 |
| 2 | 2026-04-10T08:51:06+00:00 | 2026-04-10T08:51:30+00:00 | 0 |
| 3 | 2026-04-10T09:06:06+00:00 | 2026-04-10T09:06:28+00:00 | 0 |
| 4 | 2026-04-10T09:06:06+00:00 | 2026-04-10T09:06:27+00:00 | 0 |

## Resource snapshots

| Label | Captured at | CPU % | RAM MB |
|---|---|---:|---:|
| multi-lane-start | 2026-04-10T08:51:07+00:00 | 76.40 | 66.24 |
| multi-lane-sample-1 | 2026-04-10T08:51:23+00:00 | 98.10 | 203.00 |
| multi-lane-sample-2 | 2026-04-10T08:51:39+00:00 | 87.30 | 181.75 |
| multi-lane-sample-3 | 2026-04-10T08:51:55+00:00 | 58.60 | 181.74 |
| multi-lane-sample-4 | 2026-04-10T08:52:11+00:00 | 44.20 | 181.74 |
| multi-lane-sample-5 | 2026-04-10T08:52:27+00:00 | 35.60 | 181.62 |
| multi-lane-sample-6 | 2026-04-10T08:52:43+00:00 | 29.80 | 181.62 |
| multi-lane-sample-7 | 2026-04-10T08:52:59+00:00 | 25.60 | 181.74 |
| multi-lane-sample-8 | 2026-04-10T08:53:15+00:00 | 22.50 | 181.74 |
| multi-lane-sample-9 | 2026-04-10T08:53:31+00:00 | 20.10 | 181.87 |
| multi-lane-sample-10 | 2026-04-10T08:53:47+00:00 | 18.20 | 181.72 |
| multi-lane-sample-11 | 2026-04-10T08:54:03+00:00 | 16.60 | 181.84 |
| multi-lane-sample-12 | 2026-04-10T08:54:19+00:00 | 15.30 | 181.84 |
| multi-lane-sample-13 | 2026-04-10T08:54:35+00:00 | 14.20 | 181.84 |
| multi-lane-sample-14 | 2026-04-10T08:54:51+00:00 | 13.20 | 181.84 |
| multi-lane-sample-15 | 2026-04-10T08:55:07+00:00 | 12.40 | 181.84 |
| multi-lane-sample-16 | 2026-04-10T08:55:23+00:00 | 11.60 | 181.84 |
| multi-lane-sample-17 | 2026-04-10T08:55:39+00:00 | 11.00 | 181.84 |
| multi-lane-sample-18 | 2026-04-10T08:55:55+00:00 | 10.40 | 181.84 |
| multi-lane-sample-19 | 2026-04-10T08:56:11+00:00 | 9.90 | 181.84 |
| multi-lane-sample-20 | 2026-04-10T08:56:27+00:00 | 9.50 | 181.84 |
| multi-lane-sample-21 | 2026-04-10T08:56:43+00:00 | 9.00 | 181.84 |
| multi-lane-sample-22 | 2026-04-10T08:56:59+00:00 | 8.70 | 181.84 |
| multi-lane-sample-23 | 2026-04-10T08:57:15+00:00 | 8.30 | 181.84 |
| multi-lane-sample-24 | 2026-04-10T08:57:31+00:00 | 8.00 | 181.97 |
| multi-lane-sample-25 | 2026-04-10T08:57:47+00:00 | 7.70 | 181.97 |
| multi-lane-sample-26 | 2026-04-10T08:58:03+00:00 | 7.40 | 181.84 |
| multi-lane-sample-27 | 2026-04-10T08:58:19+00:00 | 7.20 | 182.09 |
| multi-lane-sample-28 | 2026-04-10T08:58:35+00:00 | 7.00 | 182.09 |
| multi-lane-sample-29 | 2026-04-10T08:58:52+00:00 | 6.70 | 182.09 |
| multi-lane-sample-30 | 2026-04-10T08:59:08+00:00 | 6.50 | 182.09 |
| multi-lane-sample-31 | 2026-04-10T08:59:24+00:00 | 6.40 | 182.09 |
| multi-lane-sample-32 | 2026-04-10T08:59:40+00:00 | 6.20 | 182.09 |
| multi-lane-sample-33 | 2026-04-10T08:59:56+00:00 | 6.00 | 182.22 |
| multi-lane-sample-34 | 2026-04-10T09:00:12+00:00 | 5.90 | 182.22 |
| multi-lane-sample-35 | 2026-04-10T09:00:28+00:00 | 5.70 | 182.34 |
| multi-lane-sample-36 | 2026-04-10T09:00:44+00:00 | 5.60 | 182.09 |
| multi-lane-sample-37 | 2026-04-10T09:01:00+00:00 | 5.40 | 182.34 |
| multi-lane-sample-38 | 2026-04-10T09:01:16+00:00 | 5.30 | 182.47 |
| multi-lane-sample-39 | 2026-04-10T09:01:32+00:00 | 5.20 | 182.47 |
| multi-lane-sample-40 | 2026-04-10T09:01:48+00:00 | 5.10 | 182.59 |
| multi-lane-sample-41 | 2026-04-10T09:02:04+00:00 | 5.00 | 182.59 |
| multi-lane-sample-42 | 2026-04-10T09:02:20+00:00 | 4.90 | 182.47 |
| multi-lane-sample-43 | 2026-04-10T09:02:36+00:00 | 4.80 | 182.47 |
| multi-lane-sample-44 | 2026-04-10T09:02:52+00:00 | 4.70 | 182.59 |
| multi-lane-sample-45 | 2026-04-10T09:03:08+00:00 | 4.60 | 182.59 |
| multi-lane-sample-46 | 2026-04-10T09:03:24+00:00 | 4.50 | 182.59 |
| multi-lane-sample-47 | 2026-04-10T09:03:40+00:00 | 4.40 | 182.59 |
| multi-lane-sample-48 | 2026-04-10T09:03:56+00:00 | 4.40 | 182.59 |
| multi-lane-sample-49 | 2026-04-10T09:04:12+00:00 | 4.30 | 182.72 |
| multi-lane-sample-50 | 2026-04-10T09:04:28+00:00 | 4.20 | 182.72 |
| multi-lane-sample-51 | 2026-04-10T09:04:44+00:00 | 4.10 | 182.84 |
| multi-lane-sample-52 | 2026-04-10T09:05:00+00:00 | 4.10 | 182.84 |
| multi-lane-sample-53 | 2026-04-10T09:05:16+00:00 | 4.00 | 182.84 |
| multi-lane-sample-54 | 2026-04-10T09:05:32+00:00 | 3.90 | 182.84 |
| multi-lane-sample-55 | 2026-04-10T09:05:48+00:00 | 3.90 | 182.97 |
| multi-lane-sample-56 | 2026-04-10T09:06:04+00:00 | 3.80 | 182.97 |
| multi-lane-sample-57 | 2026-04-10T09:06:20+00:00 | 5.00 | 256.84 |
| multi-lane-sample-58 | 2026-04-10T09:06:36+00:00 | 6.60 | 265.02 |
| multi-lane-finish | 2026-04-10T09:06:37+00:00 | 0.00 | 12.88 |

## Lane runtime outcomes

| Lane | Cycles | Statuses | Benchmarks |
|---|---:|---|---|
| expansion | 2 | completed, completed | expansion-smoke, expansion-smoke |
| frontier | 2 | completed, completed | frontier-smoke, frontier-smoke |

## Serving verification

- Base URL: `http://46.225.113.129:8765`
- Expected lanes: `frontier, expansion`
- Proof observed while running: `yes`
- Final truth observed after completion: `yes`
- Overall status: `pass`

| Captured at | Runtime | Runtime API | Health | Running lanes |
|---|---:|---:|---:|---|
| 2026-04-10T08:51:35+00:00 | 200 | 200 | 200 | expansion, frontier |
| 2026-04-10T08:52:15+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:52:54+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:53:34+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:54:14+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:54:55+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:55:35+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:56:14+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:56:53+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:57:33+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:58:12+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:58:51+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T08:59:30+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:00:09+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:00:49+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:01:28+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:02:07+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:02:46+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:03:25+00:00 | 200 | 200 | 200 | none |
| 2026-04-10T09:04:04+00:00 | 200 | 200 | 200 | none |
| … | … | … | … | 5 additional samples omitted |

## Acquisition benchmark report

# Acquisition benchmark — acquisition-benchmark-2026-04-10T090637+0000

Generated at: `2026-04-10T09:06:37+00:00`

## Method

- Compared profiles: `1`
- Profiles: `dual-lane-smoke`
- Higher `net_new_listings_per_hour` wins.
- Ties break on lower duplicate ratio, lower challenge rate, lower degraded count, lower bytes per new listing, lower mean CPU, and lower peak RAM.
- Winner sort order: `net_new_listings_per_hour desc, duplicate_ratio asc, challenge_rate asc, degraded_count asc, bytes_per_new_listing asc, mean_cpu_percent asc, peak_ram_mb asc, experiment_id asc`

### Score formulas

- `net_new_listings` = max(listing_count_end - listing_count_start, 0) with discovery unique hits as a fallback when listing snapshots are absent
- `duplicate_ratio` = max(raw_listing_hits - net_new_listings, 0) / raw_listing_hits
- `challenge_rate` = challenge_count / (catalog_scan_count + state_probe_count)
- `bytes_per_new_listing` = storage_growth_bytes / net_new_listings

## Why the winner ranked first

- Winner: `dual-lane-smoke`
- Reason: Only one experiment was supplied, so it ranks first by default.

## Leaderboard

| Rank | Profile | Net new/h | Duplicate ratio | Challenge rate | Degraded | Bytes/new | Mean CPU % | Peak RAM MB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | dual-lane-smoke 🏆 | 81.21 | 0.9453 | 0.0000 | 0 | 30037.33 | 14.25 | 265.02 |

## dual-lane-smoke (rank 1)

- Label: `Dual-lane frontier + expansion smoke`
- Window: `2026-04-10T08:51:06+00:00` → `2026-04-10T09:06:37+00:00` (`0.26` hours)
- Discovery runs: `4` | raw hits `384` | unique hits `384`
- Catalog scans: `4` | scan challenges `0` | scan failures `0`
- Runtime cycles: `4` | degraded cycles `0` | degraded probes `0`
- Scorecard: net new/h `81.21` | duplicate ratio `0.9453` | challenge rate `0.0000` | degraded `0`
- Storage growth: `630784` bytes | bytes/new listing `30037.33`
- Resource snapshots: `60` | mean CPU `14.25` | peak RAM `265.02` MB
- Declared config: `{"profile": {"default_mode": "live-db", "execution_kind": "multi-lane-runtime", "expected_lanes": ["frontier", "expansion"], "label": "Dual-lane frontier + expansion smoke", "lanes": [{"benchmark_label": "frontier-smoke", "concurrency": 1, "interval_seconds": 900.0, "lane_name": "frontier", "max_leaf_categories": 1, "max_price": 0.0, "min_price": 30.0, "page_limit": 1, "request_delay": 3.0, "root_scope": "women", "state_refresh_limit": 1, "timeout_seconds": 20.0}, {"benchmark_label": "expansion-smoke", "concurrency": 1, "interval_seconds": 900.0, "lane_name": "expansion", "max_leaf_categories": 1, "max_price": 0.0, "min_price": 30.0, "page_limit": 1, "request_delay": 3.0, "root_scope": "men", "state_refresh_limit": 1, "timeout_seconds": 20.0}], "requires_live_runtime_truth": true, "stop_services": ["vinted-scraper.service"]}, "remote": {"db_path": "/root/Vinted/data/vinted-radar.clean.db", "host": "46.225.113.129", "identity_file": "C:\\Users\\Alexis\\.ssh\\id_ed25519", "repo_root": "/root/Vinted", "ssh_port": 22, "ssh_target": "root@46.225.113.129", "vps_env_file": "C:\\Users\\Alexis\\Documents\\VintedScrap2\\.env.vps"}, "runner": {"description": "Run the bounded experiment directly against the live SQLite path on the VPS. This preserves service uptime but mutates the live database.", "destructive": true, "duration_minutes": 30.0, "mode": "live-db", "preserves_live_service_posture": true, "sample_interval_seconds": 15.0, "verify_base_url": "http://46.225.113.129:8765", "verify_poll_interval_seconds": 10.0, "verify_timeout_seconds": 20.0, "wait_between_cycles_seconds": 0.0}}`
- Observed config: `{"interval_seconds": 900.0, "max_leaf_categories": 1, "page_limit": 1, "request_delay_seconds": 3.0, "root_scope": ["women", "men"], "runtime_config": [{"concurrency": 1, "max_leaf_categories": 1, "max_price": 0.0, "min_price": 30.0, "page_limit": 1, "proxy_pool_size": 0, "request_delay": 3.0, "root_scope": "women", "state_refresh_limit": 1, "target_brands": [], "target_catalogs": [], "timeout_seconds": 20.0, "transport_mode": "direct"}, {"concurrency": 1, "max_leaf_categories": 1, "max_price": 0.0, "min_price": 30.0, "page_limit": 1, "proxy_pool_size": 0, "request_delay": 3.0, "root_scope": "men", "state_refresh_limit": 1, "target_brands": [], "target_catalogs": [], "timeout_seconds": 20.0, "transport_mode": "direct"}], "runtime_mode": "continuous", "state_probe_limit": 1}`

