from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any

from vinted_radar.db_health import inspect_sqlite_database
from vinted_radar.repository import RadarRepository


def build_long_run_audit_report(
    db_path: str | Path,
    *,
    hours: float = 12.0,
    now: str | None = None,
    include_integrity_check: bool = False,
    issue_limit: int = 5,
    revisit_limit: int = 10,
) -> dict[str, object]:
    if hours <= 0:
        raise ValueError("hours must be greater than 0")

    bounded_issue_limit = max(int(issue_limit), 1)
    bounded_revisit_limit = max(int(revisit_limit), 1)
    generated_at_dt = _coerce_now(now)
    generated_at = generated_at_dt.replace(microsecond=0).isoformat()
    window_started_at = (generated_at_dt - timedelta(hours=float(hours))).replace(microsecond=0).isoformat()
    db_path = Path(db_path)
    db_health = inspect_sqlite_database(
        db_path,
        include_integrity_check=include_integrity_check,
        probe_tables=True,
    )

    report: dict[str, object] = {
        "generated_at": generated_at,
        "window_hours": round(float(hours), 2),
        "window_started_at": window_started_at,
        "window_finished_at": generated_at,
        "db": {
            "path": str(db_path),
            "health": db_health,
        },
        "runtime": _empty_runtime_section(),
        "discovery": _empty_discovery_section(),
        "acquisition": _empty_acquisition_section(),
        "freshness": {
            "generated_at": generated_at,
            "overall": {
                "tracked_listings": 0,
                "first-pass-only": 0,
                "fresh-followup": 0,
                "aging-followup": 0,
                "stale-followup": 0,
            },
            "by_root": [],
        },
        "revisit": {
            "top_candidates": [],
        },
        "findings": [],
        "recommendations": [],
        "verdict": {
            "status": "critical" if not db_health.get("healthy") else "unknown",
            "summary": "Database health failed; the audit cannot trust this snapshot." if not db_health.get("healthy") else "Audit not computed yet.",
        },
    }

    if not db_health.get("healthy"):
        report["findings"] = [
            "Database health is not clean; do not trust runtime, coverage, or dashboard conclusions until the snapshot is healthy."
        ]
        report["recommendations"] = [
            "Re-sync the VPS database through scripts/sync_db_safe.py with --integrity, then re-run the audit on the promoted healthy copy.",
        ]
        return report

    try:
        with RadarRepository(db_path) as repository:
            runtime_cycles = _load_runtime_cycles(repository, window_started_at)
            discovery_runs = _load_discovery_runs(repository, window_started_at)
            runtime_status = repository.runtime_status(limit=max(bounded_issue_limit, 8), now=generated_at)
            freshness = repository.freshness_summary(now=generated_at)
            revisit_candidates = repository.revisit_candidates(limit=bounded_revisit_limit, now=generated_at)

            runtime_section = _summarize_runtime(runtime_cycles, runtime_status, issue_limit=bounded_issue_limit)
            discovery_section = _summarize_discovery(
                repository,
                discovery_runs=discovery_runs,
                window_started_at=window_started_at,
                issue_limit=bounded_issue_limit,
            )
            acquisition_section = _summarize_acquisition(
                repository,
                runtime_cycles=runtime_cycles,
                runtime_status=runtime_status,
                issue_limit=bounded_issue_limit,
            )
            revisit_section = {
                "top_candidates": [_sanitize_revisit_candidate(item) for item in revisit_candidates],
            }
    except sqlite3.Error as exc:
        report["findings"] = [f"Audit queries failed: {type(exc).__name__}: {exc}"]
        report["recommendations"] = [
            "Run db-health --integrity and inspect the snapshot before trusting long-run analysis.",
        ]
        report["verdict"] = {
            "status": "critical",
            "summary": f"Audit queries failed before the runtime window could be summarized: {type(exc).__name__}: {exc}",
        }
        return report

    findings = _build_findings(runtime_section, discovery_section, acquisition_section, freshness)
    recommendations = _build_recommendations(runtime_section, discovery_section, acquisition_section, freshness)
    verdict = _build_verdict(db_health, runtime_section, discovery_section, acquisition_section, freshness, findings)

    report.update(
        {
            "runtime": runtime_section,
            "discovery": discovery_section,
            "acquisition": acquisition_section,
            "freshness": freshness,
            "revisit": revisit_section,
            "findings": findings,
            "recommendations": recommendations,
            "verdict": verdict,
        }
    )
    return report


def render_long_run_audit_markdown(report: dict[str, object]) -> str:
    db = dict(report.get("db") or {})
    db_health = dict(db.get("health") or {})
    verdict = dict(report.get("verdict") or {})
    runtime = dict(report.get("runtime") or {})
    discovery = dict(report.get("discovery") or {})
    acquisition = dict(report.get("acquisition") or {})
    freshness = dict(report.get("freshness") or {})
    freshness_overall = dict(freshness.get("overall") or {})
    probe_totals = dict(acquisition.get("probe_totals") or {})

    lines = [
        f"# Long-run audit — {report.get('window_hours')}h",
        "",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Window start: `{report.get('window_started_at')}`",
        f"- Window end: `{report.get('window_finished_at')}`",
        f"- Database: `{db.get('path')}`",
        "",
        "## Verdict",
        "",
        f"- Status: **{verdict.get('status', 'unknown')}**",
        f"- Summary: {verdict.get('summary', 'n/a')}",
        "",
        "## Database",
        "",
        f"- Healthy: `{bool(db_health.get('healthy'))}`",
        f"- Size bytes: `{db_health.get('size_bytes')}`",
        "",
        "## Runtime",
        "",
        f"- Cycles in window: `{runtime.get('cycle_count', 0)}`",
        f"- Completed / failed / interrupted: `{runtime.get('completed_cycles', 0)}` / `{runtime.get('failed_cycles', 0)}` / `{runtime.get('interrupted_cycles', 0)}`",
        f"- Success rate: `{runtime.get('success_rate')}`",
        f"- Average cycle seconds: `{runtime.get('average_cycle_seconds')}`",
        "",
        "## Discovery",
        "",
        f"- Runs in window: `{discovery.get('run_count', 0)}`",
        f"- Unique leaf catalogs scanned: `{discovery.get('unique_leaf_catalogs_scanned', 0)}` / `{discovery.get('total_leaf_catalogs_known', 0)}`",
        f"- Successful / failed scans: `{discovery.get('sum_successful_scans', 0)}` / `{discovery.get('sum_failed_scans', 0)}`",
        f"- Unique listing hits total: `{discovery.get('sum_unique_listing_hits', 0)}`",
        f"- Narrow coverage suspected: `{bool(discovery.get('narrow_coverage_suspected'))}`",
        "",
        "## Acquisition",
        "",
        f"- Latest status: `{acquisition.get('latest_status', 'unknown')}`",
        f"- Window statuses: `{json.dumps(acquisition.get('window_cycle_status_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- Direct / inconclusive / degraded probes: `{probe_totals.get('direct_signal_count', 0)}` / `{probe_totals.get('inconclusive_probe_count', 0)}` / `{probe_totals.get('degraded_probe_count', 0)}`",
        f"- Anti-bot / HTTP / transport: `{probe_totals.get('anti_bot_challenge_count', 0)}` / `{probe_totals.get('http_error_count', 0)}` / `{probe_totals.get('transport_error_count', 0)}`",
        "",
        "## Freshness snapshot",
        "",
        f"- Tracked listings: `{freshness_overall.get('tracked_listings', 0)}`",
        f"- first-pass-only: `{freshness_overall.get('first-pass-only', 0)}`",
        f"- fresh-followup: `{freshness_overall.get('fresh-followup', 0)}`",
        f"- aging-followup: `{freshness_overall.get('aging-followup', 0)}`",
        f"- stale-followup: `{freshness_overall.get('stale-followup', 0)}`",
        "",
        "## Findings",
        "",
    ]
    findings = list(report.get("findings") or [])
    if findings:
        lines.extend(f"- {item}" for item in findings)
    else:
        lines.append("- No notable findings recorded.")

    lines.extend(["", "## Recommendations", ""])
    recommendations = list(report.get("recommendations") or [])
    if recommendations:
        lines.extend(f"- {item}" for item in recommendations)
    else:
        lines.append("- No recommendations recorded.")

    revisit = dict(report.get("revisit") or {})
    top_candidates = list(revisit.get("top_candidates") or [])
    if top_candidates:
        lines.extend(["", "## Revisit candidates", ""])
        for item in top_candidates:
            lines.append(
                "- `{listing_id}` · score `{priority_score}` · `{freshness_bucket}` · obs `{observation_count}` · age `{last_seen_age_hours}h` · {title}".format(
                    listing_id=item.get("listing_id"),
                    priority_score=item.get("priority_score"),
                    freshness_bucket=item.get("freshness_bucket"),
                    observation_count=item.get("observation_count"),
                    last_seen_age_hours=item.get("last_seen_age_hours"),
                    title=item.get("title") or "(untitled)",
                )
            )

    return "\n".join(lines) + "\n"


def _empty_runtime_section() -> dict[str, object]:
    return {
        "cycle_count": 0,
        "completed_cycles": 0,
        "failed_cycles": 0,
        "interrupted_cycles": 0,
        "running_cycles": 0,
        "success_rate": None,
        "average_cycle_seconds": None,
        "latest_window_cycle": None,
        "latest_controller_status": None,
        "latest_controller_phase": None,
        "failure_phases": [],
        "recent_failures": [],
    }


def _empty_discovery_section() -> dict[str, object]:
    return {
        "run_count": 0,
        "total_leaf_catalogs_known": 0,
        "unique_leaf_catalogs_scanned": 0,
        "leaf_catalog_scan_coverage_ratio": None,
        "repeated_scan_factor": None,
        "sum_scanned_leaf_catalogs": 0,
        "sum_successful_scans": 0,
        "sum_failed_scans": 0,
        "sum_unique_listing_hits": 0,
        "average_unique_listing_hits_per_run": None,
        "runs_with_max_leaf_categories": 0,
        "narrow_coverage_suspected": False,
        "narrow_coverage_reasons": [],
        "top_failing_catalogs": [],
    }


def _empty_acquisition_section() -> dict[str, object]:
    return {
        "latest_status": "unknown",
        "latest_reasons": [],
        "window_cycle_status_counts": {"healthy": 0, "partial": 0, "degraded": 0, "unknown": 0},
        "probe_totals": {
            "direct_signal_count": 0,
            "inconclusive_probe_count": 0,
            "degraded_probe_count": 0,
            "anti_bot_challenge_count": 0,
            "http_error_count": 0,
            "transport_error_count": 0,
        },
        "top_probe_reasons": [],
        "recent_scan_failure_count": 0,
        "recent_scan_failures": [],
        "degraded_listing_examples": [],
    }


def _summarize_runtime(
    runtime_cycles: list[dict[str, object]],
    runtime_status: dict[str, object],
    *,
    issue_limit: int,
) -> dict[str, object]:
    section = _empty_runtime_section()
    if not runtime_cycles:
        section["latest_controller_status"] = runtime_status.get("status")
        section["latest_controller_phase"] = runtime_status.get("phase")
        return section

    status_counts = Counter(str(item.get("status") or "unknown") for item in runtime_cycles)
    durations = [
        _seconds_between(str(item.get("started_at")), str(item.get("finished_at")))
        for item in runtime_cycles
        if item.get("started_at") and item.get("finished_at")
    ]
    failure_phases = Counter(
        f"{item.get('status')}:{item.get('phase')}"
        for item in runtime_cycles
        if str(item.get("status") or "") in {"failed", "interrupted"}
    )
    terminal_count = sum(status_counts.get(name, 0) for name in ("completed", "failed", "interrupted"))
    recent_failures = [
        {
            "cycle_id": item.get("cycle_id"),
            "status": item.get("status"),
            "phase": item.get("phase"),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "last_error": item.get("last_error"),
        }
        for item in runtime_cycles
        if str(item.get("status") or "") in {"failed", "interrupted"}
    ][-issue_limit:]

    section.update(
        {
            "cycle_count": len(runtime_cycles),
            "completed_cycles": int(status_counts.get("completed", 0)),
            "failed_cycles": int(status_counts.get("failed", 0)),
            "interrupted_cycles": int(status_counts.get("interrupted", 0)),
            "running_cycles": int(status_counts.get("running", 0)),
            "success_rate": None if terminal_count == 0 else round(int(status_counts.get("completed", 0)) / terminal_count, 3),
            "average_cycle_seconds": None if not durations else round(sum(durations) / len(durations), 2),
            "latest_window_cycle": _runtime_cycle_excerpt(runtime_cycles[-1]),
            "latest_controller_status": runtime_status.get("status"),
            "latest_controller_phase": runtime_status.get("phase"),
            "failure_phases": [
                {"label": label, "count": count}
                for label, count in failure_phases.most_common(issue_limit)
            ],
            "recent_failures": recent_failures,
        }
    )
    return section


def _summarize_discovery(
    repository: RadarRepository,
    *,
    discovery_runs: list[dict[str, object]],
    window_started_at: str,
    issue_limit: int,
) -> dict[str, object]:
    section = _empty_discovery_section()
    connection = repository.connection
    total_leaf_catalogs_known = int(
        (connection.execute("SELECT COUNT(*) AS count FROM catalogs WHERE is_leaf = 1").fetchone() or {"count": 0})["count"]
    )
    unique_leaf_catalogs_scanned = int(
        (
            connection.execute(
                """
                SELECT COUNT(DISTINCT catalog_scans.catalog_id) AS count
                FROM catalog_scans
                JOIN discovery_runs ON discovery_runs.run_id = catalog_scans.run_id
                WHERE discovery_runs.started_at >= ?
                """,
                (window_started_at,),
            ).fetchone()
            or {"count": 0}
        )["count"]
    )
    top_failing_catalogs = [
        dict(row)
        for row in connection.execute(
            """
            SELECT
                catalogs.path AS catalog_path,
                COUNT(*) AS failure_count,
                MAX(catalog_scans.fetched_at) AS latest_failure_at,
                SUM(CASE WHEN catalog_scans.response_status = 403 THEN 1 ELSE 0 END) AS http_403_count,
                MIN(COALESCE(catalog_scans.error_message, 'HTTP ' || COALESCE(catalog_scans.response_status, 'unknown'))) AS sample_error
            FROM catalog_scans
            JOIN catalogs ON catalogs.catalog_id = catalog_scans.catalog_id
            JOIN discovery_runs ON discovery_runs.run_id = catalog_scans.run_id
            WHERE discovery_runs.started_at >= ? AND catalog_scans.success = 0
            GROUP BY catalogs.path
            ORDER BY failure_count DESC, latest_failure_at DESC, catalogs.path ASC
            LIMIT ?
            """,
            (window_started_at, issue_limit),
        )
    ]

    run_count = len(discovery_runs)
    sum_scanned_leaf_catalogs = sum(int(item.get("scanned_leaf_catalogs") or 0) for item in discovery_runs)
    sum_successful_scans = sum(int(item.get("successful_scans") or 0) for item in discovery_runs)
    sum_failed_scans = sum(int(item.get("failed_scans") or 0) for item in discovery_runs)
    sum_unique_listing_hits = sum(int(item.get("unique_listing_hits") or 0) for item in discovery_runs)
    runs_with_max_leaf_categories = sum(1 for item in discovery_runs if item.get("max_leaf_categories") is not None)
    coverage_ratio = None if total_leaf_catalogs_known == 0 else round(unique_leaf_catalogs_scanned / total_leaf_catalogs_known, 3)
    repeated_scan_factor = None if unique_leaf_catalogs_scanned == 0 else round(sum_scanned_leaf_catalogs / unique_leaf_catalogs_scanned, 3)
    narrow_coverage_suspected, narrow_reasons = _detect_narrow_coverage(
        discovery_runs=discovery_runs,
        total_leaf_catalogs_known=total_leaf_catalogs_known,
        unique_leaf_catalogs_scanned=unique_leaf_catalogs_scanned,
        sum_scanned_leaf_catalogs=sum_scanned_leaf_catalogs,
    )

    section.update(
        {
            "run_count": run_count,
            "total_leaf_catalogs_known": total_leaf_catalogs_known,
            "unique_leaf_catalogs_scanned": unique_leaf_catalogs_scanned,
            "leaf_catalog_scan_coverage_ratio": coverage_ratio,
            "repeated_scan_factor": repeated_scan_factor,
            "sum_scanned_leaf_catalogs": sum_scanned_leaf_catalogs,
            "sum_successful_scans": sum_successful_scans,
            "sum_failed_scans": sum_failed_scans,
            "sum_unique_listing_hits": sum_unique_listing_hits,
            "average_unique_listing_hits_per_run": None if run_count == 0 else round(sum_unique_listing_hits / run_count, 2),
            "runs_with_max_leaf_categories": runs_with_max_leaf_categories,
            "narrow_coverage_suspected": narrow_coverage_suspected,
            "narrow_coverage_reasons": narrow_reasons,
            "top_failing_catalogs": top_failing_catalogs,
        }
    )
    return section


def _summarize_acquisition(
    repository: RadarRepository,
    *,
    runtime_cycles: list[dict[str, object]],
    runtime_status: dict[str, object],
    issue_limit: int,
) -> dict[str, object]:
    section = _empty_acquisition_section()
    latest_contract = dict(runtime_status.get("acquisition") or {})
    window_status_counts = Counter()
    probe_totals = Counter()
    reason_counts = Counter()
    degraded_listing_counts = Counter()

    for item in runtime_cycles:
        summary = dict(item.get("state_refresh_summary") or {})
        status = str(summary.get("status") or "unknown")
        window_status_counts[status] += 1
        for key in (
            "direct_signal_count",
            "inconclusive_probe_count",
            "degraded_probe_count",
            "anti_bot_challenge_count",
            "http_error_count",
            "transport_error_count",
        ):
            probe_totals[key] += int(summary.get(key) or 0)
        for reason, count in dict(summary.get("reason_counts") or {}).items():
            reason_counts[str(reason)] += int(count or 0)
        for listing_id in list(summary.get("degraded_listing_ids") or []):
            try:
                degraded_listing_counts[int(listing_id)] += 1
            except (TypeError, ValueError):
                continue

    section.update(
        {
            "latest_status": latest_contract.get("status") or "unknown",
            "latest_reasons": list(latest_contract.get("reasons") or []),
            "window_cycle_status_counts": {
                "healthy": int(window_status_counts.get("healthy", 0)),
                "partial": int(window_status_counts.get("partial", 0)),
                "degraded": int(window_status_counts.get("degraded", 0)),
                "unknown": int(window_status_counts.get("unknown", 0)),
            },
            "probe_totals": {
                "direct_signal_count": int(probe_totals.get("direct_signal_count", 0)),
                "inconclusive_probe_count": int(probe_totals.get("inconclusive_probe_count", 0)),
                "degraded_probe_count": int(probe_totals.get("degraded_probe_count", 0)),
                "anti_bot_challenge_count": int(probe_totals.get("anti_bot_challenge_count", 0)),
                "http_error_count": int(probe_totals.get("http_error_count", 0)),
                "transport_error_count": int(probe_totals.get("transport_error_count", 0)),
            },
            "top_probe_reasons": [
                {"reason": reason, "count": count}
                for reason, count in reason_counts.most_common(issue_limit)
            ],
            "recent_scan_failure_count": int(latest_contract.get("recent_scan_failure_count") or 0),
            "recent_scan_failures": list(latest_contract.get("recent_scan_failures") or [])[:issue_limit],
            "degraded_listing_examples": _load_listing_examples(repository, degraded_listing_counts, issue_limit),
        }
    )
    return section


def _build_findings(
    runtime: dict[str, object],
    discovery: dict[str, object],
    acquisition: dict[str, object],
    freshness: dict[str, object],
) -> list[str]:
    findings: list[str] = []
    cycle_count = int(runtime.get("cycle_count") or 0)
    failed_cycles = int(runtime.get("failed_cycles") or 0)
    interrupted_cycles = int(runtime.get("interrupted_cycles") or 0)
    if cycle_count == 0:
        findings.append("No runtime cycles overlap the requested audit window.")
    elif failed_cycles or interrupted_cycles:
        findings.append(
            f"{failed_cycles} failed cycle(s) and {interrupted_cycles} interrupted cycle(s) overlapped the audit window."
        )

    if bool(discovery.get("narrow_coverage_suspected")):
        findings.extend(str(item) for item in list(discovery.get("narrow_coverage_reasons") or []))

    failed_scans = int(discovery.get("sum_failed_scans") or 0)
    if failed_scans:
        findings.append(f"Discovery recorded {failed_scans} failed catalog scan(s) in the audit window.")

    window_status_counts = dict(acquisition.get("window_cycle_status_counts") or {})
    degraded_cycles = int(window_status_counts.get("degraded") or 0)
    partial_cycles = int(window_status_counts.get("partial") or 0)
    probe_totals = dict(acquisition.get("probe_totals") or {})
    if degraded_cycles:
        findings.append(
            f"Acquisition degraded on {degraded_cycles} cycle(s), including {int(probe_totals.get('anti_bot_challenge_count') or 0)} anti-bot challenge hit(s)."
        )
    elif partial_cycles:
        findings.append(
            f"Acquisition stayed partial on {partial_cycles} cycle(s); history remained safer than fresh page signals for part of the window."
        )

    overall = dict(freshness.get("overall") or {})
    tracked = int(overall.get("tracked_listings") or 0)
    if tracked:
        first_pass_ratio = int(overall.get("first-pass-only") or 0) / tracked
        stale_ratio = int(overall.get("stale-followup") or 0) / tracked
        if first_pass_ratio >= 0.7:
            findings.append(
                f"Freshness is still first-pass-heavy: {int(overall.get('first-pass-only') or 0)} / {tracked} tracked listings have only been seen once."
            )
        if stale_ratio >= 0.2:
            findings.append(
                f"Follow-up backlog is visible: {int(overall.get('stale-followup') or 0)} / {tracked} tracked listings are already stale."
            )

    return findings


def _build_recommendations(
    runtime: dict[str, object],
    discovery: dict[str, object],
    acquisition: dict[str, object],
    freshness: dict[str, object],
) -> list[str]:
    recommendations: list[str] = []

    cycle_count = int(runtime.get("cycle_count") or 0)
    if cycle_count == 0:
        recommendations.append("Verify that the requested audit window matches the VPS run timing before drawing conclusions from an empty slice.")

    if int(runtime.get("failed_cycles") or 0) > 0:
        recommendations.append("Inspect recent runtime failures and their phases before the next long run; repeated discovery/state-refresh failures are operational debt, not noise.")

    if bool(discovery.get("narrow_coverage_suspected")):
        recommendations.append("Do not treat this window as broad market proof; either remove --max-leaf-categories or add explicit leaf-catalog rotation for credibility runs.")

    if int(discovery.get("sum_failed_scans") or 0) > 0:
        recommendations.append("Review the top failing catalogs and compare their HTTP/error patterns; repeated catalog failures deserve targeted mitigation, not just a longer run.")

    probe_totals = dict(acquisition.get("probe_totals") or {})
    if int(probe_totals.get("anti_bot_challenge_count") or 0) > 0:
        recommendations.append("Acquisition hit anti-bot pressure; compare proxy pool, request cadence, and state_refresh_limit before trusting longer unattended runs.")
    elif int(probe_totals.get("degraded_probe_count") or 0) > 0:
        recommendations.append("Probe degradation is visible; sample degraded listings with state/history before trusting state-heavy conclusions.")
    elif int(probe_totals.get("inconclusive_probe_count") or 0) > 0:
        recommendations.append("Some probes stayed inconclusive; treat history as the safer signal and inspect parsing quality on a sample of affected listings.")

    overall = dict(freshness.get("overall") or {})
    tracked = int(overall.get("tracked_listings") or 0)
    if tracked:
        if int(overall.get("first-pass-only") or 0) / tracked >= 0.7:
            recommendations.append("Freshness is still dominated by first-pass sightings; either narrow scope or increase revisit depth if the goal is credibility rather than raw intake.")
        if int(overall.get("stale-followup") or 0) / tracked >= 0.2:
            recommendations.append("Prioritize revisit-plan candidates before widening scope again; stale follow-up backlog means the corpus is getting older than the revisit budget.")

    if not recommendations:
        recommendations.append("No obvious corrective action surfaced from the audit window; keep validating with verify_vps_serving.py against the real public entrypoint.")
    return recommendations


def _build_verdict(
    db_health: dict[str, object],
    runtime: dict[str, object],
    discovery: dict[str, object],
    acquisition: dict[str, object],
    freshness: dict[str, object],
    findings: list[str],
) -> dict[str, object]:
    if not db_health.get("healthy"):
        return {
            "status": "critical",
            "summary": "Database health failed; do not trust the long-run output until a healthy snapshot is promoted.",
        }

    cycle_count = int(runtime.get("cycle_count") or 0)
    if cycle_count == 0:
        return {
            "status": "caution",
            "summary": "The database is readable, but no runtime cycles overlap the requested window, so the audit cannot judge the run itself.",
        }

    score = 0
    score += min(int(runtime.get("failed_cycles") or 0) * 2, 4)
    score += min(int(runtime.get("interrupted_cycles") or 0), 2)
    score += min(int((acquisition.get("window_cycle_status_counts") or {}).get("degraded") or 0) * 2, 4)
    score += min(int((acquisition.get("window_cycle_status_counts") or {}).get("partial") or 0), 2)
    if int(discovery.get("sum_failed_scans") or 0) > 0:
        score += 2
    if bool(discovery.get("narrow_coverage_suspected")):
        score += 2

    overall = dict(freshness.get("overall") or {})
    tracked = int(overall.get("tracked_listings") or 0)
    if tracked:
        if int(overall.get("first-pass-only") or 0) / tracked >= 0.7:
            score += 1
        if int(overall.get("stale-followup") or 0) / tracked >= 0.2:
            score += 1

    if score >= 6:
        status = "degraded"
    elif score >= 3:
        status = "caution"
    else:
        status = "healthy"

    summary_findings = findings[:2]
    if not summary_findings:
        summary = "The run looks operationally healthy across runtime, discovery, acquisition, and freshness surfaces."
    else:
        summary = " ".join(summary_findings)

    return {
        "status": status,
        "summary": summary,
    }


def _load_runtime_cycles(repository: RadarRepository, window_started_at: str) -> list[dict[str, object]]:
    rows = repository.connection.execute(
        """
        SELECT *
        FROM runtime_cycles
        WHERE started_at >= ? OR (finished_at IS NOT NULL AND finished_at >= ?)
        ORDER BY started_at ASC, cycle_id ASC
        """,
        (window_started_at, window_started_at),
    ).fetchall()
    return [_hydrate_runtime_cycle_row(row) for row in rows]


def _load_discovery_runs(repository: RadarRepository, window_started_at: str) -> list[dict[str, object]]:
    rows = repository.connection.execute(
        """
        SELECT *
        FROM discovery_runs
        WHERE started_at >= ? OR (finished_at IS NOT NULL AND finished_at >= ?)
        ORDER BY started_at ASC, run_id ASC
        """,
        (window_started_at, window_started_at),
    ).fetchall()
    return [dict(row) for row in rows]


def _load_listing_examples(
    repository: RadarRepository,
    listing_counts: Counter[int],
    limit: int,
) -> list[dict[str, object]]:
    if not listing_counts:
        return []
    top_ids = [listing_id for listing_id, _ in listing_counts.most_common(limit)]
    placeholders = ", ".join("?" for _ in top_ids)
    rows = repository.connection.execute(
        f"""
        SELECT listing_id, title, canonical_url, brand, last_discovered_at
        FROM listings
        WHERE listing_id IN ({placeholders})
        """,
        top_ids,
    ).fetchall()
    by_id = {int(row["listing_id"]): dict(row) for row in rows}
    examples: list[dict[str, object]] = []
    for listing_id in top_ids:
        payload = by_id.get(listing_id, {"listing_id": listing_id, "title": None, "canonical_url": None, "brand": None, "last_discovered_at": None})
        payload.update({"degraded_probe_count": int(listing_counts[listing_id])})
        examples.append(payload)
    return examples


def _detect_narrow_coverage(
    *,
    discovery_runs: list[dict[str, object]],
    total_leaf_catalogs_known: int,
    unique_leaf_catalogs_scanned: int,
    sum_scanned_leaf_catalogs: int,
) -> tuple[bool, list[str]]:
    if len(discovery_runs) < 2 or unique_leaf_catalogs_scanned == 0:
        return False, []

    reasons: list[str] = []
    max_leaf_values = [int(item["max_leaf_categories"]) for item in discovery_runs if item.get("max_leaf_categories") is not None]
    if max_leaf_values and len(max_leaf_values) == len(discovery_runs):
        window_cap = max(max_leaf_values)
        if unique_leaf_catalogs_scanned <= window_cap and sum_scanned_leaf_catalogs > unique_leaf_catalogs_scanned:
            reasons.append(
                "Every run in the window used max_leaf_categories and the window appears to have revisited the same limited leaf subset repeatedly."
            )

    if total_leaf_catalogs_known > 0:
        coverage_ratio = unique_leaf_catalogs_scanned / total_leaf_catalogs_known
        repeated_scan_factor = sum_scanned_leaf_catalogs / unique_leaf_catalogs_scanned
        if coverage_ratio <= 0.25 and repeated_scan_factor >= 1.5:
            reasons.append(
                "Unique leaf-catalog coverage stayed low relative to the known catalog tree while repeated scans concentrated on the same slice."
            )

    return bool(reasons), reasons


def _sanitize_revisit_candidate(item: dict[str, object]) -> dict[str, object]:
    return {
        "listing_id": item.get("listing_id"),
        "title": item.get("title"),
        "priority_score": item.get("priority_score"),
        "freshness_bucket": item.get("freshness_bucket"),
        "last_seen_age_hours": item.get("last_seen_age_hours"),
        "observation_count": item.get("observation_count"),
        "priority_reasons": list(item.get("priority_reasons") or []),
        "canonical_url": item.get("canonical_url"),
    }


def _runtime_cycle_excerpt(item: dict[str, object]) -> dict[str, object]:
    summary = dict(item.get("state_refresh_summary") or {})
    return {
        "cycle_id": item.get("cycle_id"),
        "status": item.get("status"),
        "phase": item.get("phase"),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "discovery_run_id": item.get("discovery_run_id"),
        "state_probe_limit": item.get("state_probe_limit"),
        "state_probed_count": item.get("state_probed_count"),
        "tracked_listings": item.get("tracked_listings"),
        "freshness_counts": dict(item.get("freshness_counts") or {}),
        "state_refresh_summary": summary,
        "last_error": item.get("last_error"),
    }


def _hydrate_runtime_cycle_row(row: sqlite3.Row) -> dict[str, object]:
    hydrated = dict(row)
    hydrated["config"] = _deserialize_json_dict(hydrated.pop("config_json", "{}"))
    hydrated["state_refresh_summary"] = _deserialize_json_dict(hydrated.pop("state_refresh_summary_json", "{}"))
    hydrated["freshness_counts"] = {
        "first-pass-only": int(hydrated.get("first_pass_only") or 0),
        "fresh-followup": int(hydrated.get("fresh_followup") or 0),
        "aging-followup": int(hydrated.get("aging_followup") or 0),
        "stale-followup": int(hydrated.get("stale_followup") or 0),
    }
    return hydrated


def _deserialize_json_dict(value: object) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _seconds_between(started_at: str, finished_at: str) -> float:
    start_dt = datetime.fromisoformat(started_at)
    end_dt = datetime.fromisoformat(finished_at)
    return round(max((end_dt - start_dt).total_seconds(), 0.0), 3)


def _coerce_now(now: str | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return datetime.fromisoformat(now)
