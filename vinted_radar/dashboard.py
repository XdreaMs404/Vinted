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
from vinted_radar.scoring import load_listing_scores
from vinted_radar.state_machine import STATE_ORDER

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
    brand: str | None = None
    condition: str | None = None
    query: str | None = None
    sort: str = "last_seen_desc"
    page: int = 1
    page_size: int = DEFAULT_EXPLORER_PAGE_SIZE

    @classmethod
    def from_query_params(cls, params: dict[str, list[str]]) -> ExplorerFilters:
        return cls(
            root=_normalized_filter_value(_first_value(params, "root")),
            catalog_id=_parse_int(_first_value(params, "catalog_id")),
            brand=_normalized_filter_value(_first_value(params, "brand")),
            condition=_normalized_filter_value(_first_value(params, "condition")),
            query=_clean_text(_first_value(params, "q")),
            sort=_bounded_explorer_sort(_first_value(params, "sort")),
            page=_bounded_page(_parse_int(_first_value(params, "page"))),
            page_size=_bounded_page_size(_parse_int(_first_value(params, "page_size"))),
        )

    def to_query_dict(self, *, overrides: dict[str, Any] | None = None) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.root:
            payload["root"] = self.root
        if self.catalog_id is not None:
            payload["catalog_id"] = str(self.catalog_id)
        if self.brand:
            payload["brand"] = self.brand
        if self.condition:
            payload["condition"] = self.condition
        if self.query:
            payload["q"] = self.query
        if self.sort != "last_seen_desc":
            payload["sort"] = self.sort
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
    comparison_limit = max(1, min(int(filters.limit), SEGMENT_LIMIT))
    overview = repository.overview_snapshot(now=now, comparison_limit=comparison_limit)
    featured_page = repository.listing_explorer_page(page=1, page_size=4, sort="last_seen_desc", now=now)
    featured_listings = [_serialize_overview_listing_item(item) for item in featured_page["items"]]

    return {
        "generated_at": overview["generated_at"],
        "db_path": overview["db_path"],
        "summary": overview["summary"],
        "comparisons": overview["comparisons"],
        "coverage": overview["coverage"],
        "runtime": overview["runtime"],
        "request": {
            "comparison_limit": comparison_limit,
            "primary_payload_source": "repository.overview_snapshot",
            "legacy_query_filters": {
                "root": filters.root,
                "state": filters.state,
                "catalog_id": filters.catalog_id,
                "q": filters.query,
                "listing_id": filters.listing_id,
            },
        },
        "honesty_notes": _build_honesty_notes(overview),
        "featured_listings": featured_listings,
        "diagnostics": {
            "home": "/",
            "dashboard_api": "/api/dashboard",
            "runtime_api": "/api/runtime",
            "explorer": "/explorer",
            "explorer_api": "/api/explorer",
            "health": "/health",
            "listing_detail_examples": [item["detail_api"] for item in featured_listings],
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
        brand=filters.brand,
        condition=filters.condition,
        query=filters.query,
        sort=filters.sort,
        page=filters.page,
        page_size=filters.page_size,
        now=now,
    )
    items = [_serialize_explorer_item(item) for item in page["items"]]
    return {
        "generated_at": generated_at,
        "db_path": str(repository.db_path),
        "filters": {
            "selected": {
                "root": filters.root or "all",
                "catalog_id": filters.catalog_id,
                "brand": filters.brand or "all",
                "condition": filters.condition or "all",
                "q": filters.query or "",
                "sort": page["sort"],
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
            "sort": page["sort"],
            "has_previous_page": page["has_previous_page"],
            "has_next_page": page["has_next_page"],
            "has_results": bool(items),
            "empty_reason": None if items else "No tracked listings match the current explorer filters.",
        },
        "items": items,
        "notes": {
            "estimated_publication": "Estimated publication uses the main image timestamp as a temporal signal. It is useful, but it is not an exact publication date.",
            "scalability": "Explorer results are filtered, sorted, and paged in SQL before only the current page receives observation/probe aggregation.",
        },
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
    estimated_publication_at = _format_unix_timestamp(listing.get("created_at_ts"))
    seller_login = listing.get("user_login")
    seller_profile_url = listing.get("user_profile_url")
    radar_first_seen_at = None if summary is None else summary.get("first_seen_at")
    radar_last_seen_at = None if summary is None else summary.get("last_seen_at")

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
        "engagement": {
            "visible_likes": listing.get("favourite_count"),
            "visible_views": listing.get("view_count"),
        },
        "seller": {
            "user_id": listing.get("user_id"),
            "login": seller_login,
            "profile_url": seller_profile_url,
            "display": seller_login or "Seller not exposed on the current card payload",
        },
        "timing": {
            "publication_estimated_at": estimated_publication_at,
            "publication_signal_label": None if estimated_publication_at is None else "Main image timestamp estimate",
            "radar_first_seen_at": radar_first_seen_at,
            "radar_last_seen_at": radar_last_seen_at,
        },
        "signals": [
            {"label": "Observation runs", "value": str(listing.get("observation_count") or 0)},
            {"label": "Freshness", "value": str(listing.get("freshness_bucket") or "unknown")},
            {"label": "Follow-up misses", "value": str(listing.get("follow_up_miss_count") or 0)},
            {"label": "Visible likes", "value": _format_optional_int(listing.get("favourite_count"))},
            {"label": "Visible views", "value": _format_optional_int(listing.get("view_count"))},
            {"label": "Estimated publication", "value": estimated_publication_at or "n/a"},
            {"label": "Radar first seen", "value": _format_optional_timestamp(radar_first_seen_at)},
            {"label": "Demand score", "value": _format_score(listing.get("demand_score"))},
            {"label": "Premium score", "value": _format_score(listing.get("premium_score"))},
        ],
        "transitions": transitions,
    }


def _serialize_explorer_item(item: dict[str, Any]) -> dict[str, Any]:
    listing_id = int(item["listing_id"])
    estimated_publication_at = _format_unix_timestamp(item.get("created_at_ts"))
    seller_login = item.get("user_login")
    seller_profile_url = item.get("user_profile_url")
    latest_probe_outcome = item.get("latest_probe_outcome")
    latest_probe_status = item.get("latest_probe_response_status")
    latest_probe_display = "Not probed"
    if latest_probe_outcome:
        latest_probe_display = str(latest_probe_outcome)
        if latest_probe_status is not None:
            latest_probe_display = f"{latest_probe_display} ({latest_probe_status})"

    payload = dict(item)
    payload.update(
        {
            "price_display": _format_money(item.get("price_amount_cents"), item.get("price_currency")),
            "total_price_display": _format_money(item.get("total_price_amount_cents"), item.get("total_price_currency")),
            "visible_likes_display": _format_optional_int(item.get("favourite_count")),
            "visible_views_display": _format_optional_int(item.get("view_count")),
            "estimated_publication_at": estimated_publication_at,
            "estimated_publication_note": None if estimated_publication_at is None else "Main image timestamp estimate",
            "radar_first_seen_display": _format_optional_timestamp(item.get("first_seen_at")),
            "radar_last_seen_display": _format_optional_timestamp(item.get("last_seen_at")),
            "seller_display": seller_login or "Seller not exposed",
            "seller_profile_url": seller_profile_url,
            "latest_probe_display": latest_probe_display,
            "explorer_href": f"/explorer?q={listing_id}",
            "canonical_href": item.get("canonical_url"),
            "detail_api": f"/api/listings/{listing_id}",
        }
    )
    return payload



def render_dashboard_html(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    inventory = summary["inventory"]
    honesty = summary["honesty"]
    freshness = summary["freshness"]
    diagnostics = payload["diagnostics"]
    featured_listings = payload["featured_listings"]
    recent_failures = freshness.get("recent_acquisition_failures") or []
    runtime = payload.get("runtime") or {}
    latest_cycle = runtime.get("latest_cycle") or {}

    cards_html = "".join(
        (
            _metric_card(
                "Annonces suivies",
                _escape(str(inventory.get("tracked_listings", 0))),
                [
                    f"{inventory['state_counts'].get('active', 0)} actives",
                    f"{inventory['state_counts'].get('sold_observed', 0)} vendues observées",
                    f"{inventory['state_counts'].get('sold_probable', 0)} vendues probables",
                ],
            ),
            _metric_card(
                "Signal de vente",
                _escape(str(inventory.get("sold_like_count", 0))),
                [
                    f"Support minimal par module : {inventory.get('comparison_support_threshold', 0)} annonces",
                    "Les modules marqués fragile restent visibles.",
                ],
            ),
            _metric_card(
                "Confiance",
                _escape(str(honesty["confidence_counts"].get("high", 0))),
                [
                    f"Haute {honesty['confidence_counts'].get('high', 0)}",
                    f"Moyenne {honesty['confidence_counts'].get('medium', 0)}",
                    f"Basse {honesty['confidence_counts'].get('low', 0)}",
                ],
            ),
            _metric_card(
                "Fraîcheur",
                _escape(_format_optional_timestamp(freshness.get("latest_successful_scan_at"))),
                [
                    f"Dernière vue annonce : {_format_optional_timestamp(freshness.get('latest_listing_seen_at'))}",
                    f"Cycle runtime : {latest_cycle.get('status') or freshness.get('latest_runtime_cycle_status') or 'n/a'}",
                ],
            ),
        )
    )

    modules_html = "".join(
        _render_comparison_module(module, explorer_href=diagnostics["explorer"])
        for module in payload["comparisons"].values()
    )
    notes_html = "".join(_render_honesty_note(note) for note in payload["honesty_notes"])
    featured_html = _render_featured_listing_cards(featured_listings)
    failure_html = (
        '<ul class="failure-list">'
        + "".join(
            f"<li><strong>{_escape(str(item.get('catalog_path') or 'Catalogue inconnu'))}</strong><span>{_escape(str(item.get('error_message') or item.get('response_status') or 'Erreur inconnue'))}</span></li>"
            for item in recent_failures[:5]
        )
        + "</ul>"
        if recent_failures
        else '<p class="muted">Aucune panne récente d’acquisition n’est remontée dans le dernier run connu.</p>'
    )

    diagnostics_links = [
        ("Explorer", diagnostics["explorer"]),
        ("JSON aperçu", diagnostics["dashboard_api"]),
        ("JSON runtime", diagnostics["runtime_api"]),
        ("Santé", diagnostics["health"]),
    ]
    diagnostics_html = "".join(
        f'<a class="button secondary" href="{_escape(href)}">{_escape(label)}</a>'
        for label, href in diagnostics_links
    )

    return f'''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vinted Radar — aperçu du marché</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%230e1620'/%3E%3Cpath d='M18 46V18h14.5c9.6 0 15.5 5.2 15.5 14s-5.9 14-15.2 14H18Zm8-6h5c5 0 8.6-3.1 8.6-8s-3.7-8-8.8-8H26v16Z' fill='%2387c7ff'/%3E%3C/svg%3E">
  <style>
    :root {{
      --bg: #08131e;
      --bg-soft: #0f2030;
      --panel: rgba(12, 26, 39, 0.92);
      --panel-strong: rgba(10, 20, 31, 0.97);
      --ink: #f3f7fb;
      --muted: #b7c8d8;
      --line: rgba(255,255,255,0.10);
      --accent: #87c7ff;
      --accent-strong: #3aa2ff;
      --accent-soft: rgba(135, 199, 255, 0.16);
      --success: #73d6a6;
      --warning: #ffcf74;
      --danger: #ff8a7a;
      --shadow: 0 26px 80px rgba(0, 0, 0, 0.30);
      --radius-lg: 28px;
      --radius-md: 22px;
      --radius-sm: 16px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ color-scheme: dark; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(58,162,255,0.23), transparent 28%),
        radial-gradient(circle at bottom right, rgba(115,214,166,0.12), transparent 26%),
        linear-gradient(180deg, #08131e 0%, #09111a 100%);
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: radial-gradient(circle at center, black, transparent 82%);
      opacity: 0.34;
    }}
    a {{ color: inherit; }}
    .skip-link {{
      position: absolute;
      left: 16px;
      top: -64px;
      background: var(--panel-strong);
      color: var(--ink);
      padding: 12px 16px;
      border-radius: 999px;
      border: 1px solid var(--line);
      z-index: 10;
      text-decoration: none;
    }}
    .skip-link:focus {{ top: 16px; }}
    .shell {{ max-width: 1440px; margin: 0 auto; padding: 28px; position: relative; }}
    .hero, .panel, .module, .note, .metric, .listing-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .hero {{
      border-radius: var(--radius-lg);
      padding: 30px;
      display: grid;
      gap: 20px;
      background:
        linear-gradient(135deg, rgba(135,199,255,0.22), rgba(255,255,255,0.03)),
        var(--panel);
      margin-bottom: 22px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 12px;
      color: var(--accent);
      font-weight: 700;
    }}
    h1, h2, h3 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-weight: 600;
      text-wrap: balance;
    }}
    h1 {{ font-size: clamp(2.3rem, 5vw, 4.4rem); line-height: 0.96; max-width: 12ch; }}
    h2 {{ font-size: clamp(1.45rem, 2.1vw, 2.1rem); line-height: 1.04; }}
    h3 {{ font-size: 1.08rem; line-height: 1.2; }}
    p {{ margin: 0; }}
    .lead {{ max-width: 76ch; color: var(--muted); line-height: 1.65; text-wrap: pretty; }}
    .nav-links, .button-row, .feature-actions, .module-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .button {{
      min-height: 42px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 16px;
      border-radius: 999px;
      border: 1px solid rgba(135,199,255,0.34);
      background: linear-gradient(135deg, rgba(135,199,255,0.24), rgba(58,162,255,0.08));
      color: var(--ink);
      text-decoration: none;
      font-weight: 600;
      transition: transform 140ms ease, border-color 140ms ease, background-color 140ms ease;
      font-variant-numeric: tabular-nums;
    }}
    .button:hover {{ transform: translateY(-1px); border-color: rgba(135,199,255,0.6); }}
    .button:active {{ transform: scale(0.96); }}
    .button.secondary {{ background: rgba(255,255,255,0.04); border-color: var(--line); color: var(--muted); }}
    .button:focus-visible, .lens-link:focus-visible, .listing-link:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; }}
    .cards {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 22px; }}
    .metric {{ border-radius: var(--radius-md); padding: 22px; }}
    .metric-label {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.15em; font-size: 11px; margin-bottom: 12px; }}
    .metric-value {{ font-size: 1.95rem; font-family: Georgia, "Times New Roman", serif; margin-bottom: 10px; font-variant-numeric: tabular-nums; }}
    .metric ul {{ margin: 0; padding-left: 18px; display: grid; gap: 6px; color: var(--muted); line-height: 1.45; text-wrap: pretty; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.92fr); gap: 22px; align-items: start; }}
    .stack {{ display: grid; gap: 22px; }}
    .panel {{ border-radius: var(--radius-lg); padding: 24px; }}
    .panel-head {{ display: grid; gap: 8px; margin-bottom: 18px; }}
    .panel-head p, .muted {{ color: var(--muted); line-height: 1.6; text-wrap: pretty; }}
    .module-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .module {{ border-radius: var(--radius-md); padding: 18px; display: grid; gap: 16px; }}
    .module-header {{ display: grid; gap: 10px; }}
    .badge-row, .lens-badges {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 32px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      font-size: 12px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .badge.ok {{ color: var(--success); }}
    .badge.warning {{ color: var(--warning); }}
    .badge.danger {{ color: var(--danger); }}
    .lens-list {{ display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }}
    .lens-row {{
      border-radius: var(--radius-sm);
      background: rgba(255,255,255,0.035);
      border: 1px solid rgba(255,255,255,0.07);
      padding: 14px;
      display: grid;
      gap: 10px;
    }}
    .lens-top {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .lens-top strong {{ font-size: 1rem; }}
    .lens-meta {{ color: var(--muted); line-height: 1.5; text-wrap: pretty; }}
    .lens-link, .listing-link {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
    .note-list {{ display: grid; gap: 12px; }}
    .note {{ border-radius: var(--radius-md); padding: 16px; display: grid; gap: 8px; }}
    .note.warning {{ border-color: rgba(255, 207, 116, 0.28); background: rgba(255, 207, 116, 0.08); }}
    .note.danger {{ border-color: rgba(255, 138, 122, 0.24); background: rgba(255, 138, 122, 0.08); }}
    .note.info {{ border-color: rgba(135, 199, 255, 0.26); background: rgba(135, 199, 255, 0.07); }}
    .note-title {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
    .note-title strong {{ font-size: 1rem; }}
    .note-title span {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
    .listing-grid {{ display: grid; gap: 14px; }}
    .listing-card {{ border-radius: var(--radius-md); padding: 18px; display: grid; gap: 12px; }}
    .listing-meta {{ color: var(--muted); line-height: 1.55; text-wrap: pretty; }}
    .listing-stats {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .failure-list {{ margin: 0; padding-left: 18px; display: grid; gap: 10px; color: var(--muted); line-height: 1.5; }}
    .failure-list strong {{ color: var(--ink); display: block; margin-bottom: 3px; }}
    @media (max-width: 1080px) {{ .layout {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 680px) {{
      .shell {{ padding: 18px; }}
      .hero, .panel, .metric {{ padding: 18px; }}
      .module-grid {{ grid-template-columns: 1fr; }}
      .lens-top {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <a class="skip-link" href="#contenu-principal">Aller au contenu</a>
  <main id="contenu-principal" class="shell">
    <header class="hero">
      <span class="eyebrow">Vue d’ensemble du marché</span>
      <h1>Ce qui bouge maintenant sur le radar Vinted.</h1>
      <p class="lead">Cette page d’accueil privilégie un aperçu français, lisible et honnête. Le contenu principal vient directement du contrat SQL du dépôt : volumes suivis, fraîcheur réelle, niveaux de confiance, zones fragiles et premiers comparatifs catégories / marques / prix / états / statuts de vente.</p>
      <nav class="nav-links" aria-label="Raccourcis d’exploration">
        <a class="button" href="{_escape(diagnostics['explorer'])}">Explorer les annonces</a>
        <a class="button secondary" href="{_escape(diagnostics['dashboard_api'])}">Ouvrir le JSON aperçu</a>
        <a class="button secondary" href="{_escape(diagnostics['runtime_api'])}">Voir le runtime</a>
        <a class="button secondary" href="{_escape(diagnostics['health'])}">Vérifier la santé</a>
      </nav>
    </header>

    <section class="cards" aria-label="Indicateurs clés">{cards_html}</section>

    <div class="layout">
      <div class="stack">
        <section class="panel" aria-labelledby="modules-title">
          <div class="panel-head">
            <h2 id="modules-title">Comparaisons à lire avec contexte</h2>
            <p>Chaque module garde les raisons de support faible, de signal partiel et d’estimation. Rien n’est lissé : les cartes fragiles restent visibles pour que le doute soit lisible, pas caché.</p>
          </div>
          <div class="module-grid">{modules_html}</div>
        </section>

        <section class="panel" aria-labelledby="listings-title">
          <div class="panel-head">
            <h2 id="listings-title">Exemples d’annonces pour aller plus loin</h2>
            <p>Ces cartes ouvrent des chemins concrets vers l’explorateur, la fiche JSON détaillée et la page publique quand elle est encore disponible.</p>
          </div>
          {featured_html}
        </section>
      </div>

      <aside class="stack" aria-label="Contexte et honnêteté">
        <section class="panel" aria-labelledby="honesty-title">
          <div class="panel-head">
            <h2 id="honesty-title">Niveau d’honnêteté du signal</h2>
            <p>Ces notes résument les zones d’inférence, de dégradation et d’approximation qui comptent le plus pour interpréter la page correctement.</p>
          </div>
          <div class="note-list">{notes_html}</div>
        </section>

        <section class="panel" aria-labelledby="runtime-title">
          <div class="panel-head">
            <h2 id="runtime-title">Fraîcheur et incidents récents</h2>
            <p>Dernier scan réussi : {_escape(_format_optional_timestamp(freshness.get('latest_successful_scan_at')))} · dernier cycle runtime : {_escape(str(freshness.get('latest_runtime_cycle_status') or 'n/a'))}.</p>
          </div>
          {failure_html}
        </section>

        <section class="panel" aria-labelledby="diag-title">
          <div class="panel-head">
            <h2 id="diag-title">Surfaces de diagnostic</h2>
            <p>Pour diagnostiquer une régression, comparez d’abord cette page avec les JSON publics correspondants : même source, symptômes plus faciles à tracer.</p>
          </div>
          <div class="button-row">{diagnostics_html}</div>
        </section>
      </aside>
    </div>
  </main>
</body>
</html>'''



def _serialize_overview_listing_item(item: dict[str, Any]) -> dict[str, Any]:
    return _serialize_explorer_item(item)



def _build_honesty_notes(overview: dict[str, Any]) -> list[dict[str, Any]]:
    summary = overview["summary"]
    inventory = summary["inventory"]
    honesty = summary["honesty"]
    freshness = summary["freshness"]

    threshold = int(inventory.get("comparison_support_threshold") or 0)
    notes: list[dict[str, Any]] = [
        {
            "slug": "low-support-rule",
            "level": "info",
            "title": "Supports fragiles laissés visibles",
            "count": threshold,
            "description": f"Toute ligne sous {threshold} annonces suivies reste affichée avec un badge de prudence au lieu d’être masquée.",
        }
    ]

    inferred_count = int(honesty.get("inferred_state_count") or 0)
    if inferred_count:
        notes.append(
            {
                "slug": "inferred-states",
                "level": "warning",
                "title": "États inférés",
                "count": inferred_count,
                "description": f"{inferred_count} annonces reposent sur des absences de rescans ou un contexte indirect, pas sur un constat direct de la page produit.",
            }
        )

    unknown_count = int(honesty.get("unknown_state_count") or 0)
    if unknown_count:
        notes.append(
            {
                "slug": "unknown-states",
                "level": "warning",
                "title": "États encore inconnus",
                "count": unknown_count,
                "description": f"{unknown_count} annonces n’ont pas encore assez de signal pour trancher proprement entre actif, vendu ou supprimé.",
            }
        )

    partial_count = int(honesty.get("partial_signal_count") or 0)
    if partial_count:
        notes.append(
            {
                "slug": "partial-signals",
                "level": "warning",
                "title": "Signal partiel",
                "count": partial_count,
                "description": f"{partial_count} annonces ont des champs publics incomplets ; la lecture reste utile, mais moins robuste.",
            }
        )

    thin_count = int(honesty.get("thin_signal_count") or 0)
    if thin_count:
        notes.append(
            {
                "slug": "thin-signals",
                "level": "danger",
                "title": "Signal mince",
                "count": thin_count,
                "description": f"{thin_count} annonces cumulent très peu de signaux publics : à lire comme une piste, pas comme une certitude.",
            }
        )

    estimated_count = int(honesty.get("estimated_publication_count") or 0)
    missing_estimated_count = int(honesty.get("missing_estimated_publication_count") or 0)
    if estimated_count or missing_estimated_count:
        description_parts: list[str] = []
        if estimated_count:
            description_parts.append(
                f"{estimated_count} annonces utilisent une estimation de date de publication basée sur l’horodatage de l’image principale"
            )
        if missing_estimated_count:
            description_parts.append(
                f"{missing_estimated_count} n’ont pas cette estimation et restent donc plus opaques dans le temps"
            )
        notes.append(
            {
                "slug": "estimated-publication",
                "level": "info",
                "title": "Signal de publication estimé",
                "count": estimated_count,
                "description": ". ".join(part.rstrip(".") for part in description_parts) + ".",
            }
        )

    failure_count = int(freshness.get("recent_acquisition_failure_count") or 0)
    if failure_count:
        notes.append(
            {
                "slug": "recent-acquisition-failures",
                "level": "danger",
                "title": "Acquisition dégradée récemment",
                "count": failure_count,
                "description": f"{failure_count} échecs récents de scan peuvent sous-représenter certaines zones du marché jusqu’au prochain cycle propre.",
            }
        )

    return notes



def _render_honesty_note(note: dict[str, Any]) -> str:
    level = str(note.get("level") or "info")
    return (
        f'<article class="note { _escape(level) }">'
        f'<div class="note-title"><strong>{_escape(str(note.get("title") or "Note"))}</strong>'
        f'<span>{_escape(str(note.get("count") if note.get("count") is not None else ""))}</span></div>'
        f'<p class="muted">{_escape(str(note.get("description") or ""))}</p>'
        f'</article>'
    )



def _translate_overview_reason(reason: str, *, support_threshold: int) -> str:
    thin_support_reason = f"No lens value reaches the minimum support threshold of {support_threshold} tracked listings."
    if reason == thin_support_reason:
        return f"Aucune valeur de ce module n’atteint le seuil minimal de {support_threshold} annonces suivies."
    if reason == "No tracked listings are available for this comparison lens yet.":
        return "Aucune annonce suivie n’est encore disponible pour ce module de comparaison."
    return reason



def _render_comparison_module(module: dict[str, Any], *, explorer_href: str) -> str:
    status = str(module.get("status") or "empty")
    status_labels = {
        "ok": ("Support solide", "ok"),
        "thin-support": ("Support fragile", "warning"),
        "empty": ("Vide", "danger"),
    }
    status_label, status_class = status_labels.get(status, (status, "warning"))
    rows = module.get("rows") or []
    rows_html = (
        "<ol class=" + '"lens-list">' + "".join(_render_comparison_row(row, explorer_href=explorer_href) for row in rows) + "</ol>"
        if rows
        else '<p class="muted">Aucune ligne disponible pour ce module.</p>'
    )
    reason_html = "" if not module.get("reason") else f'<p class="muted">{_escape(_translate_overview_reason(str(module["reason"]), support_threshold=int(module.get("support_threshold") or 0)))}</p>'
    return (
        f'<article class="module">'
        f'<header class="module-header">'
        f'<div class="lens-top"><div><h3>{_escape(str(module.get("title") or module.get("lens") or "Module"))}</h3></div>'
        f'<span class="badge {status_class}">{_escape(status_label)}</span></div>'
        f'{reason_html}'
        f'</header>'
        f'{rows_html}'
        f'</article>'
    )



def _render_comparison_row(row: dict[str, Any], *, explorer_href: str) -> str:
    inventory = row.get("inventory") if isinstance(row.get("inventory"), dict) else {}
    honesty = row.get("honesty") if isinstance(row.get("honesty"), dict) else {}
    filters = row.get("drilldown", {}).get("filters") if isinstance(row.get("drilldown"), dict) else {}
    if not isinstance(filters, dict):
        filters = {}

    average_price = inventory.get("average_price_amount_cents")
    average_price_display = "n/a" if average_price is None else _format_money(round(float(average_price)), "€")
    support_share = float(inventory.get("support_share") or 0.0) * 100.0
    filters_label = _describe_drilldown_filters(filters)
    drilldown_href = _explorer_href_from_filters(filters, fallback=explorer_href)
    uses_specific_filters = drilldown_href != explorer_href

    badges: list[str] = []
    if honesty.get("low_support"):
        badges.append('<span class="badge warning">Support fragile</span>')
    if int(honesty.get("partial_signal_count") or 0):
        badges.append(f'<span class="badge warning">Partiel {int(honesty.get("partial_signal_count") or 0)}</span>')
    if int(honesty.get("thin_signal_count") or 0):
        badges.append(f'<span class="badge danger">Mince {int(honesty.get("thin_signal_count") or 0)}</span>')
    if int(honesty.get("unknown_state_count") or 0):
        badges.append(f'<span class="badge warning">Inconnu {int(honesty.get("unknown_state_count") or 0)}</span>')
    if int(honesty.get("inferred_state_count") or 0):
        badges.append(f'<span class="badge info">Inféré {int(honesty.get("inferred_state_count") or 0)}</span>')

    action_label = "Ouvrir le filtre dans l’explorateur" if uses_specific_filters else "Explorer en détail"
    return (
        f'<li class="lens-row">'
        f'<div class="lens-top"><div><strong>{_escape(str(row.get("label") or row.get("value") or "n/a"))}</strong>'
        f'<p class="lens-meta">Support {int(inventory.get("support_count") or 0)} · {support_share:.0f} % du suivi · vendus-like {int(inventory.get("sold_like_count") or 0)} · prix moyen {average_price_display}</p></div>'
        f'<a class="lens-link" href="{_escape(drilldown_href)}">{_escape(action_label)}</a></div>'
        f'<div class="lens-badges">{"".join(badges) or "<span class=\"badge ok\">Lecture stable</span>"}</div>'
        f'<p class="muted">Observé {int(honesty.get("observed_state_count") or 0)} · Inféré {int(honesty.get("inferred_state_count") or 0)} · Estimé publication {int(honesty.get("estimated_publication_count") or 0)} · {filters_label}</p>'
        f'</li>'
    )



def _render_featured_listing_cards(featured_listings: list[dict[str, Any]]) -> str:
    if not featured_listings:
        return '<p class="muted">Aucune annonce suivie n’est disponible pour le moment.</p>'

    cards: list[str] = []
    for item in featured_listings:
        canonical_link = ""
        if item.get("canonical_href"):
            canonical_link = f'<a class="button secondary" href="{_escape(str(item["canonical_href"]))}" target="_blank" rel="noreferrer">Voir sur Vinted</a>'
        cards.append(
            f'''
            <article class="listing-card">
              <div>
                <h3>{_escape(str(item.get("title") or "Annonce sans titre"))}</h3>
                <p class="listing-meta">{_escape(str(item.get("primary_catalog_path") or "Catalogue inconnu"))} · {_escape(str(item.get("brand") or "Marque inconnue"))}</p>
              </div>
              <div class="listing-stats">
                <span class="badge ok">{_escape(str(item.get("price_display") or "prix n/a"))}</span>
                <span class="badge">{_escape(str(item.get("freshness_bucket") or "fraîcheur inconnue"))}</span>
                <span class="badge">Likes { _escape(str(item.get("visible_likes_display") or "n/a")) }</span>
                <span class="badge">Vues { _escape(str(item.get("visible_views_display") or "n/a")) }</span>
              </div>
              <p class="listing-meta">Publication estimée : {_escape(str(item.get("estimated_publication_at") or "n/a"))} · { _escape(str(item.get("estimated_publication_note") or "Aucune estimation publique supplémentaire.")) }</p>
              <div class="feature-actions">
                <a class="button" href="{_escape(str(item.get("explorer_href") or "/explorer"))}">Ouvrir dans l’explorateur</a>
                <a class="button secondary" href="{_escape(str(item.get("detail_api") or "#"))}">JSON détail</a>
                {canonical_link}
              </div>
            </article>
            '''
        )
    return '<div class="listing-grid">' + "".join(cards) + '</div>'



def _explorer_href_from_filters(filters: dict[str, Any], *, fallback: str = "/explorer") -> str:
    supported_keys = {"root", "catalog_id", "brand", "condition"}
    params: dict[str, str] = {}
    for key, value in filters.items():
        if key not in supported_keys or value in {None, "", "all"}:
            continue
        params[key] = str(value)
    if not params:
        return fallback
    return f"{fallback}?{urlencode(params)}"



def _describe_drilldown_filters(filters: dict[str, Any]) -> str:
    labels = {
        "root": "racine",
        "catalog_id": "catalogue",
        "brand": "marque",
        "condition": "état",
        "price_band": "tranche de prix",
        "state": "statut radar",
    }
    state_labels = {
        "active": "actif",
        "sold_observed": "vendu observé",
        "sold_probable": "vendu probable",
        "unavailable_non_conclusive": "indisponible",
        "deleted": "supprimée",
        "unknown": "inconnu",
    }
    price_labels = {
        "under_20_eur": "< 20 €",
        "20_to_39_eur": "20–39 €",
        "40_plus_eur": "40 € et plus",
        "unknown": "prix inconnu",
    }
    parts: list[str] = []
    for key, value in filters.items():
        rendered_value = value
        if key == "state":
            rendered_value = state_labels.get(str(value), value)
        elif key == "price_band":
            rendered_value = price_labels.get(str(value), value)
        parts.append(f"{labels.get(key, key)} : {rendered_value}")
    return "Filtre suggéré — " + ", ".join(parts) if parts else "Filtre suggéré indisponible dans l’explorateur actuel."

def render_explorer_html(payload: dict[str, Any]) -> str:
    selected = payload["filters"]["selected"]
    available = payload["filters"]["available"]
    results = payload["results"]
    diagnostics = payload["diagnostics"]
    notes = payload.get("notes") or {}
    items = payload["items"]
    filters = ExplorerFilters(
        root=None if selected["root"] == "all" else selected["root"],
        catalog_id=selected["catalog_id"],
        brand=None if selected["brand"] == "all" else selected["brand"],
        condition=None if selected["condition"] == "all" else selected["condition"],
        query=selected["q"] or None,
        sort=str(selected["sort"]),
        page=int(selected["page"]),
        page_size=int(selected["page_size"]),
    )

    root_options = "".join(_option_html(item["value"], item["label"], selected["root"]) for item in available["roots"])
    catalog_options = "".join(_option_html(item["value"], item["label"], selected["catalog_id"]) for item in available["catalogs"])
    brand_options = "".join(_option_html(item["value"], item["label"], selected["brand"]) for item in available["brands"])
    condition_options = "".join(_option_html(item["value"], item["label"], selected["condition"]) for item in available["conditions"])
    sort_options = "".join(_option_html(item["value"], item["label"], selected["sort"]) for item in available["sorts"])
    selected_sort_label = next((item["label"] for item in available["sorts"] if item["value"] == selected["sort"]), str(selected["sort"]))
    page_size_options = "".join(_option_html(str(value), str(value), selected["page_size"]) for value in (25, 50, 100))

    if items:
        rows_html = "".join(
            f"""
            <tr>
              <td><strong>{int(item['listing_id'])}</strong></td>
              <td>
                <div><strong>{_escape(str(item.get('title') or '(untitled)'))}</strong></div>
                <div class=\"link-muted\">{_escape(str(item.get('brand') or 'Unknown brand'))}</div>
                <div class=\"link-muted\">{'<a class="link-muted" href="' + _escape(str(item.get('seller_profile_url'))) + '" target="_blank" rel="noreferrer">' + _escape(str(item.get('seller_display') or 'Seller not exposed')) + '</a>' if item.get('seller_profile_url') else _escape(str(item.get('seller_display') or 'Seller not exposed'))}</div>
              </td>
              <td>{_escape(str(item.get('primary_catalog_path') or item.get('root_title') or 'Unknown'))}</td>
              <td>
                <div>{_escape(str(item.get('price_display') or 'price n/a'))}</div>
                <div class=\"link-muted\">total {_escape(str(item.get('total_price_display') or 'n/a'))}</div>
              </td>
              <td>{_escape(str(item.get('visible_likes_display') or 'n/a'))}</td>
              <td>{_escape(str(item.get('visible_views_display') or 'n/a'))}</td>
              <td>
                <div>{_escape(str(item.get('estimated_publication_at') or 'n/a'))}</div>
                <div class=\"link-muted\">{_escape(str(item.get('estimated_publication_note') or 'No image timestamp signal'))}</div>
              </td>
              <td>
                <div>{_escape(str(item.get('radar_first_seen_display') or 'n/a'))}</div>
                <div class=\"link-muted\">last {_escape(str(item.get('radar_last_seen_display') or 'n/a'))}</div>
              </td>
              <td>
                <div>{_escape(str(item.get('freshness_bucket') or 'unknown'))}</div>
                <div class=\"link-muted\">{_escape(str(item.get('observation_count') or 0))} obs</div>
              </td>
              <td>{_escape(str(item.get('latest_probe_display') or 'Not probed'))}</td>
              <td>
                <div class=\"actions\">
                  <a class=\"button secondary\" href=\"{_escape(str(item.get('explorer_href') or '/explorer'))}\">Explorer</a>
                  <a class=\"button secondary\" href=\"{_escape(str(item.get('detail_api')))}\">JSON</a>
                  {'' if not item.get('canonical_href') else f'<a class="button secondary" href="{_escape(str(item.get("canonical_href")))}" target="_blank" rel="noreferrer">Vinted</a>'}
                </div>
              </td>
            </tr>
            """
            for item in items
        )
    else:
        rows_html = "<tr><td colspan='10'>No tracked listings match the current explorer filters.</td></tr>"

    previous_href = _explorer_query(filters, overrides={"page": max(filters.page - 1, 1)})
    next_href = _explorer_query(filters, overrides={"page": filters.page + 1})

    return f"""<!doctype html>
<html lang=\"fr\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Vinted Radar — explorateur</title>
  <link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%2315100f'/%3E%3Cpath d='M17 46V18h12.5c9.6 0 16.5 5.3 16.5 14 0 8.5-6.5 14-15.9 14H17Zm8-6h4.3c5.1 0 8.7-3 8.7-8s-3.7-8-9-8H25v16Z' fill='%23d5a15b'/%3E%3C/svg%3E'>
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
    .shell {{ max-width: 1520px; margin: 0 auto; padding: 32px; }}
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
    table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
    th, td {{ padding: 13px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); vertical-align: top; }}
    th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--muted); background: rgba(255,255,255,0.02); }}
    .notes {{ display: grid; gap: 8px; margin-top: 14px; }}
    .notes p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
  </style>
</head>
<body>
  <main class=\"shell\">
    <section class=\"panel\">
      <span class=\"eyebrow\">SQL-backed explorer</span>
      <h1>Listing explorer separated from the dashboard summary.</h1>
      <p class=\"subhead\">This surface filters, sorts, and pages tracked listings in SQLite first, then enriches only the current page with observation history and latest probe context. Use the dashboard for market summary and ranking proof; use this explorer for broad corpus browsing.</p>
      <div class=\"notes\">
        <p>{_escape(str(notes.get('scalability') or ''))}</p>
        <p>{_escape(str(notes.get('estimated_publication') or ''))}</p>
      </div>
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
          Brand
          <select name=\"brand\">{brand_options}</select>
        </label>
        <label>
          Condition
          <select name=\"condition\">{condition_options}</select>
        </label>
        <label>
          Search
          <input type=\"search\" name=\"q\" value=\"{_escape(selected['q'])}\" placeholder=\"Title, brand, seller, listing ID\">
        </label>
        <label>
          Sort
          <select name=\"sort\">{sort_options}</select>
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
        <div class=\"stat\"><strong>{_escape(str(selected_sort_label))}</strong><br><span class=\"link-muted\">active SQL sort</span></div>
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
              <th>Price</th>
              <th>Likes</th>
              <th>Views</th>
              <th>Estimated publication</th>
              <th>Radar timing</th>
              <th>Freshness</th>
              <th>Latest probe</th>
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

    state_explanation = detail.get("state_explanation") if isinstance(detail.get("state_explanation"), dict) else {}
    score_explanation = detail.get("score_explanation") if isinstance(detail.get("score_explanation"), dict) else {}
    score_context = score_explanation.get("context") if isinstance(score_explanation, dict) else None
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
    state_reasons = state_explanation.get("reasons") if isinstance(state_explanation.get("reasons"), list) else []
    score_factors = score_explanation.get("factors") if isinstance(score_explanation.get("factors"), dict) else {}
    seller = detail.get("seller") if isinstance(detail.get("seller"), dict) else {}
    timing = detail.get("timing") if isinstance(detail.get("timing"), dict) else {}
    seller_html = (
        f'<a class="link-muted" href="{_escape(str(seller.get("profile_url")))}" target="_blank" rel="noreferrer">{_escape(str(seller.get("login") or seller.get("display") or "Seller not exposed"))}</a>'
        if seller.get("profile_url")
        else f'<span class="link-muted">{_escape(str(seller.get("display") or "Seller not exposed"))}</span>'
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
        <strong>{_escape(str(detail.get('price_display') or 'price n/a'))}</strong> · <span class=\"link-muted\">total displayed { _escape(str(detail.get('total_price_display') or 'n/a')) }</span><br>
        <span class=\"link-muted\">Brand { _escape(str(detail.get('brand') or 'Unknown')) } · Size { _escape(str(detail.get('size_label') or 'n/a')) } · Condition { _escape(str(detail.get('condition_label') or 'n/a')) }</span>
      </div>
      <div class=\"signal\">
        <span class=\"signal-label\">Visible seller</span>
        {seller_html}<br>
        <span class=\"link-muted\">Estimated publication comes from the main image timestamp when present. Radar first seen is the first moment this collector observed the listing.</span>
      </div>
      <div>
        <h3>Timing</h3>
        <ul class=\"bullet-list\">
          <li>Estimated publication: {_escape(str(timing.get('publication_estimated_at') or 'n/a'))}</li>
          <li>Radar first seen: {_escape(_format_optional_timestamp(timing.get('radar_first_seen_at')))}</li>
          <li>Radar last seen: {_escape(_format_optional_timestamp(timing.get('radar_last_seen_at')))}</li>
        </ul>
      </div>
      <div>
        <h3>Inference basis</h3>
        <ul class=\"bullet-list\">{''.join(f'<li>{_escape(reason)}</li>' for reason in state_reasons) or '<li>No state explanation available.</li>'}</ul>
      </div>
      <div>
        <h3>Score context</h3>
        <ul class=\"bullet-list\">
          {''.join(f'<li>{_escape(name.replace("_", " "))}: {_format_score(value)}</li>' for name, value in score_factors.items())}
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


def _bounded_explorer_sort(value: str | None) -> str:
    if value in {
        "last_seen_desc",
        "price_desc",
        "price_asc",
        "favourite_desc",
        "view_desc",
        "created_at_desc",
        "first_seen_desc",
    }:
        return str(value)
    return "last_seen_desc"


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


def _format_optional_int(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(int(value))


def _format_optional_timestamp(value: Any) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(str(value)).astimezone(UTC).replace(microsecond=0).isoformat()
    except ValueError:
        return str(value)


def _format_unix_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)
