from __future__ import annotations

import json
from pathlib import Path
import sys

import typer

from vinted_radar.dashboard import serve_dashboard
from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import build_listing_score_detail, build_market_summary, build_rankings, load_listing_scores
from vinted_radar.services.discovery import DiscoveryOptions, build_default_service
from vinted_radar.services.state_refresh import build_default_state_refresh_service
from vinted_radar.state_machine import evaluate_listing_state, summarize_state_evaluations

app = typer.Typer(add_completion=False, help="Local-first Vinted Homme/Femme radar CLI.")


@app.command()
def discover(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    page_limit: int = typer.Option(1, "--page-limit", min=1, help="How many catalog pages to fetch per leaf category."),
    max_leaf_categories: int | None = typer.Option(None, "--max-leaf-categories", min=1, help="Limit the number of leaf categories scanned in the run."),
    root_scope: str = typer.Option("both", "--root-scope", help="Which public root catalogs to scan: both, women, or men."),
    request_delay: float = typer.Option(0.5, "--request-delay", min=0.0, help="Delay between HTTP requests in seconds."),
    timeout_seconds: float = typer.Option(20.0, "--timeout-seconds", min=1.0, help="HTTP timeout per request in seconds."),
) -> None:
    service = build_default_service(db_path=str(db), timeout_seconds=timeout_seconds, request_delay=request_delay)
    try:
        report = service.run(
            DiscoveryOptions(
                page_limit=page_limit,
                max_leaf_categories=max_leaf_categories,
                root_scope=root_scope,
                request_delay=request_delay,
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


@app.command()
def coverage(
    db: Path = typer.Option(Path("data/vinted-radar.db"), "--db", help="SQLite database path."),
    run_id: str | None = typer.Option(None, "--run-id", help="Inspect a specific run instead of the latest one."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    with RadarRepository(db) as repository:
        summary = repository.coverage_summary(run_id)

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
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic evaluation."),
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    service = build_default_state_refresh_service(db_path=str(db), timeout_seconds=timeout_seconds, request_delay=request_delay)
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
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override for deterministic rendering."),
) -> None:
    typer.echo(f"Dashboard URL: http://{host}:{port}")
    typer.echo(f"Dashboard API: http://{host}:{port}/api/dashboard")
    typer.echo(f"Database: {db}")
    try:
        serve_dashboard(db_path=db, host=host, port=port, now=now)
    except KeyboardInterrupt:
        typer.echo("Dashboard server stopped.")


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


def _format_money(amount_cents: object, currency: object) -> str:
    if amount_cents is None:
        return "price n/a"
    return f"{int(amount_cents) / 100:.2f} {currency or ''}".strip()


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
    app()


if __name__ == "__main__":
    main()
