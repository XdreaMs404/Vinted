from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from vinted_radar.proxies import mask_proxy_url
from vinted_radar.repository import RadarRepository

_CHALLENGE_MARKERS = (
    "captcha",
    "challenge",
    "turnstile",
    "cloudflare",
    "attention required",
    "just a moment",
    "__cf_chl",
)


def collect_acquisition_benchmark_facts(
    db_path: str | Path,
    *,
    experiment_id: str,
    profile: str,
    window_started_at: str,
    window_finished_at: str,
    label: str | None = None,
    config: dict[str, object] | None = None,
    storage_snapshots: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
    resource_snapshots: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    with RadarRepository(db_path) as repository:
        discovery_runs = _load_window_discovery_runs(
            repository,
            window_started_at=window_started_at,
            window_finished_at=window_finished_at,
        )
        catalog_scans = _load_window_catalog_scans(
            repository,
            window_started_at=window_started_at,
            window_finished_at=window_finished_at,
        )
        runtime_cycles = _load_window_runtime_cycles(
            repository,
            window_started_at=window_started_at,
            window_finished_at=window_finished_at,
        )

    return {
        "experiment_id": experiment_id,
        "profile": profile,
        "label": label or profile,
        "window": {
            "started_at": window_started_at,
            "finished_at": window_finished_at,
        },
        "config": dict(config or {}),
        "facts": {
            "db": {"path": str(Path(db_path))},
            "discovery_runs": discovery_runs,
            "catalog_scans": catalog_scans,
            "runtime_cycles": runtime_cycles,
            "storage_snapshots": [dict(item) for item in storage_snapshots],
            "resource_snapshots": [dict(item) for item in resource_snapshots],
        },
    }


def build_acquisition_benchmark_report(
    experiments: list[dict[str, object]] | tuple[dict[str, object], ...],
    *,
    generated_at: str | None = None,
) -> dict[str, object]:
    timestamp = _coerce_now(generated_at).replace(microsecond=0).isoformat()
    normalized_experiments = [
        _normalize_experiment_payload(dict(experiment)) for experiment in experiments
    ]
    ranked_experiments = _rank_experiments(normalized_experiments)

    leaderboard = []
    for rank, experiment in enumerate(ranked_experiments, start=1):
        experiment["rank"] = rank
        experiment["winner"] = rank == 1
        scorecard = dict(experiment.get("scorecard") or {})
        leaderboard.append(
            {
                "rank": rank,
                "winner": rank == 1,
                "experiment_id": experiment.get("experiment_id"),
                "profile": experiment.get("profile"),
                "label": experiment.get("label"),
                "window_hours": experiment.get("window", {}).get("duration_hours"),
                "net_new_listings": scorecard.get("net_new_listings"),
                "net_new_listings_per_hour": scorecard.get(
                    "net_new_listings_per_hour"
                ),
                "duplicate_ratio": scorecard.get("duplicate_ratio"),
                "challenge_rate": scorecard.get("challenge_rate"),
                "challenge_count": scorecard.get("challenge_count"),
                "degraded_count": scorecard.get("degraded_count"),
                "bytes_per_new_listing": scorecard.get("bytes_per_new_listing"),
                "mean_cpu_percent": scorecard.get("mean_cpu_percent"),
                "peak_ram_mb": scorecard.get("peak_ram_mb"),
            }
        )

    methodology = {
        "winner_sort_order": [
            "net_new_listings_per_hour desc",
            "duplicate_ratio asc",
            "challenge_rate asc",
            "degraded_count asc",
            "bytes_per_new_listing asc",
            "mean_cpu_percent asc",
            "peak_ram_mb asc",
            "experiment_id asc",
        ],
        "score_fields": [
            "net_new_listings",
            "net_new_listings_per_hour",
            "duplicate_ratio",
            "challenge_count",
            "challenge_rate",
            "degraded_count",
            "bytes_per_new_listing",
            "mean_cpu_percent",
            "peak_cpu_percent",
            "mean_ram_mb",
            "peak_ram_mb",
        ],
        "formulas": {
            "net_new_listings": "max(listing_count_end - listing_count_start, 0) with discovery unique hits as a fallback when listing snapshots are absent",
            "duplicate_ratio": "max(raw_listing_hits - net_new_listings, 0) / raw_listing_hits",
            "challenge_rate": "challenge_count / (catalog_scan_count + state_probe_count)",
            "bytes_per_new_listing": "storage_growth_bytes / net_new_listings",
        },
    }

    return {
        "benchmark_id": f"acquisition-benchmark-{_timestamp_slug(timestamp)}",
        "generated_at": timestamp,
        "methodology": methodology,
        "summary": _build_report_summary(leaderboard),
        "leaderboard": leaderboard,
        "experiments": ranked_experiments,
    }


def render_acquisition_benchmark_markdown(report: dict[str, object]) -> str:
    leaderboard = list(report.get("leaderboard") or [])
    experiments = list(report.get("experiments") or [])
    methodology = dict(report.get("methodology") or {})
    summary = dict(report.get("summary") or {})
    compared_profiles = [
        str(item)
        for item in list(summary.get("profiles") or [])
        if str(item).strip()
    ]

    lines = [
        f"# Acquisition benchmark — {report.get('benchmark_id')}",
        "",
        f"Generated at: `{report.get('generated_at')}`",
        "",
        "## Method",
        "",
        f"- Compared profiles: `{summary.get('profile_count', len(leaderboard))}`",
        f"- Profiles: `{', '.join(compared_profiles) or 'n/a'}`",
        "- Higher `net_new_listings_per_hour` wins.",
        "- Ties break on lower duplicate ratio, lower challenge rate, lower degraded count, lower bytes per new listing, lower mean CPU, and lower peak RAM.",
        f"- Winner sort order: `{', '.join(list(methodology.get('winner_sort_order') or [])) or 'n/a'}`",
        "",
        "### Score formulas",
        "",
    ]

    for field_name, formula in dict(methodology.get("formulas") or {}).items():
        lines.append(f"- `{field_name}` = {formula}")

    lines.extend(
        [
            "",
            "## Why the winner ranked first",
            "",
            f"- Winner: `{summary.get('winner_profile') or summary.get('winner_experiment_id') or 'n/a'}`",
        ]
    )
    if summary.get("runner_up_profile") or summary.get("runner_up_experiment_id"):
        lines.append(
            f"- Runner-up: `{summary.get('runner_up_profile') or summary.get('runner_up_experiment_id')}`"
        )
    lines.append(f"- Reason: {summary.get('winner_reason') or 'n/a'}")

    lines.extend(
        [
            "",
            "## Leaderboard",
            "",
            "| Rank | Profile | Net new/h | Duplicate ratio | Challenge rate | Degraded | Bytes/new | Mean CPU % | Peak RAM MB |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for row in leaderboard:
        winner_suffix = " 🏆" if row.get("winner") else ""
        lines.append(
            "| {rank} | {profile}{winner_suffix} | {net_new_per_hour} | {duplicate_ratio} | {challenge_rate} | {degraded_count} | {bytes_per_new} | {mean_cpu} | {peak_ram} |".format(
                rank=row.get("rank"),
                profile=row.get("profile") or row.get("experiment_id"),
                winner_suffix=winner_suffix,
                net_new_per_hour=_format_number(row.get("net_new_listings_per_hour"), 2),
                duplicate_ratio=_format_number(row.get("duplicate_ratio"), 4),
                challenge_rate=_format_number(row.get("challenge_rate"), 4),
                degraded_count=row.get("degraded_count", 0),
                bytes_per_new=_format_number(row.get("bytes_per_new_listing"), 2),
                mean_cpu=_format_number(row.get("mean_cpu_percent"), 2),
                peak_ram=_format_number(row.get("peak_ram_mb"), 2),
            )
        )

    for experiment in experiments:
        discovery = dict(experiment.get("discovery") or {})
        scans = dict(experiment.get("catalog_scans") or {})
        runtime = dict(experiment.get("runtime") or {})
        storage = dict(experiment.get("storage") or {})
        resources = dict(experiment.get("resources") or {})
        scorecard = dict(experiment.get("scorecard") or {})
        window = dict(experiment.get("window") or {})
        config = dict(experiment.get("config") or {})
        declared_config = dict(config.get("declared") or {})
        observed_config = dict(config.get("observed") or {})

        lines.extend(
            [
                "",
                f"## {experiment.get('profile')} (rank {experiment.get('rank')})",
                "",
                f"- Label: `{experiment.get('label') or experiment.get('profile') or experiment.get('experiment_id')}`",
                f"- Window: `{window.get('started_at')}` → `{window.get('finished_at')}` (`{_format_number(window.get('duration_hours'), 2)}` hours)",
                f"- Discovery runs: `{discovery.get('run_count', 0)}` | raw hits `{discovery.get('raw_listing_hits', 0)}` | unique hits `{discovery.get('unique_listing_hits', 0)}`",
                f"- Catalog scans: `{scans.get('scan_count', 0)}` | scan challenges `{scans.get('challenge_count', 0)}` | scan failures `{scans.get('failure_count', 0)}`",
                f"- Runtime cycles: `{runtime.get('cycle_count', 0)}` | degraded cycles `{runtime.get('degraded_cycle_count', 0)}` | degraded probes `{runtime.get('degraded_probe_count', 0)}`",
                f"- Scorecard: net new/h `{_format_number(scorecard.get('net_new_listings_per_hour'), 2)}` | duplicate ratio `{_format_number(scorecard.get('duplicate_ratio'), 4)}` | challenge rate `{_format_number(scorecard.get('challenge_rate'), 4)}` | degraded `{scorecard.get('degraded_count', 0)}`",
                f"- Storage growth: `{storage.get('storage_growth_bytes')}` bytes | bytes/new listing `{_format_number(scorecard.get('bytes_per_new_listing'), 2)}`",
                f"- Resource snapshots: `{resources.get('sample_count', 0)}` | mean CPU `{_format_number(scorecard.get('mean_cpu_percent'), 2)}` | peak RAM `{_format_number(scorecard.get('peak_ram_mb'), 2)}` MB",
            ]
        )
        if declared_config:
            lines.append(
                f"- Declared config: `{json.dumps(declared_config, ensure_ascii=False, sort_keys=True)}`"
            )
        if observed_config:
            lines.append(
                f"- Observed config: `{json.dumps(observed_config, ensure_ascii=False, sort_keys=True)}`"
            )

    return "\n".join(lines) + "\n"


def write_acquisition_benchmark_report(
    report: dict[str, object],
    *,
    json_path: str | Path,
    markdown_path: str | Path | None = None,
) -> dict[str, str]:
    json_target = Path(json_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    written = {"json": str(json_target)}
    if markdown_path is not None:
        markdown_target = Path(markdown_path)
        markdown_target.parent.mkdir(parents=True, exist_ok=True)
        markdown_target.write_text(
            render_acquisition_benchmark_markdown(report),
            encoding="utf-8",
        )
        written["markdown"] = str(markdown_target)
    return written


def redact_acquisition_benchmark_report(report: dict[str, object]) -> dict[str, object]:
    sanitized = _sanitize_report_payload(report, key_path=())
    return sanitized if isinstance(sanitized, dict) else {}


def _build_report_summary(
    leaderboard: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> dict[str, object]:
    compared_profiles = [
        {
            "experiment_id": row.get("experiment_id"),
            "profile": row.get("profile"),
            "label": row.get("label"),
        }
        for row in leaderboard
    ]
    winner = None if not leaderboard else dict(leaderboard[0])
    runner_up = None if len(leaderboard) < 2 else dict(leaderboard[1])
    return {
        "profile_count": len(compared_profiles),
        "profiles": [
            str(item.get("profile") or item.get("experiment_id") or "")
            for item in compared_profiles
            if str(item.get("profile") or item.get("experiment_id") or "").strip()
        ],
        "compared_profiles": compared_profiles,
        "winner_experiment_id": None if winner is None else winner.get("experiment_id"),
        "winner_profile": None if winner is None else winner.get("profile"),
        "winner_label": None if winner is None else winner.get("label"),
        "runner_up_experiment_id": None if runner_up is None else runner_up.get("experiment_id"),
        "runner_up_profile": None if runner_up is None else runner_up.get("profile"),
        "runner_up_label": None if runner_up is None else runner_up.get("label"),
        "winner_reason": _build_winner_reason(winner, runner_up),
    }


def _build_winner_reason(
    winner: dict[str, object] | None,
    runner_up: dict[str, object] | None,
) -> str:
    if winner is None:
        return "No experiments were compared."
    if runner_up is None:
        return "Only one experiment was supplied, so it ranks first by default."

    metric_rules = (
        ("net_new_listings_per_hour", "higher", "net new listings/hour"),
        ("duplicate_ratio", "lower", "duplicate ratio"),
        ("challenge_rate", "lower", "challenge rate"),
        ("degraded_count", "lower", "degraded count"),
        ("bytes_per_new_listing", "lower", "bytes per new listing"),
        ("mean_cpu_percent", "lower", "mean CPU percent"),
        ("peak_ram_mb", "lower", "peak RAM MB"),
    )
    for index, (field_name, direction, label) in enumerate(metric_rules):
        winner_value = winner.get(field_name)
        runner_up_value = runner_up.get(field_name)
        if winner_value is None or runner_up_value is None:
            continue
        if winner_value == runner_up_value:
            continue
        winner_numeric = float(winner_value)
        runner_up_numeric = float(runner_up_value)
        if direction == "higher":
            prefix = "Won on"
        else:
            prefix = "Matched higher-priority metrics and won on" if index > 0 else "Won on"
        return (
            f"{prefix} {label}: "
            f"{_format_metric_value(field_name, winner_numeric)} vs "
            f"{_format_metric_value(field_name, runner_up_numeric)}."
        )

    return "All score fields tied, so deterministic experiment_id ordering ranked it first."


def _sanitize_report_payload(value: object, *, key_path: tuple[str, ...]) -> object:
    key_name = key_path[-1] if key_path else ""
    normalized_key = key_name.casefold()

    if isinstance(value, dict):
        return {
            str(item_key): _sanitize_report_payload(
                item_value,
                key_path=(*key_path, str(item_key)),
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [
            _sanitize_report_payload(item, key_path=key_path)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _sanitize_report_payload(item, key_path=key_path)
            for item in value
        ]
    if not isinstance(value, str):
        return value
    if _is_secret_key(normalized_key):
        return "<redacted>"
    if _is_proxy_key(normalized_key):
        return _mask_sensitive_url(value, prefer_proxy_mask=True)
    return _mask_sensitive_url(value)


def _is_secret_key(key_name: str) -> bool:
    return any(
        marker in key_name
        for marker in (
            "password",
            "passwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
            "authorization",
        )
    )


def _is_proxy_key(key_name: str) -> bool:
    return "proxy" in key_name


def _mask_sensitive_url(value: str, *, prefer_proxy_mask: bool = False) -> str:
    candidate = value.strip()
    if not candidate:
        return value
    if prefer_proxy_mask:
        try:
            return mask_proxy_url(candidate)
        except ValueError:
            pass
    if "://" not in candidate or "@" not in candidate:
        return value
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return value
    if parts.username is None and parts.password is None:
        return value
    hostname = parts.hostname or "unknown"
    port = f":{parts.port}" if parts.port is not None else ""
    return urlunsplit(
        (
            parts.scheme,
            f"***@{hostname}{port}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


def _format_metric_value(field_name: str, value: float) -> str:
    if field_name == "degraded_count":
        return str(int(round(value)))
    if field_name in {"duplicate_ratio", "challenge_rate"}:
        return f"{value:.4f}"
    return f"{value:.2f}"


def _normalize_experiment_payload(experiment: dict[str, object]) -> dict[str, object]:
    facts = dict(experiment.get("facts") or {})
    discovery_runs = _normalize_discovery_runs(facts.get("discovery_runs") or [])
    catalog_scans = _normalize_catalog_scans(facts.get("catalog_scans") or [])
    runtime_cycles = _normalize_runtime_cycles(facts.get("runtime_cycles") or [])
    storage_snapshots = _normalize_storage_snapshots(
        facts.get("storage_snapshots") or []
    )
    resource_snapshots = _normalize_resource_snapshots(
        facts.get("resource_snapshots") or []
    )
    window = _normalize_window(
        dict(experiment.get("window") or {}),
        discovery_runs=discovery_runs,
        catalog_scans=catalog_scans,
        runtime_cycles=runtime_cycles,
        storage_snapshots=storage_snapshots,
        resource_snapshots=resource_snapshots,
    )
    storage = _summarize_storage(storage_snapshots)
    discovery = _summarize_discovery_runs(discovery_runs)
    catalog_scan_summary = _summarize_catalog_scans(catalog_scans)
    runtime = _summarize_runtime_cycles(runtime_cycles)
    resources = _summarize_resource_snapshots(resource_snapshots)
    scorecard = _build_scorecard(
        window=window,
        discovery=discovery,
        catalog_scans=catalog_scan_summary,
        runtime=runtime,
        storage=storage,
        resources=resources,
    )

    profile = str(experiment.get("profile") or experiment.get("experiment_id") or "")
    experiment_id = str(experiment.get("experiment_id") or profile)
    label = str(experiment.get("label") or profile or experiment_id)

    return {
        "experiment_id": experiment_id,
        "profile": profile or experiment_id,
        "label": label,
        "window": window,
        "config": _normalize_config(
            explicit_config=dict(experiment.get("config") or {}),
            discovery_runs=discovery_runs,
            runtime_cycles=runtime_cycles,
        ),
        "facts": {
            "db": dict(facts.get("db") or {}),
            "discovery_runs": discovery_runs,
            "catalog_scans": catalog_scans,
            "runtime_cycles": runtime_cycles,
            "storage_snapshots": storage_snapshots,
            "resource_snapshots": resource_snapshots,
        },
        "discovery": discovery,
        "catalog_scans": catalog_scan_summary,
        "runtime": runtime,
        "storage": storage,
        "resources": resources,
        "scorecard": scorecard,
    }


def _normalize_window(
    raw_window: dict[str, object],
    *,
    discovery_runs: list[dict[str, object]],
    catalog_scans: list[dict[str, object]],
    runtime_cycles: list[dict[str, object]],
    storage_snapshots: list[dict[str, object]],
    resource_snapshots: list[dict[str, object]],
) -> dict[str, object]:
    explicit_started_at = _as_text(raw_window.get("started_at"))
    explicit_finished_at = _as_text(raw_window.get("finished_at"))

    candidate_starts = [
        explicit_started_at,
        *[row.get("started_at") for row in discovery_runs],
        *[row.get("fetched_at") for row in catalog_scans],
        *[row.get("started_at") for row in runtime_cycles],
        *[row.get("captured_at") for row in storage_snapshots],
        *[row.get("captured_at") for row in resource_snapshots],
    ]
    candidate_finishes = [
        explicit_finished_at,
        *[row.get("finished_at") or row.get("started_at") for row in discovery_runs],
        *[row.get("fetched_at") for row in catalog_scans],
        *[row.get("finished_at") or row.get("started_at") for row in runtime_cycles],
        *[row.get("captured_at") for row in storage_snapshots],
        *[row.get("captured_at") for row in resource_snapshots],
    ]

    started_at = _first_timestamp(candidate_starts)
    finished_at = _last_timestamp(candidate_finishes)
    duration_hours = _hours_between(started_at, finished_at)

    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_hours": None if duration_hours is None else round(duration_hours, 4),
        "source": "explicit" if explicit_started_at or explicit_finished_at else "derived",
    }


def _normalize_config(
    *,
    explicit_config: dict[str, object],
    discovery_runs: list[dict[str, object]],
    runtime_cycles: list[dict[str, object]],
) -> dict[str, object]:
    observed = {
        "root_scope": _collapse_unique_values(
            row.get("root_scope") for row in discovery_runs
        ),
        "page_limit": _collapse_unique_values(
            row.get("page_limit") for row in discovery_runs
        ),
        "max_leaf_categories": _collapse_unique_values(
            row.get("max_leaf_categories") for row in discovery_runs
        ),
        "request_delay_seconds": _collapse_unique_values(
            row.get("request_delay_seconds") for row in discovery_runs
        ),
        "runtime_mode": _collapse_unique_values(row.get("mode") for row in runtime_cycles),
        "interval_seconds": _collapse_unique_values(
            row.get("interval_seconds") for row in runtime_cycles
        ),
        "state_probe_limit": _collapse_unique_values(
            row.get("state_probe_limit") for row in runtime_cycles
        ),
        "runtime_config": _collapse_unique_values(
            row.get("config") for row in runtime_cycles if row.get("config")
        ),
    }
    return {
        "declared": explicit_config,
        "observed": {
            key: value for key, value in observed.items() if value is not None
        },
    }


def _summarize_discovery_runs(
    discovery_runs: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "run_count": len(discovery_runs),
        "raw_listing_hits": sum(int(row.get("raw_listing_hits") or 0) for row in discovery_runs),
        "unique_listing_hits": sum(
            int(row.get("unique_listing_hits") or 0) for row in discovery_runs
        ),
        "successful_scans": sum(
            int(row.get("successful_scans") or 0) for row in discovery_runs
        ),
        "failed_scans": sum(int(row.get("failed_scans") or 0) for row in discovery_runs),
        "scanned_leaf_catalogs": sum(
            int(row.get("scanned_leaf_catalogs") or 0) for row in discovery_runs
        ),
    }


def _summarize_catalog_scans(catalog_scans: list[dict[str, object]]) -> dict[str, object]:
    status_counts = Counter(
        "null" if row.get("response_status") is None else str(row.get("response_status"))
        for row in catalog_scans
    )
    challenge_count = sum(1 for row in catalog_scans if _catalog_scan_challenge(row))
    success_count = sum(1 for row in catalog_scans if bool(row.get("success")))

    return {
        "scan_count": len(catalog_scans),
        "success_count": success_count,
        "failure_count": len(catalog_scans) - success_count,
        "challenge_count": challenge_count,
        "http_403_count": sum(
            1 for row in catalog_scans if int(row.get("response_status") or 0) == 403
        ),
        "http_429_count": sum(
            1 for row in catalog_scans if int(row.get("response_status") or 0) == 429
        ),
        "response_status_counts": dict(sorted(status_counts.items())),
        "api_listing_count_total": sum(
            int(row.get("api_listing_count") or 0) for row in catalog_scans
        ),
        "accepted_listing_count_total": sum(
            int(row.get("accepted_listing_count") or 0) for row in catalog_scans
        ),
        "filtered_out_count_total": sum(
            int(row.get("filtered_out_count") or 0) for row in catalog_scans
        ),
    }


def _summarize_runtime_cycles(runtime_cycles: list[dict[str, object]]) -> dict[str, object]:
    cycle_status_counts = Counter(
        str(row.get("status") or "unknown") for row in runtime_cycles
    )
    summary_status_counts = Counter(
        str(dict(row.get("state_refresh_summary") or {}).get("status") or "unknown")
        for row in runtime_cycles
    )
    reason_counts = Counter()
    direct_signal_count = 0
    inconclusive_probe_count = 0
    degraded_probe_count = 0
    anti_bot_challenge_count = 0
    http_error_count = 0
    transport_error_count = 0
    state_probe_count = 0

    for row in runtime_cycles:
        summary = dict(row.get("state_refresh_summary") or {})
        direct_signal_count += int(summary.get("direct_signal_count") or 0)
        inconclusive_probe_count += int(summary.get("inconclusive_probe_count") or 0)
        degraded_probe_count += int(summary.get("degraded_probe_count") or 0)
        anti_bot_challenge_count += int(summary.get("anti_bot_challenge_count") or 0)
        http_error_count += int(summary.get("http_error_count") or 0)
        transport_error_count += int(summary.get("transport_error_count") or 0)
        state_probe_count += int(
            row.get("state_probed_count")
            or summary.get("probed_count")
            or summary.get("selected_target_count")
            or 0
        )
        for reason, count in dict(summary.get("reason_counts") or {}).items():
            reason_counts[str(reason)] += int(count or 0)

    return {
        "cycle_count": len(runtime_cycles),
        "completed_cycle_count": int(cycle_status_counts.get("completed", 0)),
        "failed_cycle_count": int(cycle_status_counts.get("failed", 0)),
        "interrupted_cycle_count": int(cycle_status_counts.get("interrupted", 0)),
        "degraded_cycle_count": int(summary_status_counts.get("degraded", 0)),
        "partial_cycle_count": int(summary_status_counts.get("partial", 0)),
        "healthy_cycle_count": int(summary_status_counts.get("healthy", 0)),
        "unknown_cycle_count": int(summary_status_counts.get("unknown", 0)),
        "state_probe_count": state_probe_count,
        "direct_signal_count": direct_signal_count,
        "inconclusive_probe_count": inconclusive_probe_count,
        "degraded_probe_count": degraded_probe_count,
        "anti_bot_challenge_count": anti_bot_challenge_count,
        "http_error_count": http_error_count,
        "transport_error_count": transport_error_count,
        "top_reasons": [
            {"reason": reason, "count": count}
            for reason, count in reason_counts.most_common(5)
        ],
    }


def _summarize_storage(storage_snapshots: list[dict[str, object]]) -> dict[str, object]:
    if not storage_snapshots:
        return {
            "snapshot_count": 0,
            "listing_count_start": None,
            "listing_count_end": None,
            "listing_count_delta": None,
            "db_size_bytes_start": None,
            "db_size_bytes_end": None,
            "artifact_size_bytes_start": None,
            "artifact_size_bytes_end": None,
            "storage_bytes_start": None,
            "storage_bytes_end": None,
            "storage_growth_bytes": None,
        }

    ordered = sorted(
        storage_snapshots,
        key=lambda row: (
            _coerce_datetime(row.get("captured_at")) or datetime.min.replace(tzinfo=UTC),
            json.dumps(row, ensure_ascii=False, sort_keys=True),
        ),
    )
    first = ordered[0]
    last = ordered[-1]

    listing_count_start = _coerce_int(
        first.get("listing_count")
        if first.get("listing_count") is not None
        else first.get("tracked_listings")
    )
    listing_count_end = _coerce_int(
        last.get("listing_count")
        if last.get("listing_count") is not None
        else last.get("tracked_listings")
    )
    storage_bytes_start = _storage_bytes(first)
    storage_bytes_end = _storage_bytes(last)
    db_size_bytes_start = _coerce_int(first.get("db_size_bytes"))
    db_size_bytes_end = _coerce_int(last.get("db_size_bytes"))
    artifact_size_bytes_start = _artifact_bytes(first)
    artifact_size_bytes_end = _artifact_bytes(last)

    return {
        "snapshot_count": len(storage_snapshots),
        "listing_count_start": listing_count_start,
        "listing_count_end": listing_count_end,
        "listing_count_delta": _subtract_ints(listing_count_end, listing_count_start),
        "db_size_bytes_start": db_size_bytes_start,
        "db_size_bytes_end": db_size_bytes_end,
        "artifact_size_bytes_start": artifact_size_bytes_start,
        "artifact_size_bytes_end": artifact_size_bytes_end,
        "storage_bytes_start": storage_bytes_start,
        "storage_bytes_end": storage_bytes_end,
        "storage_growth_bytes": _subtract_ints(storage_bytes_end, storage_bytes_start),
    }


def _summarize_resource_snapshots(
    resource_snapshots: list[dict[str, object]],
) -> dict[str, object]:
    cpu_values = [
        value
        for row in resource_snapshots
        if (value := _cpu_percent(row)) is not None
    ]
    ram_values = [
        value
        for row in resource_snapshots
        if (value := _ram_mb(row)) is not None
    ]

    return {
        "sample_count": len(resource_snapshots),
        "mean_cpu_percent": None if not cpu_values else round(sum(cpu_values) / len(cpu_values), 4),
        "peak_cpu_percent": None if not cpu_values else round(max(cpu_values), 4),
        "mean_ram_mb": None if not ram_values else round(sum(ram_values) / len(ram_values), 4),
        "peak_ram_mb": None if not ram_values else round(max(ram_values), 4),
    }


def _build_scorecard(
    *,
    window: dict[str, object],
    discovery: dict[str, object],
    catalog_scans: dict[str, object],
    runtime: dict[str, object],
    storage: dict[str, object],
    resources: dict[str, object],
) -> dict[str, object]:
    duration_hours = _coerce_float(window.get("duration_hours"))
    raw_listing_hits = int(discovery.get("raw_listing_hits") or 0)
    fallback_unique_hits = int(discovery.get("unique_listing_hits") or 0)
    listing_count_delta = _coerce_int(storage.get("listing_count_delta"))
    storage_growth_bytes = _coerce_int(storage.get("storage_growth_bytes"))
    derived_net_new = fallback_unique_hits if listing_count_delta is None else max(listing_count_delta, 0)
    duplicate_listing_hits = max(raw_listing_hits - derived_net_new, 0)

    scan_count = int(catalog_scans.get("scan_count") or 0)
    state_probe_count = int(runtime.get("state_probe_count") or 0)
    challenge_count = int(catalog_scans.get("challenge_count") or 0) + int(
        runtime.get("anti_bot_challenge_count") or 0
    )
    degraded_count = int(runtime.get("degraded_cycle_count") or 0) + int(
        runtime.get("degraded_probe_count") or 0
    )
    request_count = scan_count + state_probe_count

    bytes_per_new_listing = None
    if storage_growth_bytes is not None and derived_net_new > 0:
        bytes_per_new_listing = storage_growth_bytes / derived_net_new

    return {
        "net_new_source": "listing_count_delta" if listing_count_delta is not None else "discovery_unique_listing_hits_fallback",
        "net_new_listings": derived_net_new,
        "net_new_listings_per_hour": _divide(derived_net_new, duration_hours),
        "raw_listing_hits": raw_listing_hits,
        "duplicate_listing_hits": duplicate_listing_hits,
        "duplicate_ratio": _divide(duplicate_listing_hits, raw_listing_hits),
        "challenge_count": challenge_count,
        "challenge_rate": _divide(challenge_count, request_count),
        "degraded_count": degraded_count,
        "degraded_rate": _divide(degraded_count, request_count),
        "bytes_per_new_listing": None if bytes_per_new_listing is None else round(bytes_per_new_listing, 4),
        "storage_growth_bytes": storage_growth_bytes,
        "mean_cpu_percent": resources.get("mean_cpu_percent"),
        "peak_cpu_percent": resources.get("peak_cpu_percent"),
        "mean_ram_mb": resources.get("mean_ram_mb"),
        "peak_ram_mb": resources.get("peak_ram_mb"),
    }


def _rank_experiments(experiments: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        experiments,
        key=lambda experiment: (
            _desc_sort_key(experiment.get("scorecard", {}).get("net_new_listings_per_hour")),
            _asc_sort_key(experiment.get("scorecard", {}).get("duplicate_ratio")),
            _asc_sort_key(experiment.get("scorecard", {}).get("challenge_rate")),
            _asc_sort_key(experiment.get("scorecard", {}).get("degraded_count")),
            _asc_sort_key(experiment.get("scorecard", {}).get("bytes_per_new_listing")),
            _asc_sort_key(experiment.get("scorecard", {}).get("mean_cpu_percent")),
            _asc_sort_key(experiment.get("scorecard", {}).get("peak_ram_mb")),
            str(experiment.get("experiment_id") or ""),
        ),
    )


def _load_window_discovery_runs(
    repository: RadarRepository,
    *,
    window_started_at: str,
    window_finished_at: str,
) -> list[dict[str, object]]:
    rows = repository.connection.execute(
        "SELECT * FROM discovery_runs ORDER BY started_at ASC, run_id ASC"
    ).fetchall()
    normalized_rows = [dict(row) for row in rows]
    return [
        row
        for row in normalized_rows
        if _window_overlaps(
            row.get("started_at"),
            row.get("finished_at") or row.get("started_at"),
            window_started_at,
            window_finished_at,
        )
    ]


def _load_window_catalog_scans(
    repository: RadarRepository,
    *,
    window_started_at: str,
    window_finished_at: str,
) -> list[dict[str, object]]:
    rows = repository.connection.execute(
        """
        SELECT
            catalog_scans.*,
            catalogs.root_title AS root_title,
            catalogs.path AS catalog_path
        FROM catalog_scans
        JOIN catalogs ON catalogs.catalog_id = catalog_scans.catalog_id
        ORDER BY catalog_scans.fetched_at ASC, catalog_scans.run_id ASC, catalog_scans.catalog_id ASC, catalog_scans.page_number ASC
        """
    ).fetchall()
    normalized_rows = [dict(row) for row in rows]
    return [
        row
        for row in normalized_rows
        if _timestamp_between(
            row.get("fetched_at"), window_started_at, window_finished_at
        )
    ]


def _load_window_runtime_cycles(
    repository: RadarRepository,
    *,
    window_started_at: str,
    window_finished_at: str,
) -> list[dict[str, object]]:
    rows = repository.connection.execute(
        "SELECT * FROM runtime_cycles ORDER BY started_at ASC, cycle_id ASC"
    ).fetchall()
    normalized_rows = [dict(row) for row in rows]
    return [
        _hydrate_runtime_cycle_row(row)
        for row in normalized_rows
        if _window_overlaps(
            row.get("started_at"),
            row.get("finished_at") or row.get("started_at"),
            window_started_at,
            window_finished_at,
        )
    ]


def _hydrate_runtime_cycle_row(row: dict[str, object]) -> dict[str, object]:
    hydrated = dict(row)
    hydrated["config"] = _deserialize_json_dict(hydrated.pop("config_json", "{}"))
    hydrated["state_refresh_summary"] = _deserialize_json_dict(
        hydrated.pop("state_refresh_summary_json", "{}")
    )
    hydrated["freshness_counts"] = {
        "first-pass-only": int(hydrated.get("first_pass_only") or 0),
        "fresh-followup": int(hydrated.get("fresh_followup") or 0),
        "aging-followup": int(hydrated.get("aging_followup") or 0),
        "stale-followup": int(hydrated.get("stale_followup") or 0),
    }
    return hydrated


def _normalize_discovery_runs(rows: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        normalized.append(
            {
                "run_id": row.get("run_id"),
                "started_at": row.get("started_at"),
                "finished_at": row.get("finished_at"),
                "status": row.get("status"),
                "root_scope": row.get("root_scope"),
                "page_limit": row.get("page_limit"),
                "max_leaf_categories": row.get("max_leaf_categories"),
                "request_delay_seconds": row.get("request_delay_seconds"),
                "scanned_leaf_catalogs": int(row.get("scanned_leaf_catalogs") or 0),
                "successful_scans": int(row.get("successful_scans") or 0),
                "failed_scans": int(row.get("failed_scans") or 0),
                "raw_listing_hits": int(row.get("raw_listing_hits") or 0),
                "unique_listing_hits": int(row.get("unique_listing_hits") or 0),
                "last_error": row.get("last_error"),
            }
        )
    return sorted(
        normalized,
        key=lambda row: (
            _coerce_datetime(row.get("started_at")) or datetime.min.replace(tzinfo=UTC),
            str(row.get("run_id") or ""),
        ),
    )


def _normalize_catalog_scans(rows: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        normalized.append(
            {
                "run_id": row.get("run_id"),
                "catalog_id": row.get("catalog_id"),
                "catalog_path": row.get("catalog_path"),
                "root_title": row.get("root_title"),
                "page_number": row.get("page_number"),
                "requested_url": row.get("requested_url"),
                "fetched_at": row.get("fetched_at"),
                "response_status": row.get("response_status"),
                "success": bool(row.get("success")),
                "listing_count": int(row.get("listing_count") or 0),
                "api_listing_count": int(row.get("api_listing_count") or 0),
                "accepted_listing_count": int(row.get("accepted_listing_count") or 0),
                "filtered_out_count": int(row.get("filtered_out_count") or 0),
                "accepted_ratio": _coerce_float(row.get("accepted_ratio")),
                "error_message": row.get("error_message"),
            }
        )
    return sorted(
        normalized,
        key=lambda row: (
            _coerce_datetime(row.get("fetched_at")) or datetime.min.replace(tzinfo=UTC),
            str(row.get("run_id") or ""),
            int(row.get("catalog_id") or 0),
            int(row.get("page_number") or 0),
        ),
    )


def _normalize_runtime_cycles(rows: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        state_refresh_summary = row.get("state_refresh_summary")
        if not isinstance(state_refresh_summary, dict):
            state_refresh_summary = _deserialize_json_dict(
                row.get("state_refresh_summary_json") or "{}"
            )
        config = row.get("config")
        if not isinstance(config, dict):
            config = _deserialize_json_dict(row.get("config_json") or "{}")
        normalized.append(
            {
                "cycle_id": row.get("cycle_id"),
                "started_at": row.get("started_at"),
                "finished_at": row.get("finished_at"),
                "mode": row.get("mode"),
                "status": row.get("status"),
                "phase": row.get("phase"),
                "interval_seconds": row.get("interval_seconds"),
                "state_probe_limit": int(row.get("state_probe_limit") or 0),
                "discovery_run_id": row.get("discovery_run_id"),
                "state_probed_count": int(row.get("state_probed_count") or 0),
                "tracked_listings": int(row.get("tracked_listings") or 0),
                "state_refresh_summary": state_refresh_summary,
                "config": config,
                "last_error": row.get("last_error"),
            }
        )
    return sorted(
        normalized,
        key=lambda row: (
            _coerce_datetime(row.get("started_at")) or datetime.min.replace(tzinfo=UTC),
            str(row.get("cycle_id") or ""),
        ),
    )


def _normalize_storage_snapshots(rows: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        normalized.append(
            {
                "captured_at": row.get("captured_at"),
                "listing_count": _coerce_int(
                    row.get("listing_count")
                    if row.get("listing_count") is not None
                    else row.get("tracked_listings")
                ),
                "db_size_bytes": _coerce_int(row.get("db_size_bytes")),
                "artifact_size_bytes": _artifact_bytes(row),
                "storage_bytes": _storage_bytes(row),
            }
        )
    return sorted(
        normalized,
        key=lambda row: (
            _coerce_datetime(row.get("captured_at")) or datetime.min.replace(tzinfo=UTC),
            json.dumps(row, ensure_ascii=False, sort_keys=True),
        ),
    )


def _normalize_resource_snapshots(rows: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        normalized.append(
            {
                "captured_at": row.get("captured_at"),
                "cpu_percent": _cpu_percent(row),
                "ram_mb": _ram_mb(row),
            }
        )
    return sorted(
        normalized,
        key=lambda row: (
            _coerce_datetime(row.get("captured_at")) or datetime.min.replace(tzinfo=UTC),
            json.dumps(row, ensure_ascii=False, sort_keys=True),
        ),
    )


def _catalog_scan_challenge(row: dict[str, object]) -> bool:
    response_status = _coerce_int(row.get("response_status"))
    if response_status in {403, 429}:
        return True
    error_message = _as_text(row.get("error_message"))
    if not error_message:
        return False
    lowered = error_message.casefold()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


def _artifact_bytes(row: dict[str, object]) -> int | None:
    for key in (
        "artifact_size_bytes",
        "file_size_bytes",
        "auxiliary_size_bytes",
        "extra_size_bytes",
    ):
        value = _coerce_int(row.get(key))
        if value is not None:
            return value
    return None


def _storage_bytes(row: dict[str, object]) -> int | None:
    direct_total = _coerce_int(
        row.get("storage_bytes")
        if row.get("storage_bytes") is not None
        else row.get("total_size_bytes")
    )
    if direct_total is not None:
        return direct_total

    db_bytes = _coerce_int(row.get("db_size_bytes"))
    artifact_bytes = _artifact_bytes(row)
    if db_bytes is None and artifact_bytes is None:
        return None
    return int((db_bytes or 0) + (artifact_bytes or 0))


def _cpu_percent(row: dict[str, object]) -> float | None:
    for key in (
        "cpu_percent",
        "cpu_pct",
        "system_cpu_percent",
        "process_cpu_percent",
    ):
        value = _coerce_float(row.get(key))
        if value is not None:
            return value
    return None


def _ram_mb(row: dict[str, object]) -> float | None:
    for key in ("ram_mb", "rss_mb", "memory_rss_mb", "memory_mb"):
        value = _coerce_float(row.get(key))
        if value is not None:
            return value
    for key in ("ram_bytes", "rss_bytes", "memory_rss_bytes", "memory_bytes"):
        value = _coerce_float(row.get(key))
        if value is not None:
            return value / (1024.0 * 1024.0)
    return None


def _collapse_unique_values(values: Any) -> object:
    unique_values: list[object] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        fingerprint = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique_values.append(value)

    if not unique_values:
        return None
    if len(unique_values) == 1:
        return unique_values[0]
    return unique_values


def _desc_sort_key(value: object) -> tuple[int, float]:
    numeric = _coerce_float(value)
    if numeric is None:
        return (1, 0.0)
    return (0, -numeric)


def _asc_sort_key(value: object) -> tuple[int, float]:
    numeric = _coerce_float(value)
    if numeric is None:
        return (1, 0.0)
    return (0, numeric)


def _timestamp_between(value: object, started_at: str, finished_at: str) -> bool:
    value_dt = _coerce_datetime(value)
    started_dt = _coerce_datetime(started_at)
    finished_dt = _coerce_datetime(finished_at)
    if value_dt is None or started_dt is None or finished_dt is None:
        return False
    return started_dt <= value_dt <= finished_dt


def _window_overlaps(
    started_at: object,
    finished_at: object,
    window_started_at: str,
    window_finished_at: str,
) -> bool:
    started_dt = _coerce_datetime(started_at)
    finished_dt = _coerce_datetime(finished_at)
    window_started_dt = _coerce_datetime(window_started_at)
    window_finished_dt = _coerce_datetime(window_finished_at)
    if (
        started_dt is None
        or finished_dt is None
        or window_started_dt is None
        or window_finished_dt is None
    ):
        return False
    return started_dt <= window_finished_dt and finished_dt >= window_started_dt


def _deserialize_json_dict(value: object) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _subtract_ints(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left - right


def _divide(numerator: int | float, denominator: int | float | None) -> float | None:
    if denominator in {None, 0}:
        return None
    return round(float(numerator) / float(denominator), 4)


def _hours_between(started_at: str | None, finished_at: str | None) -> float | None:
    start_dt = _coerce_datetime(started_at)
    end_dt = _coerce_datetime(finished_at)
    if start_dt is None or end_dt is None:
        return None
    return max((end_dt - start_dt).total_seconds(), 0.0) / 3600.0


def _first_timestamp(values: list[object]) -> str | None:
    timestamps = [
        dt.replace(microsecond=0).isoformat()
        for value in values
        if (dt := _coerce_datetime(value)) is not None
    ]
    return None if not timestamps else min(timestamps)


def _last_timestamp(values: list[object]) -> str | None:
    timestamps = [
        dt.replace(microsecond=0).isoformat()
        for value in values
        if (dt := _coerce_datetime(value)) is not None
    ]
    return None if not timestamps else max(timestamps)


def _coerce_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _coerce_datetime(value: object) -> datetime | None:
    text = _as_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _coerce_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _timestamp_slug(value: str) -> str:
    return value.replace(":", "").replace("+00:00", "Z")


def _format_number(value: object, digits: int) -> str:
    numeric = _coerce_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:.{digits}f}"
