from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import html
import json
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import WSGIServer, make_server

from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import build_market_summary, build_rankings, load_listing_scores
from vinted_radar.state_machine import STATE_ORDER, summarize_state_evaluations

DEFAULT_LIMIT = 10
MAX_LIMIT = 24
SEGMENT_LIMIT = 6
DEFAULT_EXPLORER_PAGE_SIZE = 50
MAX_EXPLORER_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class DashboardFilters:
    root: str | None = None
    state: str | None = None
    catalog_id: int | None = None
    query: str | None = None
    limit: int = DEFAULT_LIMIT
    listing_id: int | None = None

    @classmethod
    def from_query_params(cls, params: dict[str, list[str]]) -> DashboardFilters:
        root = _normalized_filter_value(_first_value(params, "root"))
        state = _normalized_filter_value(_first_value(params, "state"))
        query = _clean_text(_first_value(params, "q"))
        return cls(
            root=root,
            state=state,
            catalog_id=_parse_int(_first_value(params, "catalog_id")),
            query=query,
            limit=_bounded_limit(_parse_int(_first_value(params, "limit"))),
            listing_id=_parse_int(_first_value(params, "listing_id")),
        )

    def to_query_dict(self, *, include_listing: bool = True) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.root:
            payload["root"] = self.root
        if self.state:
            payload["state"] = self.state
        if self.catalog_id is not None:
            payload["catalog_id"] = str(self.catalog_id)
        if self.query:
            payload["q"] = self.query
        if self.limit != DEFAULT_LIMIT:
            payload["limit"] = str(self.limit)
        if include_listing and self.listing_id is not None:
            payload["listing_id"] = str(self.listing_id)
        return payload


@dataclass(frozen=True, slots=True)
class ExplorerFilters:
    root: str | None = None
    catalog_id: int | None = None
    query: str | None = None
    page: int = 1
    page_size: int = DEFAULT_EXPLORER_PAGE_SIZE

    @classmethod
    def from_query_params(cls, params: dict[str, list[str]]) -> ExplorerFilters:
        return cls(
            root=_normalized_filter_value(_first_value(params, "root")),
            catalog_id=_parse_int(_first_value(params, "catalog_id")),
            query=_clean_text(_first_value(params, "q")),
            page=_bounded_page(_parse_int(_first_value(params, "page"))),
            page_size=_bounded_page_size(_parse_int(_first_value(params, "page_size"))),
        )

    def to_query_dict(self, *, overrides: dict[str, Any] | None = None) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.root:
            payload["root"] = self.root
        if self.catalog_id is not None:
            payload["catalog_id"] = str(self.catalog_id)
        if self.query:
            payload["q"] = self.query
        if self.page != 1:
            payload["page"] = str(self.page)
        if self.page_size != DEFAULT_EXPLORER_PAGE_SIZE:
            payload["page_size"] = str(self.page_size)
        for key, value in (overrides or {}).items():
            if value in {None, "", "all"}:
                payload.pop(key, None)
            else:
                payload[key] = str(value)
        return payload


@dataclass(slots=True)
class DashboardServerHandle:
    host: str
    port: int
    server: WSGIServer
    thread: Thread

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)


class DashboardApplication:
    def __init__(self, db_path: str | Path, *, now: str | None = None) -> None:
        self.db_path = Path(db_path)
        self.now = now

    def __call__(self, environ: dict[str, Any], start_response) -> list[bytes]:
        path = environ.get("PATH_INFO") or "/"
        params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)

        if path in {"", "/"}:
            filters = DashboardFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_dashboard_payload(repository, filters=filters, now=self.now)
            body = render_dashboard_html(payload)
            return _respond(start_response, "200 OK", body, content_type="text/html; charset=utf-8")

        if path == "/api/dashboard":
            filters = DashboardFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_dashboard_payload(repository, filters=filters, now=self.now)
            body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path == "/explorer":
            filters = ExplorerFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_explorer_payload(repository, filters=filters, now=self.now)
            body = render_explorer_html(payload)
            return _respond(start_response, "200 OK", body, content_type="text/html; charset=utf-8")

        if path == "/api/explorer":
            filters = ExplorerFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_explorer_payload(repository, filters=filters, now=self.now)
            body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path == "/api/runtime":
            with RadarRepository(self.db_path) as repository:
                payload = repository.runtime_status(limit=8)
            body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path.startswith("/api/listings/"):
            listing_id = _parse_int(path.rsplit("/", 1)[-1])
            if listing_id is None:
                return _respond(start_response, "404 Not Found", json.dumps({"error": "listing_not_found"}), content_type="application/json; charset=utf-8")
            with RadarRepository(self.db_path) as repository:
                listing_scores = load_listing_scores(repository, now=self.now)
                listing = _find_listing(listing_scores, listing_id)
                detail = build_listing_detail_payload(repository, listing, now=self.now) if listing is not None else None
            if detail is None:
                return _respond(start_response, "404 Not Found", json.dumps({"error": "listing_not_found", "listing_id": listing_id}), content_type="application/json; charset=utf-8")
            body = json.dumps(detail, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path == "/health":
            with RadarRepository(self.db_path) as repository:
                coverage = repository.coverage_summary()
                freshness = repository.freshness_summary(now=self.now)
                runtime_status = repository.runtime_status(limit=1)
            body = json.dumps(
                {
                    "status": "ok",
                    "db_path": str(self.db_path),
                    "has_run": coverage is not None,
                    "tracked_listings": int(freshness["overall"].get("tracked_listings") or 0),
                    "latest_runtime_cycle": runtime_status["latest_cycle"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        return _respond(start_response, "404 Not Found", "Not Found", content_type="text/plain; charset=utf-8")


def serve_dashboard(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    now: str | None = None,
) -> None:
    application = DashboardApplication(db_path, now=now)
    with make_server(host, port, application) as server:
        server.serve_forever()


def start_dashboard_server(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    now: str | None = None,
) -> DashboardServerHandle:
    application = DashboardApplication(db_path, now=now)
    server = make_server(host, port, application)
    thread = Thread(target=server.serve_forever, name=f"dashboard-{port}", daemon=True)
    thread.start()
    return DashboardServerHandle(host=host, port=port, server=server, thread=thread)


def build_dashboard_payload(
    repository: RadarRepository,
    *,
    filters: DashboardFilters,
    now: str | None = None,
) -> dict[str, Any]:
    generated_at = _generated_at(now)
    listing_scores = load_listing_scores(repository, now=now)
    coverage = repository.coverage_summary()
    freshness = repository.freshness_summary(now=now)
    runtime = repository.runtime_status(limit=8)
    overall_state = summarize_state_evaluations(listing_scores, generated_at=generated_at)
    filter_options = _build_filter_options(listing_scores)
    filtered_scores = _apply_filters(listing_scores, filters)

    if filtered_scores:
        market_summary = build_market_summary(filtered_scores, repository, now=generated_at, limit=min(filters.limit, SEGMENT_LIMIT))
    else:
        market_summary = _empty_market_summary(generated_at, filtered_scores)

    demand_rankings = build_rankings(filtered_scores, kind="demand", limit=filters.limit)
    premium_rankings = build_rankings(filtered_scores, kind="premium", limit=filters.limit)
    selected_listing = _select_listing(listing_scores, filtered_scores, filters, demand_rankings, premium_rankings)
    detail = build_listing_detail_payload(repository, selected_listing, now=now) if selected_listing is not None else None
    selected_listing_visible = selected_listing is not None and any(int(item["listing_id"]) == int(selected_listing["listing_id"]) for item in filtered_scores)

    return {
        "generated_at": generated_at,
        "db_path": str(repository.db_path),
        "latest_run": None if coverage is None else coverage["run"],
        "coverage": coverage,
        "freshness": freshness,
        "runtime": runtime,
        "overall_state": overall_state,
        "market_summary": market_summary,
        "filters": {
            "selected": {
                "root": filters.root or "all",
                "state": filters.state or "all",
                "catalog_id": filters.catalog_id,
                "q": filters.query or "",
                "limit": filters.limit,
                "listing_id": None if selected_listing is None else int(selected_listing["listing_id"]),
            },
            "available": filter_options,
        },
        "results": {
            "total_listings": len(listing_scores),
            "filtered_listings": len(filtered_scores),
            "selected_listing_visible": selected_listing_visible,
            "has_results": bool(filtered_scores),
            "empty_reason": None if filtered_scores else "No listings match the current dashboard filters.",
        },
        "rankings": {
            "demand": demand_rankings,
            "premium": premium_rankings,
        },
        "detail": detail,
        "diagnostics": {
            "dashboard_api": "/api/dashboard",
            "runtime_api": "/api/runtime",
            "listing_api": None if selected_listing is None else f"/api/listings/{selected_listing['listing_id']}",
            "explorer": "/explorer",
            "explorer_api": "/api/explorer",
            "health": "/health",
            "latest_failures": [] if coverage is None else coverage["failures"],
        },
    }


def build_explorer_payload(
    repository: RadarRepository,
    *,
    filters: ExplorerFilters,
    now: str | None = None,
) -> dict[str, Any]:
    generated_at = _generated_at(now)
    options = repository.explorer_filter_options()
    page = repository.listing_explorer_page(
        root=filters.root,
        catalog_id=filters.catalog_id,
        query=filters.query,
        page=filters.page,
        page_size=filters.page_size,
        now=now,
    )
    return {
        "generated_at": generated_at,
        "db_path": str(repository.db_path),
        "filters": {
            "selected": {
                "root": filters.root or "all",
                "catalog_id": filters.catalog_id,
                "q": filters.query or "",
                "page": page["page"],
                "page_size": page["page_size"],
            },
            "available": options,
        },
        "results": {
            "total_listings": page["total_listings"],
            "total_pages": page["total_pages"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_previous_page": page["has_previous_page"],
            "has_next_page": page["has_next_page"],
            "has_results": bool(page["items"]),
            "empty_reason": None if page["items"] else "No tracked listings match the current explorer filters.",
        },
        "items": page["items"],
        "diagnostics": {
            "explorer_api": "/api/explorer",
            "dashboard": "/",
        },
    }



def build_listing_detail_payload(
    repository: RadarRepository,
    listing: dict[str, Any] | None,
    *,
    now: str | None = None,
) -> dict[str, Any] | None:
    if listing is None:
        return None

    listing_id = int(listing["listing_id"])
    history = repository.listing_history(listing_id, now=now, limit=12)
    summary = None if history is None else history["summary"]
    latest_probe = listing.get("latest_probe")
    transitions = _build_transition_events(listing, summary, latest_probe)

    return {
        "listing_id": listing_id,
        "title": listing.get("title"),
        "canonical_url": listing.get("canonical_url"),
        "source_url": listing.get("source_url"),
        "image_url": listing.get("image_url"),
        "brand": listing.get("brand"),
        "size_label": listing.get("size_label"),
        "condition_label": listing.get("condition_label"),
        "price_display": _format_money(listing.get("price_amount_cents"), listing.get("price_currency")),
        "total_price_display": _format_money(listing.get("total_price_amount_cents"), listing.get("total_price_currency")),
        "root_title": listing.get("root_title"),
        "primary_catalog_path": listing.get("primary_catalog_path"),
        "state_code": listing.get("state_code"),
        "basis_kind": listing.get("basis_kind"),
        "confidence_label": listing.get("confidence_label"),
        "confidence_score": listing.get("confidence_score"),
        "demand_score": listing.get("demand_score"),
        "premium_score": listing.get("premium_score"),
        "freshness_bucket": listing.get("freshness_bucket"),
        "observation_count": listing.get("observation_count"),
        "follow_up_miss_count": listing.get("follow_up_miss_count"),
        "state_explanation": listing.get("state_explanation"),
        "score_explanation": listing.get("score_explanation"),
        "latest_probe": latest_probe,
        "history": history,
        "signals": [
            {"label": "Observation runs", "value": str(listing.get("observation_count") or 0)},
            {"label": "Freshness", "value": str(listing.get("freshness_bucket") or "unknown")},
            {"label": "Follow-up misses", "value": str(listing.get("follow_up_miss_count") or 0)},
            {"label": "Demand score", "value": _format_score(listing.get("demand_score"))},
            {"label": "Premium score", "value": _format_score(listing.get("premium_score"))},
        ],
        "transitions": transitions,
    }


def render_dashboard_html(payload: dict[str, Any]) -> str:
    selected = payload["filters"]["selected"]
    filters = DashboardFilters(
        root=None if selected["root"] == "all" else selected["root"],
        state=None if selected["state"] == "all" else selected["state"],
        catalog_id=selected["catalog_id"],
        query=selected["q"] or None,
        limit=int(selected["limit"]),
        listing_id=selected["listing_id"],
    )

    latest_run = payload.get("latest_run") or {}
    latest_runtime = payload["runtime"].get("latest_cycle") or {}
    freshness = payload["freshness"]["overall"]
    state_summary = payload["overall_state"]["overall"]
    results = payload["results"]
    detail = payload.get("detail")
    diagnostics = payload["diagnostics"]

    runtime_value = _escape(str(latest_runtime.get("status") or "No cycle yet"))
    runtime_items = [
        f"Mode {latest_runtime.get('mode', 'n/a')}",
        f"Phase {latest_runtime.get('phase', 'n/a')}",
        f"Discovery run {latest_runtime.get('discovery_run_id', 'n/a')}",
    ]
    if latest_runtime.get("last_error"):
        runtime_items.append(f"Last error {latest_runtime['last_error']}")

    cards = [
        _metric_card(
            "Latest run",
            _escape(str(latest_run.get("run_id") or "No run yet")),
            [
                f"Leaf catalogs {latest_run.get('scanned_leaf_catalogs', 0)} / {latest_run.get('total_leaf_catalogs', 0)}",
                f"Page scans {latest_run.get('successful_scans', 0)} ok · {latest_run.get('failed_scans', 0)} failed",
            ],
        ),
        _metric_card(
            "Runtime",
            runtime_value,
            runtime_items,
        ),
        _metric_card(
            "Freshness",
            _escape(str(freshness.get("tracked_listings", 0))),
            [
                f"Fresh follow-up {freshness.get('fresh-followup', 0)}",
                f"First pass only {freshness.get('first-pass-only', 0)}",
                f"Stale follow-up {freshness.get('stale-followup', 0)}",
            ],
        ),
        _metric_card(
            "Confidence",
            _escape(str(state_summary.get("high_confidence", 0))),
            [
                f"High confidence {state_summary.get('high_confidence', 0)}",
                f"Medium confidence {state_summary.get('medium_confidence', 0)}",
                f"Low confidence {state_summary.get('low_confidence', 0)}",
            ],
        ),
        _metric_card(
            "Filter lens",
            _escape(f"{results['filtered_listings']} / {results['total_listings']}"),
            [
                f"Root {selected['root']}",
                f"State {selected['state']}",
                f"Catalog {selected['catalog_id'] or 'all'}",
            ],
        ),
    ]

    failures_html = "".join(
        f"<li>{_escape(str(item.get('catalog_path') or 'Unknown catalog'))}: {_escape(str(item.get('error_message') or item.get('response_status') or 'unknown error'))}</li>"
        for item in diagnostics["latest_failures"][:5]
    )
    failure_block = (
        f"<section class=\"notice\"><h3>Latest scan failures</h3><ul>{failures_html}</ul></section>"
        if failures_html
        else ""
    )

    detail_block = _render_detail_panel(detail)
    demand_table = _render_rankings_table("Demand proof", payload["rankings"]["demand"], filters, selected_listing_id=selected["listing_id"])
    premium_table = _render_rankings_table("Premium proof", payload["rankings"]["premium"], filters, selected_listing_id=selected["listing_id"])

    empty_block = (
        f"<section class=\"empty-state\"><h3>No matching listings</h3><p>{_escape(results['empty_reason'])}</p></section>"
        if not results["has_results"]
        else ""
    )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Vinted Radar dashboard</title>
  <link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%2315100f'/%3E%3Cpath d='M17 46V18h12.5c9.6 0 16.5 5.3 16.5 14 0 8.5-6.5 14-15.9 14H17Zm8-6h4.3c5.1 0 8.7-3 8.7-8s-3.7-8-9-8H25v16Z' fill='%23d5a15b'/%3E%3C/svg%3E\">
  <style>
    :root {{
      --bg: #11100d;
      --panel: rgba(29, 25, 20, 0.92);
      --panel-strong: rgba(36, 31, 25, 0.96);
      --ink: #f3ece0;
      --muted: #c9baa4;
      --accent: #d5a15b;
      --accent-soft: rgba(213, 161, 91, 0.18);
      --line: rgba(255,255,255,0.08);
      --danger: #d46a5f;
      --success: #7cc083;
      --shadow: 0 24px 70px rgba(0,0,0,0.42);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(213, 161, 91, 0.18), transparent 26%),
        radial-gradient(circle at bottom right, rgba(120, 192, 131, 0.10), transparent 24%),
        linear-gradient(180deg, #15120f 0%, #0f0d0b 100%);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      min-height: 100vh;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
      background-size: 22px 22px;
      mask-image: radial-gradient(circle at center, black, transparent 82%);
      opacity: 0.25;
    }}
    .shell {{ max-width: 1500px; margin: 0 auto; padding: 32px; position: relative; }}
    .hero {{ display: grid; gap: 22px; margin-bottom: 24px; }}
    .hero-header {{
      display: grid;
      gap: 10px;
      padding: 28px 30px;
      background: linear-gradient(135deg, rgba(213,161,91,0.16), rgba(255,255,255,0.03));
      border: 1px solid rgba(213,161,91,0.2);
      border-radius: 28px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: 0.22em; font-size: 12px; color: var(--accent); }}
    h1, h2, h3 {{ font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif; margin: 0; font-weight: 600; }}
    h1 {{ font-size: clamp(2.1rem, 4vw, 4rem); line-height: 0.98; max-width: 14ch; }}
    .subhead {{ color: var(--muted); max-width: 78ch; line-height: 1.6; }}
    .cards {{ display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }}
    .card, .panel, .metric, .notice, .empty-state {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}
    .metric {{ padding: 22px; }}
    .metric-label {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; font-size: 11px; margin-bottom: 14px; }}
    .metric-value {{ font-size: 2rem; font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif; margin-bottom: 8px; }}
    .metric ul {{ list-style: none; padding: 0; margin: 0; color: var(--muted); display: grid; gap: 6px; font-size: 0.95rem; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.9fr); gap: 22px; align-items: start; }}
    .stack {{ display: grid; gap: 22px; }}
    .panel {{ padding: 22px; }}
    .panel-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: end; margin-bottom: 18px; }}
    .panel-header p {{ margin: 4px 0 0; color: var(--muted); }}
    .filters {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
    label {{ display: grid; gap: 8px; color: var(--muted); font-size: 0.92rem; }}
    input, select {{
      width: 100%;
      border: 1px solid rgba(255,255,255,0.09);
      border-radius: 14px;
      background: rgba(255,255,255,0.04);
      color: var(--ink);
      padding: 12px 14px;
      font: inherit;
    }}
    .actions {{ display: flex; gap: 10px; align-items: end; flex-wrap: wrap; }}
    .button {{
      appearance: none;
      border: 1px solid rgba(213,161,91,0.35);
      border-radius: 999px;
      padding: 12px 16px;
      background: linear-gradient(135deg, rgba(213,161,91,0.26), rgba(213,161,91,0.08));
      color: var(--ink);
      cursor: pointer;
      text-decoration: none;
      font-weight: 600;
    }}
    .button.secondary {{ background: rgba(255,255,255,0.03); border-color: var(--line); color: var(--muted); }}
    .segment-grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .segment {{ padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)); border: 1px solid var(--line); }}
    .segment small {{ display: block; margin-top: 10px; color: var(--muted); line-height: 1.45; }}
    .table-wrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 18px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{ padding: 13px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); vertical-align: top; }}
    th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--muted); background: rgba(255,255,255,0.02); }}
    tr.selected {{ background: var(--accent-soft); }}
    .pill {{ display: inline-flex; padding: 5px 10px; border-radius: 999px; font-size: 12px; border: 1px solid rgba(255,255,255,0.09); background: rgba(255,255,255,0.04); }}
    .pill.active {{ color: var(--success); }}
    .pill.sold_observed, .pill.sold_probable {{ color: var(--accent); }}
    .pill.deleted {{ color: var(--danger); }}
    .detail {{ position: sticky; top: 24px; display: grid; gap: 18px; background: var(--panel-strong); }}
    .detail h2 {{ font-size: 2rem; line-height: 1.03; }}
    .detail-meta {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .signal {{ padding: 12px 14px; border-radius: 16px; background: rgba(255,255,255,0.03); border: 1px solid var(--line); }}
    .signal-label {{ display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 6px; }}
    .bullet-list {{ margin: 0; padding-left: 18px; color: var(--muted); line-height: 1.55; }}
    .timeline {{ display: grid; gap: 12px; }}
    .timeline-item {{ padding: 14px 16px; border-radius: 16px; background: rgba(255,255,255,0.03); border: 1px solid var(--line); }}
    .timeline-item strong {{ display: block; margin-bottom: 6px; }}
    .notice, .empty-state {{ padding: 18px 20px; }}
    a {{ color: inherit; }}
    .link-muted {{ color: var(--muted); }}
    .api-links {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: 0.92rem; color: var(--muted); }}
    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .detail {{ position: static; }}
    }}
    @media (max-width: 640px) {{
      .shell {{ padding: 18px; }}
      .hero-header, .panel, .metric {{ padding: 18px; }}
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class=\"shell\">
    <section class=\"hero\">
      <div class=\"hero-header\">
        <span class=\"eyebrow\">Local radar · evidence first</span>
        <h1>Market summary first. Listing proof immediately underneath.</h1>
        <p class=\"subhead\">This dashboard is a thin local product surface over the current Vinted Radar state, freshness, and scoring outputs. It does not invent new logic: every segment card, ranking row, and detail explanation comes from the same repository-backed payloads exposed by the CLI diagnostics.</p>
      </div>
      <div class=\"cards\">{''.join(cards)}</div>
    </section>

    <section class=\"layout\">
      <div class=\"stack\">
        <section class=\"panel\">
          <div class=\"panel-header\">
            <div>
              <h2>Filter lens</h2>
              <p>Keep the market read tight without disconnecting it from the evidence base.</p>
            </div>
          </div>
          {_render_filter_form(payload)}
        </section>

        <section class=\"panel\">
          <div class=\"panel-header\">
            <div>
              <h2>Performing segments</h2>
              <p>Segments with the strongest combined demand and premium posture in the current filtered lens.</p>
            </div>
          </div>
          {_render_segment_cards(payload['market_summary']['performing_segments'], empty_label='No performing segments match the current filters.')}
        </section>

        <section class=\"panel\">
          <div class=\"panel-header\">
            <div>
              <h2>Rising segments</h2>
              <p>Recent arrivals, visible deltas, and sold-like pressure from the same filtered evidence base.</p>
            </div>
          </div>
          {_render_segment_cards(payload['market_summary']['rising_segments'], empty_label='No rising segments match the current filters.')}
        </section>

        {failure_block}
        {empty_block}

        <section class=\"panel\">{demand_table}</section>
        <section class=\"panel\">{premium_table}</section>
      </div>

      <aside class=\"panel detail\">{detail_block}</aside>
    </section>

    <section class=\"panel\" style=\"margin-top:22px;\">
      <div class=\"panel-header\">
        <div>
          <h2>Diagnostics</h2>
          <p>Truthful JSON endpoints for debugging the exact payload that rendered this page.</p>
        </div>
      </div>
      <div class=\"api-links\">
        <a class=\"button secondary\" href=\"{_escape(diagnostics['dashboard_api'] + _suffix_query(filters, include_listing=True))}\">Dashboard payload</a>
        <a class=\"button secondary\" href=\"{_escape(diagnostics['runtime_api'])}\">Runtime payload</a>
        <a class=\"button secondary\" href=\"{_escape(diagnostics['explorer'])}\">Explorer</a>
        <a class=\"button secondary\" href=\"{_escape(diagnostics['explorer_api'])}\">Explorer payload</a>
        <a class=\"button secondary\" href=\"{_escape(diagnostics['health'])}\">Health</a>
        {'' if diagnostics['listing_api'] is None else f'<a class="button secondary" href="{_escape(diagnostics["listing_api"])}">Selected listing payload</a>'}
      </div>
    </section>
  </main>
</body>
</html>"""


def render_explorer_html(payload: dict[str, Any]) -> str:
    selected = payload["filters"]["selected"]
    available = payload["filters"]["available"]
    results = payload["results"]
    diagnostics = payload["diagnostics"]
    items = payload["items"]
    filters = ExplorerFilters(
        root=None if selected["root"] == "all" else selected["root"],
        catalog_id=selected["catalog_id"],
        query=selected["q"] or None,
        page=int(selected["page"]),
        page_size=int(selected["page_size"]),
    )

    root_options = "".join(_option_html(item["value"], item["label"], selected["root"]) for item in available["roots"])
    catalog_options = "".join(_option_html(item["value"], item["label"], selected["catalog_id"]) for item in available["catalogs"])
    page_size_options = "".join(_option_html(str(value), str(value), selected["page_size"]) for value in (25, 50, 100))

    if items:
        rows_html = "".join(
            f"""
            <tr>
              <td><strong>{int(item['listing_id'])}</strong></td>
              <td>
                <div><strong>{_escape(str(item.get('title') or '(untitled)'))}</strong></div>
                <div class=\"link-muted\">{_escape(str(item.get('brand') or 'Unknown brand'))}</div>
              </td>
              <td>{_escape(str(item.get('primary_catalog_path') or item.get('root_title') or 'Unknown'))}</td>
              <td>{_escape(str(item.get('freshness_bucket') or 'unknown'))}</td>
              <td>{_escape(_format_money(item.get('price_amount_cents'), item.get('price_currency')))}</td>
              <td>{_escape(str(item.get('observation_count') or 0))}</td>
              <td>{_escape(str(item.get('last_seen_at') or 'unknown'))}</td>
              <td>
                <a class=\"button secondary\" href=\"{_escape('/' + _suffix_query(DashboardFilters(listing_id=int(item['listing_id'])), include_listing=True))}\">Inspect</a>
              </td>
            </tr>
            """
            for item in items
        )
    else:
        rows_html = "<tr><td colspan='8'>No tracked listings match the current explorer filters.</td></tr>"

    previous_href = _explorer_query(filters, overrides={"page": max(filters.page - 1, 1)})
    next_href = _explorer_query(filters, overrides={"page": filters.page + 1})

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Vinted Radar explorer</title>
  <style>
    :root {{
      --bg: #11100d;
      --panel: rgba(29, 25, 20, 0.92);
      --ink: #f3ece0;
      --muted: #c9baa4;
      --accent: #d5a15b;
      --line: rgba(255,255,255,0.08);
      --shadow: 0 24px 70px rgba(0,0,0,0.42);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); background: linear-gradient(180deg, #15120f 0%, #0f0d0b 100%); font-family: \"Avenir Next\", \"Segoe UI\", sans-serif; min-height: 100vh; }}
    .shell {{ max-width: 1480px; margin: 0 auto; padding: 32px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); padding: 22px; margin-bottom: 22px; }}
    h1, h2 {{ font-family: \"Iowan Old Style\", \"Palatino Linotype\", Georgia, serif; margin: 0; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: 0.22em; font-size: 12px; color: var(--accent); }}
    .subhead, .link-muted {{ color: var(--muted); }}
    .filters {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); align-items: end; }}
    label {{ display: grid; gap: 8px; color: var(--muted); font-size: 0.92rem; }}
    input, select {{ width: 100%; border: 1px solid rgba(255,255,255,0.09); border-radius: 14px; background: rgba(255,255,255,0.04); color: var(--ink); padding: 12px 14px; font: inherit; }}
    .actions, .api-links, .pagination {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .button {{ appearance: none; border: 1px solid rgba(213,161,91,0.35); border-radius: 999px; padding: 12px 16px; background: linear-gradient(135deg, rgba(213,161,91,0.26), rgba(213,161,91,0.08)); color: var(--ink); cursor: pointer; text-decoration: none; font-weight: 600; }}
    .button.secondary {{ background: rgba(255,255,255,0.03); border-color: var(--line); color: var(--muted); }}
    .button.disabled {{ opacity: 0.45; pointer-events: none; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-top: 16px; }}
    .stat {{ padding: 16px; border-radius: 16px; border: 1px solid var(--line); background: rgba(255,255,255,0.03); }}
    .table-wrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 18px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
    th, td {{ padding: 13px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); vertical-align: top; }}
    th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--muted); background: rgba(255,255,255,0.02); }}
  </style>
</head>
<body>
  <main class=\"shell\">
    <section class=\"panel\">
      <span class=\"eyebrow\">SQL-backed explorer</span>
      <h1>Listing explorer separated from the dashboard summary.</h1>
      <p class=\"subhead\">This surface pages tracked listings directly from SQLite instead of loading the full scored corpus into memory. Use the main dashboard for summary and ranking proof; use this explorer for broad listing browsing.</p>
      <div class=\"api-links\" style=\"margin-top:16px;\">
        <a class=\"button secondary\" href=\"/\">Back to dashboard</a>
        <a class=\"button secondary\" href=\"{_escape(diagnostics['explorer_api'] + _explorer_suffix_query(filters))}\">Explorer payload</a>
      </div>
    </section>

    <section class=\"panel\">
      <form method=\"get\" class=\"filters\">
        <label>
          Root
          <select name=\"root\">{root_options}</select>
        </label>
        <label>
          Catalog
          <select name=\"catalog_id\">{catalog_options}</select>
        </label>
        <label>
          Search
          <input type=\"search\" name=\"q\" value=\"{_escape(selected['q'])}\" placeholder=\"Title, brand, listing ID\">
        </label>
        <label>
          Page size
          <select name=\"page_size\">{page_size_options}</select>
        </label>
        <input type=\"hidden\" name=\"page\" value=\"1\">
        <div class=\"actions\">
          <button class=\"button\" type=\"submit\">Apply filters</button>
          <a class=\"button secondary\" href=\"/explorer\">Reset</a>
        </div>
      </form>
      <div class=\"stats\">
        <div class=\"stat\"><strong>{results['total_listings']}</strong><br><span class=\"link-muted\">matching tracked listings</span></div>
        <div class=\"stat\"><strong>{results['page']}</strong><br><span class=\"link-muted\">current page / {results['total_pages'] or 0}</span></div>
        <div class=\"stat\"><strong>{available['tracked_listings']}</strong><br><span class=\"link-muted\">tracked listings in DB</span></div>
      </div>
    </section>

    <section class=\"panel\">
      <div class=\"table-wrap\">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Listing</th>
              <th>Catalog</th>
              <th>Freshness</th>
              <th>Price</th>
              <th>Obs</th>
              <th>Last seen</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
      <div class=\"pagination\" style=\"margin-top:16px;\">
        <a class=\"button secondary{' disabled' if not results['has_previous_page'] else ''}\" href=\"{_escape(previous_href)}\">Previous</a>
        <span class=\"link-muted\">Page {results['page']} of {results['total_pages'] or 1}</span>
        <a class=\"button secondary{' disabled' if not results['has_next_page'] else ''}\" href=\"{_escape(next_href)}\">Next</a>
      </div>
    </section>
  </main>
</body>
</html>"""


def _render_filter_form(payload: dict[str, Any]) -> str:
    selected = payload["filters"]["selected"]
    available = payload["filters"]["available"]
    root_options = "".join(
        _option_html(item["value"], item["label"], selected["root"]) for item in available["roots"]
    )
    state_options = "".join(
        _option_html(item["value"], item["label"], selected["state"]) for item in available["states"]
    )
    catalog_options = "".join(
        _option_html(item["value"], item["label"], selected["catalog_id"]) for item in available["catalogs"]
    )
    return f"""
      <form method=\"get\" class=\"filters\">
        <label>
          Root
          <select name=\"root\">{root_options}</select>
        </label>
        <label>
          State
          <select name=\"state\">{state_options}</select>
        </label>
        <label>
          Catalog
          <select name=\"catalog_id\">{catalog_options}</select>
        </label>
        <label>
          Search
          <input type=\"search\" name=\"q\" value=\"{_escape(selected['q'])}\" placeholder=\"Title, brand, listing ID\">
        </label>
        <label>
          Ranking rows
          <select name=\"limit\">{''.join(_option_html(str(value), str(value), selected['limit']) for value in (5, 10, 15, 24))}</select>
        </label>
        <div class=\"actions\">
          <button class=\"button\" type=\"submit\">Apply filters</button>
          <a class=\"button secondary\" href=\"/\">Reset</a>
        </div>
      </form>
    """


def _render_segment_cards(segments: list[dict[str, Any]], *, empty_label: str) -> str:
    if not segments:
        return f"<div class=\"empty-state\"><p>{_escape(empty_label)}</p></div>"
    cards = []
    for segment in segments:
        cards.append(
            f"""
            <article class=\"segment\">
              <h3>{_escape(str(segment.get('catalog_path') or 'Unknown segment'))}</h3>
              <small>
                tracked {segment.get('tracked_listings', 0)} · demand {_format_score(segment.get('avg_demand_score'))} · premium {_format_score(segment.get('avg_premium_score'))}<br>
                sold-like {segment.get('sold_like_count', 0)} · recent arrivals {segment.get('recent_arrivals', 0)} · delta {segment.get('visible_delta', 0)}
              </small>
            </article>
            """
        )
    return f"<div class=\"segment-grid\">{''.join(cards)}</div>"


def _render_rankings_table(
    title: str,
    rows: list[dict[str, Any]],
    filters: DashboardFilters,
    *,
    selected_listing_id: int | None,
) -> str:
    if not rows:
        return f"<div class=\"panel-header\"><div><h2>{_escape(title)}</h2><p>No rows match the current filters.</p></div></div>"

    score_field = "demand_score" if "Demand" in title else "premium_score"
    table_rows: list[str] = []
    for row in rows:
        listing_id = int(row["listing_id"])
        href = "/" + _suffix_query(filters, include_listing=False, overrides={"listing_id": listing_id})
        selected_class = " selected" if selected_listing_id == listing_id else ""
        state_code = str(row.get("state_code") or "unknown")
        table_rows.append(
            f"""
            <tr class=\"{selected_class.strip()}\">
              <td><strong>{listing_id}</strong></td>
              <td>
                <div><strong>{_escape(str(row.get('title') or '(untitled)'))}</strong></div>
                <div class=\"link-muted\">{_escape(str(row.get('brand') or 'Unknown brand'))}</div>
              </td>
              <td>{_escape(str(row.get('primary_catalog_path') or row.get('root_title') or 'Unknown'))}</td>
              <td><span class=\"pill {state_code}\">{_escape(state_code)}</span></td>
              <td>{_escape(_format_money(row.get('price_amount_cents'), row.get('price_currency')))}</td>
              <td>{_escape(_format_score(row.get(score_field)))}</td>
              <td>{_escape(_format_score(row.get('demand_score')))}</td>
              <td><a class=\"button secondary\" href=\"{_escape(href)}\">Inspect</a></td>
            </tr>
            """
        )

    return f"""
      <div class=\"panel-header\">
        <div>
          <h2>{_escape(title)}</h2>
          <p>Concrete ranking proof tied back to the current filtered evidence base.</p>
        </div>
      </div>
      <div class=\"table-wrap\">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Listing</th>
              <th>Catalog</th>
              <th>State</th>
              <th>Price</th>
              <th>{_escape(score_field.replace('_', ' '))}</th>
              <th>Demand</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {''.join(table_rows)}
          </tbody>
        </table>
      </div>
    """


def _render_detail_panel(detail: dict[str, Any] | None) -> str:
    if detail is None:
        return "<div><h2>No detail selected</h2><p class=\"subhead\">Pick a ranking row to inspect its history, score factors, and inference basis.</p></div>"

    score_context = detail["score_explanation"].get("context") if isinstance(detail.get("score_explanation"), dict) else None
    score_context_html = (
        f"<li>Context { _escape(str(score_context.get('label') or 'unknown')) } · peers {score_context.get('sample_size', 0)} · percentile {score_context.get('price_percentile')}</li>"
        if score_context is not None
        else "<li>No trustworthy premium context sample for this listing yet.</li>"
    )
    history_rows = detail["history"]["timeline"] if detail.get("history") else []
    history_html = "".join(
        f"<div class=\"timeline-item\"><strong>{_escape(str(row.get('observed_at') or 'unknown'))}</strong><span>{_escape(_format_money(row.get('price_amount_cents'), row.get('price_currency')))} · {_escape(str(row.get('catalog_path') or 'Unknown catalog'))} · sightings {row.get('sighting_count', 0)}</span></div>"
        for row in history_rows
    ) or "<div class=\"timeline-item\"><span>No observation timeline recorded.</span></div>"
    transitions_html = "".join(
        f"<div class=\"timeline-item\"><strong>{_escape(str(item['label']))}</strong><span>{_escape(str(item['timestamp']))}</span><br><span>{_escape(str(item['description']))}</span></div>"
        for item in detail["transitions"]
    )

    return f"""
      <div>
        <span class=\"eyebrow\">Listing detail</span>
        <h2>{_escape(str(detail.get('title') or '(untitled)'))}</h2>
        <p class=\"subhead\">{_escape(str(detail.get('primary_catalog_path') or detail.get('root_title') or 'Unknown catalog'))}</p>
      </div>
      <div class=\"detail-meta\">
        <span class=\"pill { _escape(str(detail.get('state_code') or 'unknown')) }\">{_escape(str(detail.get('state_code') or 'unknown'))}</span>
        <span class=\"pill\">{_escape(str(detail.get('basis_kind') or 'unknown'))}</span>
        <span class=\"pill\">{_escape(str(detail.get('confidence_label') or 'unknown'))} confidence</span>
      </div>
      <div class=\"detail-grid\">
        {''.join(f'<div class="signal"><span class="signal-label">{_escape(item["label"])}</span>{_escape(str(item["value"]))}</div>' for item in detail['signals'])}
      </div>
      <div class=\"signal\">
        <span class=\"signal-label\">Public fields</span>
        <strong>{_escape(str(detail.get('price_display') or 'price n/a'))}</strong><br>
        <span class=\"link-muted\">Brand { _escape(str(detail.get('brand') or 'Unknown')) } · Size { _escape(str(detail.get('size_label') or 'n/a')) } · Condition { _escape(str(detail.get('condition_label') or 'n/a')) }</span>
      </div>
      <div>
        <h3>Inference basis</h3>
        <ul class=\"bullet-list\">{''.join(f'<li>{_escape(reason)}</li>' for reason in detail['state_explanation']['reasons'])}</ul>
      </div>
      <div>
        <h3>Score context</h3>
        <ul class=\"bullet-list\">
          {''.join(f'<li>{_escape(name.replace("_", " "))}: {_format_score(value)}</li>' for name, value in detail['score_explanation']['factors'].items())}
          {score_context_html}
        </ul>
      </div>
      <div>
        <h3>Transition path</h3>
        <div class=\"timeline\">{transitions_html}</div>
      </div>
      <div>
        <h3>Observation timeline</h3>
        <div class=\"timeline\">{history_html}</div>
      </div>
      <div class=\"api-links\">
        {'' if not detail.get('canonical_url') else f'<a class="button secondary" href="{_escape(str(detail["canonical_url"]))}" target="_blank" rel="noreferrer">Open canonical listing</a>'}
      </div>
    """


def _apply_filters(listing_scores: list[dict[str, Any]], filters: DashboardFilters) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    query = (filters.query or "").lower()
    for item in listing_scores:
        if filters.root and str(item.get("root_title") or "") != filters.root:
            continue
        if filters.state and str(item.get("state_code") or "") != filters.state:
            continue
        if filters.catalog_id is not None and int(item.get("primary_catalog_id") or -1) != filters.catalog_id:
            continue
        if query:
            haystack = " ".join(
                [
                    str(item.get("listing_id") or ""),
                    str(item.get("title") or ""),
                    str(item.get("brand") or ""),
                    str(item.get("primary_catalog_path") or ""),
                ]
            ).lower()
            if query not in haystack:
                continue
        filtered.append(item)
    return filtered


def _build_filter_options(listing_scores: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    roots: dict[str, int] = {}
    states: dict[str, int] = {}
    catalogs: dict[int, dict[str, Any]] = {}
    for item in listing_scores:
        root_title = str(item.get("root_title") or "Unknown")
        state_code = str(item.get("state_code") or "unknown")
        roots[root_title] = roots.get(root_title, 0) + 1
        states[state_code] = states.get(state_code, 0) + 1
        catalog_id = item.get("primary_catalog_id")
        if catalog_id is not None:
            entry = catalogs.setdefault(
                int(catalog_id),
                {
                    "value": str(catalog_id),
                    "catalog_id": int(catalog_id),
                    "label": str(item.get("primary_catalog_path") or item.get("root_title") or f"catalog:{catalog_id}"),
                    "count": 0,
                },
            )
            entry["count"] += 1

    root_options = [{"value": "all", "label": "All roots"}] + [
        {"value": root, "label": f"{root} ({count})"}
        for root, count in sorted(roots.items())
    ]
    state_options = [{"value": "all", "label": "All states"}] + [
        {"value": state, "label": f"{state} ({states[state]})"}
        for state in STATE_ORDER
        if state in states
    ]
    catalog_options = [{"value": "", "label": "All catalogs"}] + sorted(catalogs.values(), key=lambda item: str(item["label"]))
    return {"roots": root_options, "states": state_options, "catalogs": catalog_options}


def _select_listing(
    listing_scores: list[dict[str, Any]],
    filtered_scores: list[dict[str, Any]],
    filters: DashboardFilters,
    demand_rankings: list[dict[str, Any]],
    premium_rankings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if filters.listing_id is not None:
        explicit = _find_listing(listing_scores, filters.listing_id)
        if explicit is not None:
            return explicit
    for source in (demand_rankings, premium_rankings, filtered_scores, listing_scores):
        if source:
            return source[0]
    return None


def _find_listing(listing_scores: list[dict[str, Any]], listing_id: int) -> dict[str, Any] | None:
    for item in listing_scores:
        if int(item["listing_id"]) == listing_id:
            return item
    return None


def _build_transition_events(
    listing: dict[str, Any],
    history_summary: dict[str, Any] | None,
    latest_probe: dict[str, Any] | None,
) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    catalog_path = str(listing.get("primary_catalog_path") or listing.get("root_title") or "the tracked catalog")
    if history_summary is not None:
        events.append(
            {
                "label": "First seen",
                "timestamp": str(history_summary.get("first_seen_at") or "unknown"),
                "description": f"Entered tracking from {catalog_path}.",
            }
        )
        events.append(
            {
                "label": "Last observed",
                "timestamp": str(history_summary.get("last_seen_at") or "unknown"),
                "description": f"Last visible card snapshot in {catalog_path} ({history_summary.get('freshness_bucket', 'unknown')}).",
            }
        )
    follow_up_miss_count = int(listing.get("follow_up_miss_count") or 0)
    if follow_up_miss_count:
        events.append(
            {
                "label": "Follow-up misses",
                "timestamp": str(listing.get("state_explanation", {}).get("evaluated_at") or "unknown"),
                "description": f"Missed {follow_up_miss_count} successful primary-catalog rescans after the last sighting.",
            }
        )
    if isinstance(latest_probe, dict):
        events.append(
            {
                "label": "Latest probe",
                "timestamp": str(latest_probe.get("probed_at") or "unknown"),
                "description": f"Probe outcome {latest_probe.get('probe_outcome') or 'unknown'} with HTTP {latest_probe.get('response_status') or 'n/a'}.",
            }
        )
    events.append(
        {
            "label": "Current state",
            "timestamp": str(listing.get("state_explanation", {}).get("evaluated_at") or "unknown"),
            "description": f"Classified as {listing.get('state_code')} on a {listing.get('basis_kind')} basis with {listing.get('confidence_label')} confidence.",
        }
    )
    return events


def _empty_market_summary(generated_at: str, filtered_scores: list[dict[str, Any]]) -> dict[str, Any]:
    overall = summarize_state_evaluations(filtered_scores, generated_at=generated_at)["overall"] if filtered_scores else {
        "tracked_listings": 0,
        **{state: 0 for state in STATE_ORDER},
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "observed_basis": 0,
        "inferred_basis": 0,
        "unknown_basis": 0,
    }
    return {
        "generated_at": generated_at,
        "overall": overall,
        "performing_segments": [],
        "rising_segments": [],
    }


def _metric_card(label: str, value: str, items: list[str]) -> str:
    return f"<article class=\"metric\"><div class=\"metric-label\">{label}</div><div class=\"metric-value\">{value}</div><ul>{''.join(f'<li>{_escape(item)}</li>' for item in items)}</ul></article>"


def _option_html(value: str | int | None, label: str, selected_value: str | int | None) -> str:
    current = "" if value is None else str(value)
    selected = " selected" if current == ("" if selected_value is None else str(selected_value)) else ""
    return f"<option value=\"{_escape(current)}\"{selected}>{_escape(label)}</option>"


def _suffix_query(
    filters: DashboardFilters,
    *,
    include_listing: bool,
    overrides: dict[str, Any] | None = None,
) -> str:
    params = filters.to_query_dict(include_listing=include_listing)
    for key, value in (overrides or {}).items():
        if value in {None, "", "all"}:
            params.pop(key, None)
        else:
            params[key] = str(value)
    if not params:
        return ""
    return "?" + urlencode(params)


def _explorer_query(filters: ExplorerFilters, *, overrides: dict[str, Any] | None = None) -> str:
    params = filters.to_query_dict(overrides=overrides)
    if not params:
        return "/explorer"
    return "/explorer?" + urlencode(params)


def _explorer_suffix_query(filters: ExplorerFilters, *, overrides: dict[str, Any] | None = None) -> str:
    params = filters.to_query_dict(overrides=overrides)
    if not params:
        return ""
    return "?" + urlencode(params)


def _respond(start_response, status: str, body: str, *, content_type: str) -> list[bytes]:
    encoded = body.encode("utf-8")
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(encoded)))])
    return [encoded]


def _first_value(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    if not values:
        return None
    return values[0]


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bounded_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _bounded_page(value: int | None) -> int:
    if value is None:
        return 1
    return max(1, value)


def _bounded_page_size(value: int | None) -> int:
    if value is None:
        return DEFAULT_EXPLORER_PAGE_SIZE
    return max(1, min(value, MAX_EXPLORER_PAGE_SIZE))


def _normalized_filter_value(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned in {None, "", "all"}:
        return None
    return cleaned


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _generated_at(now: str | None) -> str:
    if now is not None:
        return now
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _format_money(amount_cents: Any, currency: Any) -> str:
    if amount_cents is None:
        return "price n/a"
    return f"{int(amount_cents) / 100:.2f} {currency or ''}".strip()


def _format_score(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)
