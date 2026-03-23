from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import typer

from vinted_radar.dashboard import serve_dashboard, start_dashboard_server
from vinted_radar.db_health import inspect_sqlite_database
from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import build_listing_score_detail, build_market_summary, build_rankings, load_listing_scores
from vinted_radar.services.discovery import DiscoveryOptions, build_default_service
from vinted_radar.services.runtime import RadarRuntimeCycleReport, RadarRuntimeOptions, RadarRuntimeService
from vinted_radar.services.state_refresh import build_default_state_refresh_service
from vinted_radar.serving import build_dashboard_urls
from vinted_radar.state_machine import evaluate_listing_state, summarize_state_evaluations

app = typer.Typer(add_completion=False, help="Local-first Vinted Homme/Femme radar CLI.")


@app.command()
def discover(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    page_limit: int = typer.Option(5, "--page-limit", min=1, help="How many catalog pages to fetch per leaf category."),
    max_leaf_categories: int | None = typer.Option(None, "--max-leaf-categories", min=1, help="Limit the number of leaf categories scanned in the run."),
    root_scope: str = typer.Option("both", "--root-scope", help="Which root catalogs to scan: both, women, or men."),
    request_delay: float = typer.Option(3.0, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    concurrency: int = typer.Option(1, "--concurrency", min=1, help="Max requests in flight across all catalogs."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy URL (http://user:pass@host:port). Repeatable for pool."),
) -> None:
    proxies = list(proxy) if proxy else None
    service = build_default_service(db_path=str(db), timeout_seconds=timeout_seconds, request_delay=request_delay, proxies=proxies)
    try:
        report = service.run(
            DiscoveryOptions(
                page_limit=page_limit,
                max_leaf_categories=max_leaf_categories,
                root_scope=root_scope,
                request_delay=request_delay,
                concurrency=concurrency,
            )
        )
    finally:
        service.repository.close()

    typer.echo(f"Run: {report.run_id}")
    typer.echo(f"Seeds synced: {report.total_seed_catalogs} catalogs ({report.total_leaf_catalogs} leaf catalogs)")
    typer.echo(f"Leaf catalogs scanned: {report.scanned_leaf_catalogs}")
    typer.echo(f"Page scans: {report.successful_scans} successful, {report.failed_scans} failed")
    typer.echo(f"Listings discovered: {report.raw_listing_hits} sightings, {report.unique_listing_hits} unique IDs")
    typer.echo(f"Database: {db}")


@app.command("batch")
def batch_run(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    page_limit: int = typer.Option(5, "--page-limit", min=1, help="How many catalog pages to fetch per leaf category."),
    max_leaf_categories: int | None = typer.Option(None, "--max-leaf-categories", min=1, help="Limit the number of leaf categories scanned in the batch cycle."),
    root_scope: str = typer.Option("both", "--root-scope", help="Which root catalogs to scan: both, women, or men."),
    min_price: float = typer.Option(30.0, "--min-price", min=0.0, help="Minimum listing price in euros."),
    target_catalogs: list[int] | None = typer.Option(None, "--target-catalogs", help="Catalog ID to scan. Repeatable."),
    target_brands: list[str] | None = typer.Option(None, "--target-brands", help="Brand name to allow. Repeatable."),
    state_refresh_limit: int = typer.Option(10, "--state-refresh-limit", min=1, help="How many listing item pages to probe after discovery."),
    request_delay: float = typer.Option(3.0, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    concurrency: int = typer.Option(1, "--concurrency", min=1, help="Max requests in flight across all catalogs."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy URL (http://user:pass@host:port). Repeatable for pool."),
    dashboard: bool = typer.Option(False, "--dashboard/--no-dashboard", help="Serve the local dashboard after the batch cycle completes."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind the local dashboard server when --dashboard is enabled."),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Port to bind the local dashboard server when --dashboard is enabled."),
    base_path: str = typer.Option("", "--base-path", help="Optional route prefix when the dashboard is mounted behind a reverse proxy (example: /radar)."),
    public_base_url: str | None = typer.Option(None, "--public-base-url", help="Optional external base URL prefix advertised to operators and used for absolute dashboard links (example: https://radar.example.com/radar)."),
) -> None:
    proxies = tuple(proxy) if proxy else ()
    runtime_service = RadarRuntimeService(db)
    options = _build_runtime_options(
        page_limit=page_limit,
        max_leaf_categories=max_leaf_categories,
        root_scope=root_scope,
        min_price=min_price,
        target_catalogs=target_catalogs,
        target_brands=target_brands,
        state_refresh_limit=state_refresh_limit,
        request_delay=request_delay,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
        proxies=proxies,
    )
    try:
        report = runtime_service.run_cycle(options, mode="batch")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Batch cycle failed: {type(exc).__name__}: {exc}", err=True)
        typer.echo(f"Inspect runtime status with: python -m vinted_radar.cli runtime-status --db {db}", err=True)
        raise typer.Exit(code=1) from exc

    _render_runtime_cycle_report(report, db=db)
    if not dashboard:
        return

    _echo_dashboard_urls(host=host, port=port, base_path=base_path, public_base_url=public_base_url)
    try:
        serve_dashboard(db_path=db, host=host, port=port, base_path=base_path, public_base_url=public_base_url)
    except KeyboardInterrupt:
        typer.echo("Dashboard server stopped.")


@app.command("continuous")
def continuous_run(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    page_limit: int = typer.Option(5, "--page-limit", min=1, help="How many catalog pages to fetch per leaf category."),
    max_leaf_categories: int | None = typer.Option(None, "--max-leaf-categories", min=1, help="Limit the number of leaf categories scanned in each cycle."),
    root_scope: str = typer.Option("both", "--root-scope", help="Which root catalogs to scan: both, women, or men."),
    min_price: float = typer.Option(30.0, "--min-price", min=0.0, help="Minimum listing price in euros."),
    target_catalogs: list[int] | None = typer.Option(None, "--target-catalogs", help="Catalog ID to scan. Repeatable."),
    target_brands: list[str] | None = typer.Option(None, "--target-brands", help="Brand name to allow. Repeatable."),
    state_refresh_limit: int = typer.Option(10, "--state-refresh-limit", min=1, help="How many listing item pages to probe after each discovery cycle."),
    interval_seconds: float = typer.Option(1800.0, "--interval-seconds", min=0.1, help="Delay between completed cycles in seconds."),
    max_cycles: int | None = typer.Option(None, "--max-cycles", min=1, help="Optional cycle cap for smoke runs or tests."),
    request_delay: float = typer.Option(3.0, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    concurrency: int = typer.Option(1, "--concurrency", min=1, help="Max requests in flight across all catalogs."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy URL (http://user:pass@host:port). Repeatable for pool."),
    dashboard: bool = typer.Option(False, "--dashboard/--no-dashboard", help="Serve the local dashboard alongside the continuous loop."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind the local dashboard server when --dashboard is enabled."),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Port to bind the local dashboard server when --dashboard is enabled."),
    base_path: str = typer.Option("", "--base-path", help="Optional route prefix when the dashboard is mounted behind a reverse proxy (example: /radar)."),
    public_base_url: str | None = typer.Option(None, "--public-base-url", help="Optional external base URL prefix advertised to operators and used for absolute dashboard links (example: https://radar.example.com/radar)."),
) -> None:
    proxies = tuple(proxy) if proxy else ()
    runtime_service = RadarRuntimeService(db)
    options = _build_runtime_options(
        page_limit=page_limit,
        max_leaf_categories=max_leaf_categories,
        root_scope=root_scope,
        min_price=min_price,
        target_catalogs=target_catalogs,
        target_brands=target_brands,
        state_refresh_limit=state_refresh_limit,
        request_delay=request_delay,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
        proxies=proxies,
    )
    dashboard_server = None
    if dashboard:
        dashboard_server = start_dashboard_server(
            db_path=db,
            host=host,
            port=port,
            base_path=base_path,
            public_base_url=public_base_url,
        )
        _echo_dashboard_urls(host=host, port=port, base_path=base_path, public_base_url=public_base_url)

    typer.echo(f"Database: {db}")
    typer.echo(f"Continuous interval: {interval_seconds:.1f}s")
    if max_cycles is not None:
        typer.echo(f"Cycle cap: {max_cycles}")
    try:
        runtime_service.run_continuous(
            options,
            interval_seconds=interval_seconds,
            max_cycles=max_cycles,
            continue_on_error=True,
            on_cycle_complete=lambda report: _render_runtime_cycle_report(report, db=db),
        )
    except KeyboardInterrupt:
        typer.echo("Continuous radar stopped.")
    finally:
        if dashboard_server is not None:
            dashboard_server.stop()


@app.command("runtime-pause")
def runtime_pause(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
) -> None:
    with RadarRepository(db) as repository:
        controller = repository.request_runtime_pause()

    typer.echo(f"Database: {db}")
    typer.echo(f"Current runtime status: {controller['status']} (phase {controller['phase']})")
    if controller.get("requested_action") == "pause":
        typer.echo("Pause requested. The running cycle will stop after it finishes and then switch to paused.")
    else:
        typer.echo("Runtime is now paused in the persisted controller state.")


@app.command("runtime-resume")
def runtime_resume(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
) -> None:
    with RadarRepository(db) as repository:
        controller = repository.request_runtime_resume()

    typer.echo(f"Database: {db}")
    typer.echo(f"Current runtime status: {controller['status']} (phase {controller['phase']})")
    if controller.get("requested_action") == "resume":
        typer.echo("Resume requested. A paused controller will re-enter the schedule on the next heartbeat.")
    elif controller.get("status") == "scheduled":
        typer.echo(f"Runtime resumed. Next cycle window: {controller.get('next_resume_at') or 'now'}")
    else:
        typer.echo("No paused runtime was waiting; any pending pause request was cleared.")


@app.command("runtime-status")
def runtime_status(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    limit: int = typer.Option(5, "--limit", min=1, help="How many recent runtime cycles to show."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic runtime timing output."),
) -> None:
    with RadarRepository(db) as repository:
        status = repository.runtime_status(limit=limit, now=now)

    if status["latest_cycle"] is None and status.get("controller") is None:
        typer.echo(f"Database: {db}")
        typer.echo("No runtime cycles recorded yet.")
        return

    if output_format == "json":
        typer.echo(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    latest = status.get("latest_cycle") or {}
    controller = status.get("controller") or {}
    totals = status["totals"]
    typer.echo(f"Database: {db}")
    typer.echo(f"Runtime now: {status.get('status') or 'n/a'} (phase {status.get('phase') or 'n/a'})")
    typer.echo(f"Controller mode: {status.get('mode') or latest.get('mode') or 'n/a'}")
    typer.echo(f"Updated at: {status.get('updated_at') or 'n/a'}")
    heartbeat = status.get("heartbeat") or {}
    if heartbeat:
        typer.echo(
            "Heartbeat: age {age} / stale after {threshold} / stale {stale}".format(
                age=_format_duration_seconds(heartbeat.get("age_seconds")),
                threshold=_format_duration_seconds(heartbeat.get("stale_after_seconds")),
                stale="yes" if heartbeat.get("is_stale") else "no",
            )
        )
    if status.get("paused_at"):
        typer.echo(
            f"Paused since: {status['paused_at']} ({_format_duration_seconds(status.get('elapsed_pause_seconds'))})"
        )
    if status.get("next_resume_at"):
        typer.echo(
            f"Next resume: {status['next_resume_at']} ({_format_duration_seconds(status.get('next_resume_in_seconds'))} remaining)"
        )
    if status.get("requested_action") and status.get("requested_action") != "none":
        typer.echo(f"Pending operator action: {status['requested_action']} @ {status.get('requested_at') or 'n/a'}")
    if status.get("last_error"):
        typer.echo(f"Controller last error: {status['last_error']}")
        if status.get("last_error_at"):
            typer.echo(f"Controller last error at: {status['last_error_at']}")

    if latest:
        typer.echo(f"Latest cycle: {latest['cycle_id']}")
        typer.echo(f"Latest cycle status: {latest['status']} (phase {latest['phase']})")
        typer.echo(f"Started: {latest['started_at']}")
        typer.echo(f"Finished: {latest['finished_at'] or 'still running'}")
        typer.echo(f"Discovery run: {latest.get('discovery_run_id') or 'n/a'}")
        typer.echo(f"State probes: {latest.get('state_probed_count', 0)} / {latest.get('state_probe_limit', 0)}")
        state_refresh_summary = latest.get("state_refresh_summary") or {}
        if state_refresh_summary:
            typer.echo(
                "State refresh health: {status} | direct {direct} | inconclusive {inconclusive} | degraded {degraded}".format(
                    status=state_refresh_summary.get("status") or "unknown",
                    direct=state_refresh_summary.get("direct_signal_count") or 0,
                    inconclusive=state_refresh_summary.get("inconclusive_probe_count") or 0,
                    degraded=state_refresh_summary.get("degraded_probe_count") or 0,
                )
            )
        typer.echo(
            "Freshness snapshot: first-pass {first_pass_only}, fresh {fresh_followup}, aging {aging_followup}, stale {stale_followup}".format(
                **latest
            )
        )

    typer.echo(
        "Cycle totals: completed {completed_cycles}, failed {failed_cycles}, running {running_cycles}, interrupted {interrupted_cycles}".format(
            **totals
        )
    )
    typer.echo("Recent cycles:")
    for cycle in status["recent_cycles"]:
        typer.echo(
            "- {cycle_id} | {mode} | {status} | phase {phase} | tracked {tracked_listings} | probes {state_probed_count}".format(
                **cycle
            )
        )


@app.command("db-health")
def db_health(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
    integrity: bool = typer.Option(False, "--integrity/--quick", help="Run full integrity_check in addition to quick_check."),
) -> None:
    report = inspect_sqlite_database(db, include_integrity_check=integrity, probe_tables=True)

    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif output_format == "table":
        _render_db_health_report(report)
    else:
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    if not report["healthy"]:
        raise typer.Exit(code=1)


@app.command()
def coverage(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    run_id: str | None = typer.Option(None, "--run-id", help="Inspect a specific run instead of the latest one."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    try:
        with RadarRepository(db) as repository:
            summary = repository.coverage_summary(run_id)
    except sqlite3.DatabaseError as exc:
        typer.echo(f"Database: {db}")
        typer.echo(f"Coverage query failed: {type(exc).__name__}: {exc}")
        typer.echo(f"Inspect DB health with: python -m vinted_radar.cli db-health --db {db} --integrity")
        raise typer.Exit(code=1) from exc

    if summary is None:
        typer.echo(f"Database: {db}")
        typer.echo("No discovery runs recorded yet.")
        return

    if output_format == "json":
        typer.echo(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    run = summary["run"]
    typer.echo(f"Database: {db}")
    typer.echo(f"Run: {run['run_id']}")
    typer.echo(f"Status: {run['status']}")
    typer.echo(f"Roots: {run['root_scope']}")
    typer.echo(f"Leaf catalogs scanned: {run['scanned_leaf_catalogs']} / {run['total_leaf_catalogs']}")
    typer.echo(f"Page scans: {run['successful_scans']} successful, {run['failed_scans']} failed")
    typer.echo(f"Listings: {run['raw_listing_hits']} sightings, {run['unique_listing_hits']} unique IDs")
    if run.get("last_error"):
        typer.echo(f"Last error: {run['last_error']}")

    typer.echo("By root:")
    for row in summary["by_root"]:
        typer.echo(
            "- {root}: {scanned}/{total} leaf catalogs scanned, {success} successful scans, {failed} failed scans, {sightings} sightings, {unique} unique IDs".format(
                root=row["root_title"],
                scanned=row["scanned_leaf_catalogs"],
                total=row["total_leaf_catalogs"],
                success=row["successful_scans"],
                failed=row["failed_scans"],
                sightings=row["listing_sightings"],
                unique=row["unique_listings"],
            )
        )

    failures = summary["failures"]
    if failures:
        typer.echo("Failures:")
        for failure in failures:
            error = failure["error_message"] or f"HTTP {failure['response_status']}"
            typer.echo(f"- {failure['catalog_path']} page {failure['page_number']}: {error}")


@app.command("freshness")
def freshness(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic inspection."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        summary = repository.freshness_summary(now=now)

    if summary["overall"]["tracked_listings"] == 0:
        typer.echo(f"Database: {db}")
        typer.echo("No listing history recorded yet.")
        return

    if output_format == "json":
        typer.echo(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    overall = summary["overall"]
    typer.echo(f"Database: {db}")
    typer.echo(f"Generated at: {summary['generated_at']}")
    typer.echo(f"Tracked listings: {overall['tracked_listings']}")
    typer.echo("Freshness buckets:")
    for bucket in ("first-pass-only", "fresh-followup", "aging-followup", "stale-followup"):
        typer.echo(f"- {bucket}: {overall[bucket]}")
    typer.echo("By root:")
    for row in summary["by_root"]:
        typer.echo(
            "- {root_title}: tracked {tracked_listings}, first-pass {first}, fresh {fresh}, aging {aging}, stale {stale}".format(
                **row,
                first=row["first-pass-only"],
                fresh=row["fresh-followup"],
                aging=row["aging-followup"],
                stale=row["stale-followup"],
            )
        )


@app.command("revisit-plan")
def revisit_plan(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    limit: int = typer.Option(10, "--limit", min=1, help="How many candidates to show."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic inspection."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        candidates = repository.revisit_candidates(limit=limit, now=now)

    if not candidates:
        typer.echo(f"Database: {db}")
        typer.echo("No revisit candidates yet.")
        return

    if output_format == "json":
        typer.echo(json.dumps(candidates, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    typer.echo(f"Database: {db}")
    typer.echo(f"Revisit candidates: {len(candidates)}")
    for candidate in candidates:
        display_title = candidate.get("title") or "(untitled)"
        _echo(
            "- {listing_id} | score {priority_score:.2f} | {freshness_bucket} | obs {observation_count} | age {last_seen_age_hours:.2f}h | {display_title}".format(
                **candidate,
                display_title=display_title,
            )
        )
        _echo(f"  reasons: {', '.join(candidate['priority_reasons'])}")


@app.command("history")
def history(
    listing_id: int = typer.Option(..., "--listing-id", min=1, help="Listing ID to inspect."),
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum timeline rows to show."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic inspection."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        history_payload = repository.listing_history(listing_id, now=now, limit=limit)

    if history_payload is None:
        typer.echo(f"Database: {db}")
        typer.echo(f"Listing {listing_id} was not found in observation history.")
        raise typer.Exit(code=1)

    if output_format == "json":
        typer.echo(json.dumps(history_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    summary = history_payload["summary"]
    typer.echo(f"Database: {db}")
    typer.echo(f"Listing: {summary['listing_id']}")
    _echo(f"Title: {summary.get('title') or '(untitled)'}")
    typer.echo(f"Root: {summary.get('root_title') or 'Unknown'}")
    typer.echo(f"Observations: {summary['observation_count']} runs ({summary['total_sightings']} sightings)")
    typer.echo(f"First seen: {summary['first_seen_at']}")
    typer.echo(f"Last seen: {summary['last_seen_at']} ({summary['last_seen_age_hours']:.2f}h ago)")
    typer.echo(f"Freshness: {summary['freshness_bucket']}")
    average_revisit = summary.get("average_revisit_hours")
    typer.echo(f"Average revisit gap: {average_revisit:.2f}h" if average_revisit is not None else "Average revisit gap: n/a")
    typer.echo("Timeline:")
    for row in history_payload["timeline"]:
        _echo(
            "- {observed_at} | run {run_id} | sightings {sighting_count} | {price} | {catalog}".format(
                observed_at=row["observed_at"],
                run_id=row["run_id"],
                sighting_count=row["sighting_count"],
                price=_format_money(row.get("price_amount_cents"), row.get("price_currency")),
                catalog=row.get("catalog_path") or "Unknown catalog",
            )
        )


@app.command("state-refresh")
def state_refresh(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum number of listings to probe."),
    listing_id: int | None = typer.Option(None, "--listing-id", min=1, help="Refresh a specific listing instead of selecting probe candidates."),
    request_delay: float = typer.Option(0.5, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy URL (http://user:pass@host:port). Repeatable for pool."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    service = build_default_state_refresh_service(
        db_path=str(db),
        timeout_seconds=timeout_seconds,
        request_delay=request_delay,
        proxies=list(proxy) if proxy else None,
    )
    try:
        report = service.refresh(limit=limit, listing_id=listing_id, now=now)
    finally:
        service.repository.close()

    if output_format == "json":
        typer.echo(
            json.dumps(
                {
                    "probed_count": report.probed_count,
                    "probed_listing_ids": report.probed_listing_ids,
                    "probe_summary": report.probe_summary,
                    "state_summary": report.state_summary,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    typer.echo(f"Database: {db}")
    typer.echo(f"Probed listings: {report.probed_count}")
    if report.probed_listing_ids:
        typer.echo(f"Listing IDs: {', '.join(str(item) for item in report.probed_listing_ids)}")
    probe_summary = report.probe_summary or {}
    if probe_summary:
        typer.echo(
            "Probe health: {status} | direct {direct} | inconclusive {inconclusive} | degraded {degraded}".format(
                status=probe_summary.get("status") or "unknown",
                direct=probe_summary.get("direct_signal_count") or 0,
                inconclusive=probe_summary.get("inconclusive_probe_count") or 0,
                degraded=probe_summary.get("degraded_probe_count") or 0,
            )
        )
        if probe_summary.get("anti_bot_challenge_count"):
            typer.echo(f"Anti-bot challenges: {probe_summary['anti_bot_challenge_count']}")
        if probe_summary.get("transport_error_count"):
            typer.echo(f"Transport errors: {probe_summary['transport_error_count']}")
    _render_state_summary(report.state_summary)


@app.command("state-summary")
def state_summary(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        inputs = repository.listing_state_inputs(now=now)

    if not inputs:
        typer.echo(f"Database: {db}")
        typer.echo("No listing state inputs recorded yet.")
        return

    evaluations = [evaluate_listing_state(item, now=now) for item in inputs]
    summary = summarize_state_evaluations(evaluations, generated_at=now)

    if output_format == "json":
        typer.echo(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    typer.echo(f"Database: {db}")
    _render_state_summary(summary)


@app.command("state")
def state_detail(
    listing_id: int = typer.Option(..., "--listing-id", min=1, help="Listing ID to inspect."),
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        inputs = repository.listing_state_inputs(now=now, listing_id=listing_id)

    if not inputs:
        typer.echo(f"Database: {db}")
        typer.echo(f"Listing {listing_id} has no state input history.")
        raise typer.Exit(code=1)

    evaluation = evaluate_listing_state(inputs[0], now=now)

    if output_format == "json":
        typer.echo(json.dumps(evaluation, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    typer.echo(f"Database: {db}")
    typer.echo(f"Listing: {evaluation['listing_id']}")
    _echo(f"Title: {evaluation.get('title') or '(untitled)'}")
    typer.echo(f"State: {evaluation['state_code']}")
    typer.echo(f"Basis: {evaluation['basis_kind']}")
    typer.echo(f"Confidence: {evaluation['confidence_label']} ({evaluation['confidence_score']:.2f})")
    typer.echo(f"Root: {evaluation.get('root_title') or 'Unknown'}")
    typer.echo(f"First seen: {evaluation['first_seen_at']}")
    typer.echo(f"Last seen: {evaluation['last_seen_at']} ({evaluation['last_seen_age_hours']:.2f}h ago)")
    typer.echo(f"Observations: {evaluation['observation_count']} runs ({evaluation['total_sightings']} sightings)")
    typer.echo(f"Follow-up misses: {evaluation.get('follow_up_miss_count') or 0}")
    latest_probe = evaluation.get("latest_probe")
    if isinstance(latest_probe, dict):
        typer.echo(
            f"Latest probe: {latest_probe.get('probed_at')} | outcome {latest_probe.get('probe_outcome')} | HTTP {latest_probe.get('response_status')}"
        )
        if latest_probe.get("error_message"):
            _echo(f"Probe error: {latest_probe['error_message']}")
    typer.echo("Reasons:")
    for reason in evaluation["state_explanation"]["reasons"]:
        _echo(f"- {reason}")


@app.command("score")
def score_detail(
    listing_id: int = typer.Option(..., "--listing-id", min=1, help="Listing ID to inspect."),
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        listing_scores = load_listing_scores(repository, now=now)
    payload = build_listing_score_detail(listing_scores, listing_id)
    if payload is None:
        typer.echo(f"Database: {db}")
        typer.echo(f"Listing {listing_id} has no score inputs.")
        raise typer.Exit(code=1)

    if output_format == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    typer.echo(f"Database: {db}")
    typer.echo(f"Listing: {payload['listing_id']}")
    _echo(f"Title: {payload.get('title') or '(untitled)'}")
    typer.echo(f"Demand score: {payload['demand_score']:.2f}")
    typer.echo(f"Premium score: {payload['premium_score']:.2f}")
    typer.echo(f"State: {payload['state_code']} | {payload['basis_kind']} | {payload['confidence_label']}")
    typer.echo("Demand factors:")
    for name, value in payload["score_explanation"]["factors"].items():
        typer.echo(f"- {name}: {value:.2f}")
    context = payload["score_explanation"].get("context")
    if context is None:
        typer.echo("Context: unavailable (no trustworthy peer sample)")
    else:
        typer.echo(
            "Context: {label} | peers {sample_size} | percentile {price_percentile} | band {price_band_label} | premium boost {expensive_signal:.2f}".format(
                **context
            )
        )


@app.command("rankings")
def rankings(
    kind: str = typer.Option("demand", "--kind", help="demand or premium."),
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    limit: int = typer.Option(10, "--limit", min=1, help="How many ranked listings to show."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        listing_scores = load_listing_scores(repository, now=now)
    ranking_kind = _score_kind(kind)
    ranking_rows = build_rankings(listing_scores, kind=ranking_kind, limit=limit)

    if output_format == "json":
        typer.echo(json.dumps(ranking_rows, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    score_field = "demand_score" if ranking_kind == "demand" else "premium_score"
    typer.echo(f"Database: {db}")
    typer.echo(f"Ranking kind: {ranking_kind}")
    typer.echo(f"Rows: {len(ranking_rows)}")
    for row in ranking_rows:
        _echo(
            "- {listing_id} | {score_name} {score:.2f} | demand {demand:.2f} | {state_code} | {catalog} | {title}".format(
                listing_id=row["listing_id"],
                score_name=score_field,
                score=float(row[score_field]),
                demand=float(row["demand_score"]),
                state_code=row["state_code"],
                catalog=row.get("primary_catalog_path") or row.get("root_title") or "Unknown",
                title=row.get("title") or "(untitled)",
            )
        )


@app.command("market-summary")
def market_summary(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    limit: int = typer.Option(8, "--limit", min=1, help="How many segments to show per section."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        listing_scores = load_listing_scores(repository, now=now)
        summary = build_market_summary(listing_scores, repository, now=now, limit=limit)

    if output_format == "json":
        typer.echo(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    typer.echo(f"Database: {db}")
    typer.echo(f"Generated at: {summary['generated_at']}")
    typer.echo(f"Tracked listings: {summary['overall']['tracked_listings']}")
    typer.echo("Top performing segments:")
    for segment in summary["performing_segments"]:
        typer.echo(
            "- {catalog_path} | tracked {tracked_listings} | demand {avg_demand_score:.2f} | premium {avg_premium_score:.2f} | performance {performance_score:.2f}".format(
                **segment
            )
        )
    typer.echo("Rising segments:")
    for segment in summary["rising_segments"]:
        typer.echo(
            "- {catalog_path} | recent arrivals {recent_arrivals} | delta {visible_delta} | sold-like {sold_like_count} | rising {rising_score:.2f}".format(
                **segment
            )
        )


@app.command("dashboard")
def dashboard(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind the local dashboard server."),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Port to bind the local dashboard server."),
    base_path: str = typer.Option("", "--base-path", help="Optional route prefix when the dashboard is mounted behind a reverse proxy (example: /radar)."),
    public_base_url: str | None = typer.Option(None, "--public-base-url", help="Optional external base URL prefix advertised to operators and used for absolute dashboard links (example: https://radar.example.com/radar)."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic rendering."),
) -> None:
    _echo_dashboard_urls(host=host, port=port, base_path=base_path, public_base_url=public_base_url)
    typer.echo(f"Database: {db}")
    try:
        serve_dashboard(db_path=db, host=host, port=port, now=now, base_path=base_path, public_base_url=public_base_url)
    except KeyboardInterrupt:
        typer.echo("Dashboard server stopped.")


def _echo_dashboard_urls(
    *,
    host: str,
    port: int,
    base_path: str = "",
    public_base_url: str | None = None,
) -> None:
    urls = build_dashboard_urls(host, port, base_path=base_path, public_base_url=public_base_url)
    typer.echo(f"Dashboard URL: {urls['dashboard'].rstrip('/')}")
    typer.echo(f"Overview home: {urls['home']}")
    typer.echo(f"Dashboard API: {urls['dashboard_api']}")
    typer.echo(f"Explorer: {urls['explorer']}")
    typer.echo(f"Runtime: {urls['runtime']}")
    typer.echo(f"Runtime API: {urls['runtime_api']}")
    typer.echo(f"Listing detail: {urls['detail']}")
    typer.echo(f"Listing detail API: {urls['detail_api']}")
    typer.echo(f"Health: {urls['health']}")



def _build_runtime_options(
    *,
    page_limit: int,
    max_leaf_categories: int | None,
    root_scope: str,
    min_price: float,
    target_catalogs: list[int] | None,
    target_brands: list[str] | None,
    state_refresh_limit: int,
    request_delay: float,
    timeout_seconds: float,
    concurrency: int,
    proxies: tuple[str, ...] = (),
) -> RadarRuntimeOptions:
    return RadarRuntimeOptions(
        page_limit=page_limit,
        max_leaf_categories=max_leaf_categories,
        root_scope=root_scope,
        min_price=min_price,
        target_catalogs=tuple(target_catalogs or ()),
        target_brands=tuple(target_brands or ()),
        request_delay=request_delay,
        timeout_seconds=timeout_seconds,
        state_refresh_limit=state_refresh_limit,
        concurrency=concurrency,
        proxies=proxies,
    )


def _render_runtime_cycle_report(report: RadarRuntimeCycleReport, *, db: Path) -> None:
    typer.echo(f"Database: {db}")
    typer.echo(f"Cycle: {report.cycle_id}")
    typer.echo(f"Mode: {report.mode}")
    typer.echo(f"Status: {report.status} (phase {report.phase})")
    typer.echo(f"Started: {report.started_at}")
    typer.echo(f"Finished: {report.finished_at or 'still running'}")
    typer.echo(f"Discovery run: {report.discovery_run_id or 'n/a'}")
    if report.discovery_report is not None:
        successful_scans = report.discovery_report.successful_scans
        failed_scans = report.discovery_report.failed_scans
        if failed_scans:
            discovery_summary = (
                "Discovery: {raw_listing_hits} sightings, {unique_listing_hits} unique IDs, {successful_scans} successful scans, {failed_scans} scan failures"
            ).format(
                raw_listing_hits=report.discovery_report.raw_listing_hits,
                unique_listing_hits=report.discovery_report.unique_listing_hits,
                successful_scans=successful_scans,
                failed_scans=failed_scans,
            )
        else:
            discovery_summary = (
                "Discovery: {raw_listing_hits} sightings, {unique_listing_hits} unique IDs, {successful_scans} successful scans, all scans clean"
            ).format(
                raw_listing_hits=report.discovery_report.raw_listing_hits,
                unique_listing_hits=report.discovery_report.unique_listing_hits,
                successful_scans=successful_scans,
            )
        typer.echo(discovery_summary)
    typer.echo(f"State probes: {report.state_probed_count} / {report.config.get('state_refresh_limit', 0)}")
    if report.state_refresh_summary:
        typer.echo(
            "State refresh health: {status} | direct {direct} | inconclusive {inconclusive} | degraded {degraded}".format(
                status=report.state_refresh_summary.get("status") or "unknown",
                direct=report.state_refresh_summary.get("direct_signal_count") or 0,
                inconclusive=report.state_refresh_summary.get("inconclusive_probe_count") or 0,
                degraded=report.state_refresh_summary.get("degraded_probe_count") or 0,
            )
        )
        if report.state_refresh_summary.get("anti_bot_challenge_count"):
            typer.echo(f"Anti-bot challenges: {report.state_refresh_summary['anti_bot_challenge_count']}")
    typer.echo(f"Tracked listings: {report.tracked_listings}")
    typer.echo(
        "Freshness snapshot: first-pass {first_pass_only}, fresh {fresh_followup}, aging {aging_followup}, stale {stale_followup}".format(
            first_pass_only=report.freshness_counts["first-pass-only"],
            fresh_followup=report.freshness_counts["fresh-followup"],
            aging_followup=report.freshness_counts["aging-followup"],
            stale_followup=report.freshness_counts["stale-followup"],
        )
    )
    if report.last_error:
        _echo(f"Last error: {report.last_error}")


def _render_state_summary(summary: dict[str, object]) -> None:
    overall = summary["overall"]
    typer.echo(f"Generated at: {summary['generated_at']}")
    typer.echo(f"Tracked listings: {overall['tracked_listings']}")
    typer.echo("States:")
    for state_code in ("active", "sold_observed", "sold_probable", "unavailable_non_conclusive", "deleted", "unknown"):
        typer.echo(f"- {state_code}: {overall[state_code]}")
    typer.echo(
        "Confidence: high {high_confidence}, medium {medium_confidence}, low {low_confidence}".format(**overall)
    )
    typer.echo(
        "Basis: observed {observed_basis}, inferred {inferred_basis}, unknown {unknown_basis}".format(**overall)
    )
    typer.echo("By root:")
    for row in summary["by_root"]:
        typer.echo(
            "- {root_title}: active {active}, sold_observed {sold_observed}, sold_probable {sold_probable}, unavailable {unavailable_non_conclusive}, deleted {deleted}, unknown {unknown}".format(
                **row
            )
        )


def _render_db_health_report(report: dict[str, object]) -> None:
    typer.echo(f"Database: {report['db_path']}")
    typer.echo(f"Exists: {'yes' if report['exists'] else 'no'}")
    if not report["exists"]:
        typer.echo("Database file was not found.")
        return

    typer.echo(f"Size: {report['size_bytes']} bytes")
    if report.get("open_error"):
        typer.echo(f"Open error: {report['open_error']}")
        return
    if report.get("schema_error"):
        typer.echo(f"Schema error: {report['schema_error']}")

    typer.echo(f"Schema tables: {report.get('schema_table_count')}")
    typer.echo("Checks:")
    for name, check in dict(report.get("checks") or {}).items():
        if check.get("ok"):
            typer.echo(f"- {name}: ok")
            continue
        if check.get("error"):
            typer.echo(f"- {name}: {check['error']}")
            continue
        messages = "; ".join(str(item) for item in list(check.get("messages") or [])[:3]) or "check failed"
        typer.echo(f"- {name}: {messages}")

    typer.echo("Critical tables:")
    for table in list(report.get("tables") or []):
        if not table.get("exists"):
            typer.echo(f"- {table['table']}: missing")
            continue
        parts: list[str] = []
        if table.get("count_ok"):
            parts.append(f"count ok ({table['row_count']} rows)")
        else:
            parts.append(f"count error {table['count_error']}")
        if table.get("sample_ok"):
            parts.append("sample ok")
        else:
            parts.append(f"sample error {table['sample_error']}")
        typer.echo(f"- {table['table']}: {', '.join(parts)}")

    typer.echo(f"Healthy: {'yes' if report['healthy'] else 'no'}")


def _format_money(amount_cents: object, currency: object) -> str:
    if amount_cents is None:
        return "price n/a"
    return f"{int(amount_cents) / 100:.2f} {currency or ''}".strip()


def _format_duration_seconds(value: object) -> str:
    if value is None:
        return "n/a"
    seconds = max(int(round(float(value))), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _score_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized not in {"demand", "premium"}:
        raise typer.BadParameter("--kind must be either 'demand' or 'premium'.")
    return normalized


def _echo(message: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    safe_message = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
    typer.echo(safe_message)


def main() -> None:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    app()


if __name__ == "__main__":
    main()
