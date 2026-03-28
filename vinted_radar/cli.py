from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3
import sys

import typer

from vinted_radar.dashboard import serve_dashboard, start_dashboard_server
from vinted_radar.db_health import inspect_sqlite_database
from vinted_radar.http import VintedHttpClient
from vinted_radar.long_run_audit import build_long_run_audit_report, render_long_run_audit_markdown
from vinted_radar.platform import (
    bootstrap_data_platform,
    doctor_data_platform,
    load_platform_config,
    render_platform_report_lines,
)
from vinted_radar.proxies import mask_proxy_url, resolve_proxy_pool
from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import build_listing_score_detail, build_market_summary, build_rankings, load_listing_scores
from vinted_radar.services.discovery import DiscoveryOptions, build_default_service
from vinted_radar.services.runtime import RadarRuntimeCycleReport, RadarRuntimeOptions, RadarRuntimeService
from vinted_radar.services.state_refresh import build_default_state_refresh_service
from vinted_radar.serving import build_dashboard_urls
from vinted_radar.state_machine import evaluate_listing_state, summarize_state_evaluations

app = typer.Typer(add_completion=False, help="Local-first Vinted Homme/Femme radar CLI.")

_AUTO_PROXY_CONCURRENCY_CAP = 24
_PROXY_PREFLIGHT_IP_ECHO_URL = "https://api.ipify.org?format=json"
_PROXY_PREFLIGHT_VINTED_URL = "https://www.vinted.fr/api/v2/catalog/items?catalog_ids=1439&page=1&per_page=1"


def _resolve_cli_proxies(*, proxy: list[str] | None, proxy_file: Path | None) -> tuple[str, ...]:
    return tuple(resolve_proxy_pool(inline=proxy, proxy_file=proxy_file))


def _resolve_cli_concurrency(concurrency: int | None, *, proxies: tuple[str, ...]) -> int:
    if concurrency is not None:
        return concurrency
    if proxies:
        return max(1, min(len(proxies), _AUTO_PROXY_CONCURRENCY_CAP))
    return 1


def _render_transport_summary(*, proxies: tuple[str, ...], concurrency: int | None = None) -> str:
    if not proxies:
        return "Transport: direct"
    resolved_concurrency = _resolve_cli_concurrency(concurrency, proxies=proxies)
    return f"Transport: proxy-pool ({len(proxies)} routes, concurrency {resolved_concurrency})"


@app.command()
def discover(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    page_limit: int = typer.Option(5, "--page-limit", min=1, help="How many catalog pages to fetch per leaf category."),
    max_leaf_categories: int | None = typer.Option(None, "--max-leaf-categories", min=1, help="Limit the number of leaf categories scanned in the run."),
    root_scope: str = typer.Option("both", "--root-scope", help="Which root catalogs to scan: both, women, or men."),
    min_price: float = typer.Option(30.0, "--min-price", min=0.0, help="Minimum listing price in euros. Defaults to 30.0; use 0 to force an explicit unbounded debug or benchmark run."),
    max_price: float = typer.Option(0.0, "--max-price", min=0.0, help="Maximum listing price in euros. Defaults to 0.0, which keeps the upper bound disabled."),
    request_delay: float = typer.Option(3.0, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    concurrency: int | None = typer.Option(None, "--concurrency", min=1, help="Max requests in flight across all catalogs. Defaults to 1 in direct mode and auto-scales up to 24 when a proxy pool is configured."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy entry. Accepts either http://user:pass@host:port or host:port:user:pass. Repeatable for pool."),
    proxy_file: Path | None = typer.Option(None, "--proxy-file", help="Optional local proxy list file. If omitted, commands auto-load data/proxies.txt when it exists."),
) -> None:
    proxies = _resolve_cli_proxies(proxy=proxy, proxy_file=proxy_file)
    resolved_concurrency = _resolve_cli_concurrency(concurrency, proxies=proxies)
    service = build_default_service(db_path=str(db), timeout_seconds=timeout_seconds, request_delay=request_delay, proxies=list(proxies) or None)
    try:
        report = service.run(
            DiscoveryOptions(
                page_limit=page_limit,
                max_leaf_categories=max_leaf_categories,
                root_scope=root_scope,
                request_delay=request_delay,
                concurrency=resolved_concurrency,
                min_price=min_price,
                max_price=max_price,
            )
        )
    finally:
        service.repository.close()

    typer.echo(f"Run: {report.run_id}")
    typer.echo(_render_transport_summary(proxies=proxies, concurrency=resolved_concurrency))
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
    min_price: float = typer.Option(30.0, "--min-price", min=0.0, help="Minimum listing price in euros. Defaults to 30.0; use 0 to force an explicit unbounded debug or benchmark run."),
    max_price: float = typer.Option(0.0, "--max-price", min=0.0, help="Maximum listing price in euros. Defaults to 0.0, which keeps the upper bound disabled."),
    target_catalogs: list[int] | None = typer.Option(None, "--target-catalogs", help="Catalog ID to scan. Repeatable."),
    target_brands: list[str] | None = typer.Option(None, "--target-brands", help="Brand name to allow. Repeatable."),
    state_refresh_limit: int = typer.Option(10, "--state-refresh-limit", min=1, help="How many listing item pages to probe after discovery."),
    request_delay: float = typer.Option(3.0, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    concurrency: int | None = typer.Option(None, "--concurrency", min=1, help="Max requests in flight across all catalogs. Defaults to 1 in direct mode and auto-scales up to 24 when a proxy pool is configured."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy entry. Accepts either http://user:pass@host:port or host:port:user:pass. Repeatable for pool."),
    proxy_file: Path | None = typer.Option(None, "--proxy-file", help="Optional local proxy list file. If omitted, commands auto-load data/proxies.txt when it exists."),
    dashboard: bool = typer.Option(False, "--dashboard/--no-dashboard", help="Serve the local dashboard after the batch cycle completes."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind the local dashboard server when --dashboard is enabled."),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Port to bind the local dashboard server when --dashboard is enabled."),
    base_path: str = typer.Option("", "--base-path", help="Optional route prefix when the dashboard is mounted behind a reverse proxy (example: /radar)."),
    public_base_url: str | None = typer.Option(None, "--public-base-url", help="Optional external base URL prefix advertised to operators and used for absolute dashboard links (example: https://radar.example.com/radar)."),
) -> None:
    proxies = _resolve_cli_proxies(proxy=proxy, proxy_file=proxy_file)
    resolved_concurrency = _resolve_cli_concurrency(concurrency, proxies=proxies)
    runtime_service = RadarRuntimeService(db)
    options = _build_runtime_options(
        page_limit=page_limit,
        max_leaf_categories=max_leaf_categories,
        root_scope=root_scope,
        min_price=min_price,
        max_price=max_price,
        target_catalogs=target_catalogs,
        target_brands=target_brands,
        state_refresh_limit=state_refresh_limit,
        request_delay=request_delay,
        timeout_seconds=timeout_seconds,
        concurrency=resolved_concurrency,
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
    min_price: float = typer.Option(30.0, "--min-price", min=0.0, help="Minimum listing price in euros. Defaults to 30.0; use 0 to force an explicit unbounded debug or benchmark run."),
    max_price: float = typer.Option(0.0, "--max-price", min=0.0, help="Maximum listing price in euros. Defaults to 0.0, which keeps the upper bound disabled."),
    target_catalogs: list[int] | None = typer.Option(None, "--target-catalogs", help="Catalog ID to scan. Repeatable."),
    target_brands: list[str] | None = typer.Option(None, "--target-brands", help="Brand name to allow. Repeatable."),
    state_refresh_limit: int = typer.Option(10, "--state-refresh-limit", min=1, help="How many listing item pages to probe after each discovery cycle."),
    interval_seconds: float = typer.Option(1800.0, "--interval-seconds", min=0.1, help="Delay between completed cycles in seconds."),
    max_cycles: int | None = typer.Option(None, "--max-cycles", min=1, help="Optional cycle cap for smoke runs or tests."),
    request_delay: float = typer.Option(3.0, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
    concurrency: int | None = typer.Option(None, "--concurrency", min=1, help="Max requests in flight across all catalogs. Defaults to 1 in direct mode and auto-scales up to 24 when a proxy pool is configured."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy entry. Accepts either http://user:pass@host:port or host:port:user:pass. Repeatable for pool."),
    proxy_file: Path | None = typer.Option(None, "--proxy-file", help="Optional local proxy list file. If omitted, commands auto-load data/proxies.txt when it exists."),
    dashboard: bool = typer.Option(False, "--dashboard/--no-dashboard", help="Serve the local dashboard alongside the continuous loop."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind the local dashboard server when --dashboard is enabled."),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Port to bind the local dashboard server when --dashboard is enabled."),
    base_path: str = typer.Option("", "--base-path", help="Optional route prefix when the dashboard is mounted behind a reverse proxy (example: /radar)."),
    public_base_url: str | None = typer.Option(None, "--public-base-url", help="Optional external base URL prefix advertised to operators and used for absolute dashboard links (example: https://radar.example.com/radar)."),
) -> None:
    proxies = _resolve_cli_proxies(proxy=proxy, proxy_file=proxy_file)
    resolved_concurrency = _resolve_cli_concurrency(concurrency, proxies=proxies)
    runtime_service = RadarRuntimeService(db)
    options = _build_runtime_options(
        page_limit=page_limit,
        max_leaf_categories=max_leaf_categories,
        root_scope=root_scope,
        min_price=min_price,
        max_price=max_price,
        target_catalogs=target_catalogs,
        target_brands=target_brands,
        state_refresh_limit=state_refresh_limit,
        request_delay=request_delay,
        timeout_seconds=timeout_seconds,
        concurrency=resolved_concurrency,
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
    typer.echo(_render_transport_summary(proxies=proxies, concurrency=resolved_concurrency))
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


@app.command("proxy-preflight")
def proxy_preflight(
    sample_size: int = typer.Option(8, "--sample-size", min=1, help="How many proxy routes to sample from the configured pool."),
    timeout_seconds: float = typer.Option(10.0, "--timeout-seconds", min=1.0, help="Per-request timeout in seconds for each sampled route."),
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy entry. Accepts either http://user:pass@host:port or host:port:user:pass. Repeatable for pool."),
    proxy_file: Path | None = typer.Option(None, "--proxy-file", help="Optional local proxy list file. If omitted, commands auto-load data/proxies.txt when it exists."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    proxies = _resolve_cli_proxies(proxy=proxy, proxy_file=proxy_file)
    if not proxies:
        raise typer.BadParameter("No proxy pool is configured. Provide --proxy, --proxy-file, or create data/proxies.txt.")

    report = asyncio.run(
        _run_proxy_preflight(
            proxies=proxies,
            sample_size=sample_size,
            timeout_seconds=timeout_seconds,
        )
    )

    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")

    summary = dict(report.get("summary") or {})
    typer.echo(_render_transport_summary(proxies=proxies))
    typer.echo(
        "Preflight: sampled {sampled}/{configured} routes | success {success} | failed {failed} | unique exits {unique_exit_ips}".format(
            sampled=summary.get("sampled_routes") or 0,
            configured=summary.get("configured_proxy_count") or 0,
            success=summary.get("successful_routes") or 0,
            failed=summary.get("failed_routes") or 0,
            unique_exit_ips=summary.get("unique_exit_ip_count") or 0,
        )
    )
    typer.echo(
        "Vinted reachability: success {success} | challenge suspects {challenge}".format(
            success=summary.get("vinted_success_count") or 0,
            challenge=summary.get("vinted_challenge_count") or 0,
        )
    )
    for route in list(report.get("routes") or []):
        typer.echo(
            "- {route}: ip {ip_status}/{exit_ip} | vinted {vinted_status} | ok {ok}".format(
                route=route.get("route") or "unknown",
                ip_status=route.get("ip_echo_status") or "n/a",
                exit_ip=route.get("exit_ip") or "n/a",
                vinted_status=route.get("vinted_status") or "n/a",
                ok="yes" if route.get("ok") else "no",
            )
        )
        if route.get("error"):
            _echo(f"  error: {route['error']}")
        if route.get("challenge_suspected"):
            _echo("  note: Vinted challenge suspected on this route")


@app.command("platform-bootstrap")
def platform_bootstrap(
    output_format: str = typer.Option("table", "--format", help="table or json."),
    check_writes: bool = typer.Option(True, "--check-writes/--skip-writes", help="Write and delete probe objects under each configured object-store prefix after bootstrap."),
) -> None:
    try:
        config = load_platform_config()
    except ValueError as exc:
        typer.echo(f"Platform config error: {exc}")
        raise typer.Exit(code=1) from exc

    report = bootstrap_data_platform(config=config, check_writes=check_writes)
    _emit_platform_report(report=report, output_format=output_format)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command("platform-doctor")
def platform_doctor(
    output_format: str = typer.Option("table", "--format", help="table or json."),
    check_writes: bool = typer.Option(True, "--check-writes/--skip-writes", help="Write and delete probe objects under each configured object-store prefix during diagnostics."),
) -> None:
    try:
        config = load_platform_config()
    except ValueError as exc:
        typer.echo(f"Platform config error: {exc}")
        raise typer.Exit(code=1) from exc

    report = doctor_data_platform(config=config, check_writes=check_writes)
    _emit_platform_report(report=report, output_format=output_format)
    if not report.ok:
        raise typer.Exit(code=1)


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


@app.command("audit-long-run")
def audit_long_run(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    hours: float = typer.Option(12.0, "--hours", min=0.1, help="How many trailing hours to audit."),
    issue_limit: int = typer.Option(5, "--issue-limit", min=1, help="How many failing catalogs, degraded listings, and failure samples to include."),
    revisit_limit: int = typer.Option(10, "--revisit-limit", min=1, help="How many revisit candidates to include."),
    output_format: str = typer.Option("table", "--format", help="table, json, or markdown."),
    integrity: bool = typer.Option(False, "--integrity/--quick", help="Run full integrity_check before trusting the audit. Recommended on copied VPS snapshots."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic audit windows."),
) -> None:
    report = build_long_run_audit_report(
        db,
        hours=hours,
        now=now,
        include_integrity_check=integrity,
        issue_limit=issue_limit,
        revisit_limit=revisit_limit,
    )

    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif output_format == "markdown":
        _echo(render_long_run_audit_markdown(report))
    elif output_format == "table":
        _render_long_run_audit_report(report)
    else:
        raise typer.BadParameter("--format must be either 'table', 'json', or 'markdown'.")

    if not bool(((report.get("db") or {}).get("health") or {}).get("healthy")):
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
    proxy: list[str] | None = typer.Option(None, "--proxy", help="Proxy entry. Accepts either http://user:pass@host:port or host:port:user:pass. Repeatable for pool."),
    proxy_file: Path | None = typer.Option(None, "--proxy-file", help="Optional local proxy list file. If omitted, commands auto-load data/proxies.txt when it exists."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    proxies = _resolve_cli_proxies(proxy=proxy, proxy_file=proxy_file)
    service = build_default_state_refresh_service(
        db_path=str(db),
        timeout_seconds=timeout_seconds,
        request_delay=request_delay,
        proxies=list(proxies) or None,
    )
    try:
        report = service.refresh(limit=limit, listing_id=listing_id, now=now)
    finally:
        service.repository.close()

    if output_format == "json":
        typer.echo(
            json.dumps(
                {
                    "transport": {
                        "mode": "proxy-pool" if proxies else "direct",
                        "proxy_pool_size": len(proxies),
                    },
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
    typer.echo(_render_transport_summary(proxies=proxies))
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



async def _run_proxy_preflight(
    *,
    proxies: tuple[str, ...],
    sample_size: int,
    timeout_seconds: float,
) -> dict[str, object]:
    selected = list(proxies[:sample_size])
    results = await asyncio.gather(
        *(
            _probe_single_proxy(proxy_url=proxy_url, timeout_seconds=timeout_seconds)
            for proxy_url in selected
        )
    )
    unique_exit_ips = {
        str(item.get("exit_ip"))
        for item in results
        if item.get("exit_ip")
    }
    successful_routes = sum(1 for item in results if item.get("ok"))
    failed_routes = len(results) - successful_routes
    vinted_success_count = sum(1 for item in results if item.get("vinted_ok"))
    vinted_challenge_count = sum(1 for item in results if item.get("challenge_suspected"))
    return {
        "summary": {
            "configured_proxy_count": len(proxies),
            "sampled_routes": len(results),
            "successful_routes": successful_routes,
            "failed_routes": failed_routes,
            "unique_exit_ip_count": len(unique_exit_ips),
            "vinted_success_count": vinted_success_count,
            "vinted_challenge_count": vinted_challenge_count,
        },
        "routes": results,
    }


async def _probe_single_proxy(*, proxy_url: str, timeout_seconds: float) -> dict[str, object]:
    route_label = mask_proxy_url(proxy_url)
    payload: dict[str, object] = {
        "route": route_label,
        "exit_ip": None,
        "ip_echo_status": None,
        "vinted_status": None,
        "challenge_suspected": False,
        "vinted_ok": False,
        "ok": False,
        "error": None,
    }
    client = VintedHttpClient(
        proxies=[proxy_url],
        request_delay=0.0,
        timeout_seconds=timeout_seconds,
        max_retries=1,
    )
    try:
        ip_response = await client.get_text_async(_PROXY_PREFLIGHT_IP_ECHO_URL)
        payload["ip_echo_status"] = ip_response.status_code
        if ip_response.status_code < 400:
            payload["exit_ip"] = _extract_exit_ip(ip_response.text)

        vinted_response = await client.get_text_async(_PROXY_PREFLIGHT_VINTED_URL)
        challenge_suspected = _response_looks_like_vinted_challenge(vinted_response.text)
        payload["vinted_status"] = vinted_response.status_code
        payload["challenge_suspected"] = challenge_suspected
        payload["vinted_ok"] = (
            vinted_response.status_code < 400
            and not challenge_suspected
            and _response_looks_like_json(vinted_response.text)
        )
        payload["ok"] = (
            ip_response.status_code < 400
            and payload["exit_ip"] is not None
            and bool(payload["vinted_ok"])
        )
    except Exception as exc:  # noqa: BLE001
        payload["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await client.close_async()
        client.close()
    return payload


def _extract_exit_ip(text: str) -> str | None:
    candidate = text.strip()
    if not candidate:
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return candidate or None
    if isinstance(payload, dict):
        ip_value = payload.get("ip") or payload.get("origin")
        return None if ip_value is None else str(ip_value)
    return candidate


def _response_looks_like_json(text: str) -> bool:
    candidate = text.strip()
    if not candidate:
        return False
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict)


def _response_looks_like_vinted_challenge(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "captcha",
            "turnstile",
            "cloudflare",
            "just a moment",
            "attention required",
            "__cf_chl",
        )
    )


def _build_runtime_options(
    *,
    page_limit: int,
    max_leaf_categories: int | None,
    root_scope: str,
    min_price: float,
    max_price: float,
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
        max_price=max_price,
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
    typer.echo(
        _render_transport_summary(
            proxies=tuple(["proxy"] * int(report.config.get("proxy_pool_size") or 0)),
            concurrency=int(report.config.get("concurrency") or 0) or None,
        )
    )
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


def _render_long_run_audit_report(report: dict[str, object]) -> None:
    db = dict(report.get("db") or {})
    db_health = dict(db.get("health") or {})
    verdict = dict(report.get("verdict") or {})
    runtime = dict(report.get("runtime") or {})
    discovery = dict(report.get("discovery") or {})
    acquisition = dict(report.get("acquisition") or {})
    freshness = dict(report.get("freshness") or {})
    freshness_overall = dict(freshness.get("overall") or {})
    probe_totals = dict(acquisition.get("probe_totals") or {})

    typer.echo(f"Database: {db.get('path')}")
    typer.echo(
        "Audit window: {hours}h ({start} → {end})".format(
            hours=report.get("window_hours"),
            start=report.get("window_started_at"),
            end=report.get("window_finished_at"),
        )
    )
    typer.echo(
        "Verdict: {status} — {summary}".format(
            status=verdict.get("status") or "unknown",
            summary=verdict.get("summary") or "n/a",
        )
    )
    typer.echo(
        "Database health: {healthy} | size {size} bytes".format(
            healthy="yes" if db_health.get("healthy") else "no",
            size=db_health.get("size_bytes") or 0,
        )
    )

    typer.echo("Runtime:")
    typer.echo(
        "- cycles {cycle_count} | completed {completed_cycles} | failed {failed_cycles} | interrupted {interrupted_cycles} | running {running_cycles}".format(
            **runtime,
        )
    )
    typer.echo(
        "- success rate {success_rate} | average cycle {avg}".format(
            success_rate=runtime.get("success_rate") if runtime.get("success_rate") is not None else "n/a",
            avg=_format_duration_seconds(runtime.get("average_cycle_seconds")),
        )
    )
    typer.echo(
        "- controller now {status} (phase {phase})".format(
            status=runtime.get("latest_controller_status") or "n/a",
            phase=runtime.get("latest_controller_phase") or "n/a",
        )
    )
    latest_cycle = runtime.get("latest_window_cycle") or {}
    if latest_cycle:
        typer.echo(
            "- latest cycle {cycle_id} | {status} | phase {phase} | tracked {tracked_listings} | probes {state_probed_count}".format(
                **latest_cycle,
            )
        )
    failure_phases = list(runtime.get("failure_phases") or [])
    if failure_phases:
        typer.echo("- failure phases:")
        for item in failure_phases:
            typer.echo(f"  - {item['label']}: {item['count']}")

    typer.echo("Discovery:")
    typer.echo(
        "- runs {run_count} | unique leaf catalogs {unique_leaf_catalogs_scanned}/{total_leaf_catalogs_known} | scans ok {sum_successful_scans} | scans failed {sum_failed_scans}".format(
            **discovery,
        )
    )
    typer.echo(
        "- unique listing hits total {hits} | avg per run {avg} | repeated scan factor {factor}".format(
            hits=discovery.get("sum_unique_listing_hits") or 0,
            avg=discovery.get("average_unique_listing_hits_per_run") if discovery.get("average_unique_listing_hits_per_run") is not None else "n/a",
            factor=discovery.get("repeated_scan_factor") if discovery.get("repeated_scan_factor") is not None else "n/a",
        )
    )
    typer.echo(
        "- narrow coverage suspected: {value}".format(
            value="yes" if discovery.get("narrow_coverage_suspected") else "no",
        )
    )
    for reason in list(discovery.get("narrow_coverage_reasons") or []):
        _echo(f"  - {reason}")
    failing_catalogs = list(discovery.get("top_failing_catalogs") or [])
    if failing_catalogs:
        typer.echo("- top failing catalogs:")
        for item in failing_catalogs:
            typer.echo(
                "  - {catalog_path}: {failure_count} failures | latest {latest_failure_at} | 403s {http_403_count}".format(
                    **item,
                )
            )

    typer.echo("Acquisition:")
    typer.echo(
        "- latest status {status}".format(
            status=acquisition.get("latest_status") or "unknown",
        )
    )
    typer.echo(
        "- window healthy {healthy} | partial {partial} | degraded {degraded} | unknown {unknown}".format(
            **dict(acquisition.get("window_cycle_status_counts") or {}),
        )
    )
    typer.echo(
        "- probes direct {direct} | inconclusive {inconclusive} | degraded {degraded}".format(
            direct=probe_totals.get("direct_signal_count") or 0,
            inconclusive=probe_totals.get("inconclusive_probe_count") or 0,
            degraded=probe_totals.get("degraded_probe_count") or 0,
        )
    )
    typer.echo(
        "- anti-bot {anti_bot} | http errors {http_error} | transport errors {transport}".format(
            anti_bot=probe_totals.get("anti_bot_challenge_count") or 0,
            http_error=probe_totals.get("http_error_count") or 0,
            transport=probe_totals.get("transport_error_count") or 0,
        )
    )
    probe_reasons = list(acquisition.get("top_probe_reasons") or [])
    if probe_reasons:
        typer.echo("- top probe reasons:")
        for item in probe_reasons:
            typer.echo(f"  - {item['reason']}: {item['count']}")

    degraded_examples = list(acquisition.get("degraded_listing_examples") or [])
    if degraded_examples:
        typer.echo("- degraded listing examples:")
        for item in degraded_examples:
            _echo(
                "  - {listing_id} | count {degraded_probe_count} | {title}".format(
                    listing_id=item.get("listing_id"),
                    degraded_probe_count=item.get("degraded_probe_count"),
                    title=item.get("title") or "(untitled)",
                )
            )

    typer.echo("Freshness:")
    typer.echo(
        "- tracked {tracked_listings} | first-pass {first} | fresh {fresh} | aging {aging} | stale {stale}".format(
            tracked_listings=freshness_overall.get("tracked_listings") or 0,
            first=freshness_overall.get("first-pass-only") or 0,
            fresh=freshness_overall.get("fresh-followup") or 0,
            aging=freshness_overall.get("aging-followup") or 0,
            stale=freshness_overall.get("stale-followup") or 0,
        )
    )

    findings = list(report.get("findings") or [])
    if findings:
        typer.echo("Findings:")
        for item in findings:
            _echo(f"- {item}")

    recommendations = list(report.get("recommendations") or [])
    if recommendations:
        typer.echo("Recommendations:")
        for item in recommendations:
            _echo(f"- {item}")

    revisit = dict(report.get("revisit") or {})
    top_candidates = list(revisit.get("top_candidates") or [])
    if top_candidates:
        typer.echo("Revisit candidates:")
        for item in top_candidates:
            _echo(
                "- {listing_id} | score {priority_score} | {freshness_bucket} | obs {observation_count} | age {last_seen_age_hours}h | {title}".format(
                    listing_id=item.get("listing_id"),
                    priority_score=item.get("priority_score"),
                    freshness_bucket=item.get("freshness_bucket"),
                    observation_count=item.get("observation_count"),
                    last_seen_age_hours=item.get("last_seen_age_hours"),
                    title=item.get("title") or "(untitled)",
                )
            )


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


def _emit_platform_report(*, report: object, output_format: str) -> None:
    if output_format == "json":
        as_dict = getattr(report, "as_dict", None)
        if not callable(as_dict):
            raise typer.BadParameter("Platform report object does not expose as_dict().")
        typer.echo(json.dumps(as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_format != "table":
        raise typer.BadParameter("--format must be either 'table' or 'json'.")
    _render_platform_report(report)


def _render_platform_report(report: object) -> None:
    for line in render_platform_report_lines(report):
        typer.echo(line)


def _render_platform_system_status(label: str, status: object) -> None:
    typer.echo(f"{label}: {'ok' if getattr(status, 'ok', False) else 'fail'}")
    typer.echo(f"- endpoint: {getattr(status, 'endpoint', 'n/a')}")
    typer.echo(f"- migrations: {getattr(status, 'migration_dir', 'n/a')}")
    expected = getattr(status, 'expected_version', None)
    current = getattr(status, 'current_version', None)
    available = getattr(status, 'available_version', None)
    typer.echo(
        f"- schema: current {current if current is not None else 'n/a'} / expected {expected if expected is not None else 'n/a'} / available {available if available is not None else 'n/a'}"
    )
    applied_this_run = tuple(getattr(status, 'applied_this_run', ()) or ())
    if applied_this_run:
        typer.echo("- applied this run: " + ", ".join(f"V{int(version):03d}" for version in applied_this_run))
    pending = tuple(getattr(status, 'pending_versions', ()) or ())
    if pending:
        typer.echo("- pending: " + ", ".join(f"V{int(version):03d}" for version in pending))
    unexpected = tuple(getattr(status, 'unexpected_versions', ()) or ())
    if unexpected:
        typer.echo("- unexpected applied: " + ", ".join(f"V{int(version):03d}" for version in unexpected))
    mismatched = tuple(getattr(status, 'mismatched_checksums', ()) or ())
    if mismatched:
        typer.echo("- checksum mismatch: " + ", ".join(f"V{int(version):03d}" for version in mismatched))
    typer.echo(f"- detail: {getattr(status, 'detail', 'n/a')}")
    if getattr(status, 'error', None):
        typer.echo(f"- error: {getattr(status, 'error')}")


def _render_platform_object_storage_status(status: object) -> None:
    typer.echo(f"Object storage: {'ok' if getattr(status, 'ok', False) else 'fail'}")
    typer.echo(f"- endpoint: {getattr(status, 'endpoint_url', 'n/a')}")
    typer.echo(f"- bucket: {getattr(status, 'bucket', 'n/a')} ({getattr(status, 'region', 'n/a')})")
    typer.echo(
        "- bucket state: exists {exists} | created {created}".format(
            exists='yes' if getattr(status, 'bucket_exists', False) else 'no',
            created='yes' if getattr(status, 'bucket_created', False) else 'no',
        )
    )
    prefixes = dict(getattr(status, 'prefixes', {}) or {})
    if prefixes:
        typer.echo(
            "- prefixes: raw_events={raw_events} | manifests={manifests} | parquet={parquet}".format(
                raw_events=prefixes.get('raw_events') or 'n/a',
                manifests=prefixes.get('manifests') or 'n/a',
                parquet=prefixes.get('parquet') or 'n/a',
            )
        )
    marker_keys = tuple(getattr(status, 'ensured_marker_keys', ()) or ())
    if marker_keys:
        typer.echo("- ensured marker keys: " + ", ".join(marker_keys))
    probed = tuple(getattr(status, 'write_checked_prefixes', ()) or ())
    if probed:
        typer.echo("- write probes: " + ", ".join(probed))
    typer.echo(f"- detail: {getattr(status, 'detail', 'n/a')}")
    if getattr(status, 'error', None):
        typer.echo(f"- error: {getattr(status, 'error')}")


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
