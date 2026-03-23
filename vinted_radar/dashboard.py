from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import WSGIServer, make_server

from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import load_listing_scores
from vinted_radar.serving import RouteContext, normalize_base_path
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
    state: str | None = None
    price_band: str | None = None
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
            state=_normalized_filter_value(_first_value(params, "state")),
            price_band=_normalized_filter_value(_first_value(params, "price_band")),
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
        if self.state:
            payload["state"] = self.state
        if self.price_band:
            payload["price_band"] = self.price_band
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
    def __init__(
        self,
        db_path: str | Path,
        *,
        now: str | None = None,
        base_path: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.now = now
        self.route_context = RouteContext.from_options(base_path=base_path, public_base_url=public_base_url)

    def __call__(self, environ: dict[str, Any], start_response) -> list[bytes]:
        route_context = self._request_route_context(environ)
        path = self._request_path(environ, route_context=route_context)
        params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)

        if path in {"", "/"}:
            filters = DashboardFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_dashboard_payload(repository, filters=filters, now=self.now, route_context=route_context)
            body = render_dashboard_html(payload)
            return _respond(start_response, "200 OK", body, content_type="text/html; charset=utf-8")

        if path == "/api/dashboard":
            filters = DashboardFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_dashboard_payload(repository, filters=filters, now=self.now, route_context=route_context)
            body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path == "/explorer":
            filters = ExplorerFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_explorer_payload(repository, filters=filters, now=self.now, route_context=route_context)
            body = render_explorer_html(payload)
            return _respond(start_response, "200 OK", body, content_type="text/html; charset=utf-8")

        if path == "/api/explorer":
            filters = ExplorerFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                payload = build_explorer_payload(repository, filters=filters, now=self.now, route_context=route_context)
            body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path == "/runtime":
            with RadarRepository(self.db_path) as repository:
                payload = build_runtime_payload(repository, now=self.now, route_context=route_context)
            body = render_runtime_html(payload)
            return _respond(start_response, "200 OK", body, content_type="text/html; charset=utf-8")

        if path == "/api/runtime":
            with RadarRepository(self.db_path) as repository:
                payload = repository.runtime_status(limit=8, now=self.now)
            body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path.startswith("/listings/"):
            listing_id = _parse_int(path.rsplit("/", 1)[-1])
            if listing_id is None:
                return _respond(start_response, "404 Not Found", "Not Found", content_type="text/plain; charset=utf-8")
            explorer_filters = ExplorerFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                detail = build_listing_detail_payload(
                    repository,
                    listing_id=listing_id,
                    now=self.now,
                    route_context=route_context,
                    explorer_filters=explorer_filters,
                )
            if detail is None:
                return _respond(start_response, "404 Not Found", "Not Found", content_type="text/plain; charset=utf-8")
            body = render_listing_detail_html(detail)
            return _respond(start_response, "200 OK", body, content_type="text/html; charset=utf-8")

        if path.startswith("/api/listings/"):
            listing_id = _parse_int(path.rsplit("/", 1)[-1])
            if listing_id is None:
                return _respond(start_response, "404 Not Found", json.dumps({"error": "listing_not_found"}), content_type="application/json; charset=utf-8")
            explorer_filters = ExplorerFilters.from_query_params(params)
            with RadarRepository(self.db_path) as repository:
                detail = build_listing_detail_payload(
                    repository,
                    listing_id=listing_id,
                    now=self.now,
                    route_context=route_context,
                    explorer_filters=explorer_filters,
                )
            if detail is None:
                return _respond(start_response, "404 Not Found", json.dumps({"error": "listing_not_found", "listing_id": listing_id}), content_type="application/json; charset=utf-8")
            body = json.dumps(detail, ensure_ascii=False, indent=2, sort_keys=True)
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        if path == "/health":
            with RadarRepository(self.db_path) as repository:
                coverage = repository.coverage_summary()
                freshness = repository.freshness_summary(now=self.now)
                runtime_status = repository.runtime_status(limit=1, now=self.now)
            body = json.dumps(
                {
                    "status": "ok",
                    "db_path": str(self.db_path),
                    "has_run": coverage is not None,
                    "tracked_listings": int(freshness["overall"].get("tracked_listings") or 0),
                    "current_runtime_status": runtime_status.get("status"),
                    "runtime_controller": runtime_status.get("controller"),
                    "latest_runtime_cycle": runtime_status["latest_cycle"],
                    "acquisition": runtime_status.get("acquisition"),
                    "serving": {
                        "base_path": route_context.base_path or "/",
                        "public_base_url": route_context.public_base_url,
                        "home": route_context.path("/"),
                        "explorer": route_context.path("/explorer"),
                        "runtime": route_context.path("/runtime"),
                        "detail_example": route_context.path("/listings/1"),
                        "health": route_context.path("/health"),
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            return _respond(start_response, "200 OK", body, content_type="application/json; charset=utf-8")

        return _respond(start_response, "404 Not Found", "Not Found", content_type="text/plain; charset=utf-8")

    def _request_route_context(self, environ: dict[str, Any]) -> RouteContext:
        if self.route_context.base_path or self.route_context.public_base_url:
            return self.route_context
        base_path = normalize_base_path(
            environ.get("SCRIPT_NAME") or environ.get("HTTP_X_FORWARDED_PREFIX")
        )
        return RouteContext.from_options(base_path=base_path)

    def _request_path(self, environ: dict[str, Any], *, route_context: RouteContext) -> str:
        path = environ.get("PATH_INFO") or "/"
        prefixes = [route_context.base_path, normalize_base_path(environ.get("SCRIPT_NAME"))]
        for prefix in prefixes:
            if not prefix:
                continue
            if path == prefix:
                return "/"
            if path.startswith(prefix + "/"):
                stripped = path[len(prefix) :]
                return stripped or "/"
        return path


def serve_dashboard(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    now: str | None = None,
    base_path: str | None = None,
    public_base_url: str | None = None,
) -> None:
    application = DashboardApplication(db_path, now=now, base_path=base_path, public_base_url=public_base_url)
    with make_server(host, port, application) as server:
        server.serve_forever()


def start_dashboard_server(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    now: str | None = None,
    base_path: str | None = None,
    public_base_url: str | None = None,
) -> DashboardServerHandle:
    application = DashboardApplication(db_path, now=now, base_path=base_path, public_base_url=public_base_url)
    server = make_server(host, port, application)
    thread = Thread(target=server.serve_forever, name=f"dashboard-{port}", daemon=True)
    thread.start()
    return DashboardServerHandle(host=host, port=port, server=server, thread=thread)


def build_dashboard_payload(
    repository: RadarRepository,
    *,
    filters: DashboardFilters,
    now: str | None = None,
    route_context: RouteContext | None = None,
) -> dict[str, Any]:
    route_context = route_context or RouteContext()
    comparison_limit = max(1, min(int(filters.limit), SEGMENT_LIMIT))
    overview = repository.overview_snapshot(now=now, comparison_limit=comparison_limit)
    featured_page = repository.listing_explorer_page(page=1, page_size=4, sort="last_seen_desc", now=now)
    featured_listings = [_serialize_overview_listing_item(item, route_context=route_context) for item in featured_page["items"]]

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
        "serving": {
            "base_path": route_context.base_path or "/",
            "public_base_url": route_context.public_base_url,
        },
        "honesty_notes": _build_honesty_notes(overview),
        "featured_listings": featured_listings,
        "diagnostics": {
            "home": route_context.path("/"),
            "dashboard_api": route_context.path("/api/dashboard"),
            "runtime": route_context.path("/runtime"),
            "runtime_api": route_context.path("/api/runtime"),
            "explorer": route_context.path("/explorer"),
            "explorer_api": route_context.path("/api/explorer"),
            "health": route_context.path("/health"),
            "listing_detail_examples": [item["detail_href"] for item in featured_listings],
            "listing_detail_api_examples": [item["detail_api"] for item in featured_listings],
        },
    }


def build_explorer_payload(
    repository: RadarRepository,
    *,
    filters: ExplorerFilters,
    now: str | None = None,
    route_context: RouteContext | None = None,
) -> dict[str, Any]:
    route_context = route_context or RouteContext()
    generated_at = _generated_at(now)
    options = repository.explorer_filter_options(now=now)
    snapshot = repository.explorer_snapshot(
        root=filters.root,
        catalog_id=filters.catalog_id,
        brand=filters.brand,
        condition=filters.condition,
        state=filters.state,
        price_band=filters.price_band,
        query=filters.query,
        sort=filters.sort,
        page=filters.page,
        page_size=filters.page_size,
        comparison_limit=SEGMENT_LIMIT,
        now=now,
    )
    runtime = repository.runtime_status(limit=5, now=now)
    acquisition = runtime.get("acquisition") if isinstance(runtime, dict) else {}
    page = snapshot["page"]
    summary = snapshot["summary"]
    explorer_context = _build_explorer_context(filters, available=options, route_context=route_context)
    comparisons = _hydrate_explorer_comparison_links(
        snapshot["comparisons"],
        filters=filters,
        base_href=route_context.path("/explorer"),
    )
    items = [
        _serialize_explorer_item(
            item,
            route_context=route_context,
            explorer_filters=filters,
        )
        for item in page["items"]
    ]
    return {
        "generated_at": generated_at,
        "db_path": str(repository.db_path),
        "serving": {
            "base_path": route_context.base_path or "/",
            "public_base_url": route_context.public_base_url,
        },
        "filters": {
            "selected": {
                "root": filters.root or "all",
                "catalog_id": filters.catalog_id,
                "brand": filters.brand or "all",
                "condition": filters.condition or "all",
                "state": filters.state or "all",
                "price_band": filters.price_band or "all",
                "q": filters.query or "",
                "sort": page["sort"],
                "page": page["page"],
                "page_size": page["page_size"],
            },
            "available": options,
            "active": explorer_context["active_filters"],
            "summary": explorer_context["summary"],
        },
        "summary": summary,
        "comparisons": comparisons,
        "results": {
            "total_listings": page["total_listings"],
            "total_pages": page["total_pages"],
            "page": page["page"],
            "page_size": page["page_size"],
            "sort": page["sort"],
            "has_previous_page": page["has_previous_page"],
            "has_next_page": page["has_next_page"],
            "has_results": bool(items),
            "active_filter_count": len(explorer_context["active_filters"]),
            "empty_reason": None if items else "Aucune annonce suivie ne correspond aux filtres actuels de l’explorateur. Relâche un filtre, la recherche, ou la page courante pour réouvrir le corpus.",
        },
        "items": items,
        "context": explorer_context,
        "runtime": runtime,
        "acquisition": acquisition,
        "notes": {
            "estimated_publication": "La publication estimée s'appuie sur le timestamp de l'image principale. C'est un signal utile, pas une date de publication exacte.",
            "scalability": "Les résultats, comparaisons et compteurs de l’explorateur sont calculés côté SQL sur la tranche filtrée avant le rendu HTML de la page courante.",
            "support_rule": f"Toute comparaison sous {summary['inventory']['comparison_support_threshold']} annonces suivies garde un badge de prudence au lieu d’être supprimée.",
            "acquisition_status": None if not isinstance(acquisition, dict) else acquisition.get("status"),
            "acquisition_reasons": [] if not isinstance(acquisition, dict) else list(acquisition.get("reasons") or []),
        },
        "diagnostics": {
            "home": route_context.path("/"),
            "explorer": route_context.path("/explorer"),
            "explorer_api": route_context.path("/api/explorer"),
            "dashboard": route_context.path("/"),
            "runtime": route_context.path("/runtime"),
        },
    }



def build_runtime_payload(
    repository: RadarRepository,
    *,
    now: str | None = None,
    limit: int = 8,
    route_context: RouteContext | None = None,
) -> dict[str, Any]:
    route_context = route_context or RouteContext()
    generated_at = _generated_at(now)
    runtime = repository.runtime_status(limit=limit, now=now)
    controller = runtime.get("controller") or {}
    latest_cycle = runtime.get("latest_cycle") or {}
    heartbeat = runtime.get("heartbeat") or {}
    acquisition = runtime.get("acquisition") or {}
    return {
        "generated_at": generated_at,
        "db_path": str(repository.db_path),
        "serving": {
            "base_path": route_context.base_path or "/",
            "public_base_url": route_context.public_base_url,
        },
        "runtime": runtime,
        "acquisition": acquisition,
        "summary": {
            "status": runtime.get("status"),
            "phase": runtime.get("phase"),
            "mode": runtime.get("mode") or latest_cycle.get("mode"),
            "updated_at": runtime.get("updated_at"),
            "paused_at": runtime.get("paused_at"),
            "next_resume_at": runtime.get("next_resume_at"),
            "elapsed_pause_seconds": runtime.get("elapsed_pause_seconds"),
            "next_resume_in_seconds": runtime.get("next_resume_in_seconds"),
            "last_error": runtime.get("last_error"),
            "last_error_at": runtime.get("last_error_at"),
            "requested_action": runtime.get("requested_action"),
            "requested_at": runtime.get("requested_at"),
            "heartbeat": heartbeat,
            "active_cycle_id": runtime.get("active_cycle_id"),
            "latest_cycle_id": runtime.get("latest_cycle_id"),
            "controller_mode": controller.get("mode"),
            "acquisition_status": acquisition.get("status"),
        },
        "latest_cycle": latest_cycle,
        "recent_cycles": runtime.get("recent_cycles") or [],
        "recent_failures": runtime.get("recent_failures") or [],
        "totals": runtime.get("totals") or {},
        "diagnostics": {
            "home": route_context.path("/"),
            "dashboard_api": route_context.path("/api/dashboard"),
            "runtime": route_context.path("/runtime"),
            "runtime_api": route_context.path("/api/runtime"),
            "health": route_context.path("/health"),
            "explorer": route_context.path("/explorer"),
        },
        "notes": {
            "scheduled": "Un runtime 'scheduled' attend la prochaine fenêtre de reprise enregistrée en base. Ce n'est pas un run terminé : c'est une attente saine et suivie.",
            "paused": "Un runtime 'paused' garde un `paused_at` persistant. Le temps écoulé dépend du contrôleur, pas d'une estimation dérivée du dernier cycle.",
            "failed": "Un cycle raté reste visible dans l'historique, mais le contrôleur peut revenir à `scheduled` si la boucle continue avec retry.",
        },
    }



def build_listing_detail_payload(
    repository: RadarRepository,
    *,
    listing_id: int,
    now: str | None = None,
    route_context: RouteContext | None = None,
    explorer_filters: ExplorerFilters | None = None,
) -> dict[str, Any] | None:
    route_context = route_context or RouteContext()
    listing_scores = load_listing_scores(repository, now=now)
    listing = _find_listing(listing_scores, listing_id)
    if listing is None:
        return None

    history = repository.listing_history(listing_id, now=now, limit=12)
    summary = None if history is None else history["summary"]
    latest_probe = listing.get("latest_probe")
    transitions = _build_transition_events(listing, summary, latest_probe)
    estimated_publication_at = _format_unix_timestamp(listing.get("created_at_ts"))
    seller_login = listing.get("user_login")
    seller_profile_url = listing.get("user_profile_url")
    radar_first_seen_at = None if summary is None else summary.get("first_seen_at")
    radar_last_seen_at = None if summary is None else summary.get("last_seen_at")
    explorer_context = None
    if explorer_filters is not None:
        explorer_context = _build_explorer_context(
            explorer_filters,
            available=repository.explorer_filter_options(now=now),
            route_context=route_context,
        )

    engagement = {
        "visible_likes": listing.get("favourite_count"),
        "visible_views": listing.get("view_count"),
    }
    seller = {
        "user_id": listing.get("user_id"),
        "login": seller_login,
        "profile_url": seller_profile_url,
        "display": seller_login or "Vendeur non exposé sur la carte actuelle",
    }
    timing = {
        "publication_estimated_at": estimated_publication_at,
        "publication_signal_label": None if estimated_publication_at is None else "Estimation via le timestamp de l'image principale",
        "radar_first_seen_at": radar_first_seen_at,
        "radar_last_seen_at": radar_last_seen_at,
    }
    narrative = _build_detail_narrative(
        listing=listing,
        history_summary=summary,
        latest_probe=latest_probe,
        explorer_context=explorer_context,
        timing=timing,
        seller=seller,
        engagement=engagement,
    )
    provenance = _build_detail_provenance(
        listing=listing,
        latest_probe=latest_probe,
        timing=timing,
        history_summary=summary,
    )

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
        "explorer_context": explorer_context,
        "narrative": narrative,
        "provenance": provenance,
        "serving": {
            "base_path": route_context.base_path or "/",
            "public_base_url": route_context.public_base_url,
        },
        "diagnostics": {
            "home": route_context.path("/"),
            "explorer": route_context.path("/explorer"),
            "runtime": route_context.path("/runtime"),
            "detail_href": route_context.path(f"/listings/{listing_id}"),
            "detail_api": route_context.path(f"/api/listings/{listing_id}"),
            "dashboard_api": route_context.path("/api/dashboard"),
            "runtime_api": route_context.path("/api/runtime"),
            "explorer_back": None if explorer_context is None else explorer_context.get("back_href"),
            "explorer_back_api": None if explorer_context is None else explorer_context.get("back_api"),
        },
        "engagement": engagement,
        "seller": seller,
        "timing": timing,
        "signals": [
            {"label": "Observations", "value": str(listing.get("observation_count") or 0)},
            {"label": "Fraîcheur", "value": _freshness_label(listing.get("freshness_bucket") or "unknown")},
            {"label": "Ratés de suivi", "value": str(listing.get("follow_up_miss_count") or 0)},
            {"label": "Likes visibles", "value": _format_optional_int(listing.get("favourite_count"))},
            {"label": "Vues visibles", "value": _format_optional_int(listing.get("view_count"))},
            {"label": "Publication estimée", "value": estimated_publication_at or "n/a"},
            {"label": "Premier vu radar", "value": _format_optional_timestamp(radar_first_seen_at)},
            {"label": "Score demande", "value": _format_score(listing.get("demand_score"))},
            {"label": "Score premium", "value": _format_score(listing.get("premium_score"))},
        ],
        "transitions": transitions,
    }


def _build_detail_narrative(
    *,
    listing: dict[str, Any],
    history_summary: dict[str, Any] | None,
    latest_probe: dict[str, Any] | None,
    explorer_context: dict[str, Any] | None,
    timing: dict[str, Any],
    seller: dict[str, Any],
    engagement: dict[str, Any],
) -> dict[str, Any]:
    state_read = _build_detail_state_read(listing, latest_probe=latest_probe)
    market_read = _build_detail_market_read(listing)
    timing_read = _build_detail_timing_read(timing)
    visibility_read = _build_detail_visibility_read(seller=seller, engagement=engagement)
    active_filters = [] if explorer_context is None else explorer_context.get("active_filters") or []
    explorer_angle = None
    if explorer_context is not None and explorer_context.get("summary"):
        explorer_angle = f"Lecture ouverte depuis {explorer_context['summary']}."
    highlights = [state_read, market_read, timing_read, visibility_read]
    return {
        "headline": state_read["headline"],
        "summary": state_read["summary"],
        "explorer_angle": explorer_angle,
        "active_filter_count": len(active_filters),
        "highlights": highlights,
        "risk_notes": _build_detail_risk_notes(
            listing=listing,
            latest_probe=latest_probe,
            timing=timing,
            seller=seller,
            engagement=engagement,
        ),
        "proof_guide": "Les sections de preuve conservent le détail technique du score, de l’état, de la timeline et des transitions utilisées par le radar.",
    }


def _build_detail_state_read(listing: dict[str, Any], *, latest_probe: dict[str, Any] | None) -> dict[str, str]:
    state_code = str(listing.get("state_code") or "unknown")
    basis_kind = str(listing.get("basis_kind") or "unknown")
    confidence_label = str(listing.get("confidence_label") or "unknown")
    follow_up_miss_count = int(listing.get("follow_up_miss_count") or 0)
    observation_count = int(listing.get("observation_count") or 0)
    latest_probe_outcome = None if latest_probe is None else latest_probe.get("probe_outcome")
    latest_probe_status = None if latest_probe is None else latest_probe.get("response_status")

    if state_code == "active":
        headline = "Lecture radar : encore visible"
        if latest_probe_outcome == "active":
            summary = "La dernière vérification publique retrouvait une annonce encore achetable, ce qui garde la lecture côté actif sur une base observée."
        elif basis_kind == "observed":
            summary = "L’annonce figurait encore dans le dernier scan réussi de son catalogue principal, donc le radar la traite comme toujours active."
        else:
            summary = "Le radar la garde active faute de scan plus récent contradictoire ; ce n’est pas un constat direct de page produit."
    elif state_code == "sold_observed":
        headline = "Lecture radar : vendue avec signal direct"
        summary = "La page produit exposait un signal public de fermeture à l’achat, donc le radar lit cette annonce comme vendue sur une base observée."
    elif state_code == "sold_probable":
        headline = "Lecture radar : probablement déjà partie"
        summary = f"L’annonce a disparu après {follow_up_miss_count} rescans du catalogue sans réapparition ; le radar penche donc vers une vente probable, sans constat direct final."
    elif state_code == "unavailable_non_conclusive":
        headline = "Lecture radar : retirée ou indisponible, sans verdict final"
        if latest_probe_outcome == "unavailable":
            summary = "La page produit reste atteignable mais publiquement indisponible ; le signal ne permet pas de conclure proprement à une vente ou à une suppression."
        else:
            summary = "Le radar voit un affaiblissement du signal, mais pas assez distinct pour trancher entre vendu, supprimé, ou simple indisponibilité temporaire."
    elif state_code == "deleted":
        headline = "Lecture radar : signal distinct de suppression"
        summary = "La dernière vérification publique a renvoyé un signal clair de suppression, ce qui en fait la lecture la plus robuste disponible."
    else:
        headline = "Lecture radar : signal encore trop faible pour trancher"
        summary = "Le radar manque encore de preuve directe ou d’absences répétées assez nettes pour conclure proprement sur l’état actuel."

    detail_bits = [
        f"Base {_detail_basis_phrase(basis_kind)}",
        f"confiance {_confidence_label(confidence_label)}",
        _detail_observation_label(observation_count),
    ]
    if latest_probe_status is not None:
        detail_bits.append(f"dernière probe HTTP {latest_probe_status}")
    return {
        "slug": "radar_read",
        "title": "Lecture radar",
        "headline": headline,
        "summary": summary,
        "body": summary + " " + " · ".join(detail_bits) + ".",
        "tone": _detail_state_tone(state_code=state_code, basis_kind=basis_kind, confidence_label=confidence_label),
        "provenance": basis_kind,
    }


def _build_detail_market_read(listing: dict[str, Any]) -> dict[str, str]:
    demand_score = float(listing.get("demand_score") or 0.0)
    premium_score = float(listing.get("premium_score") or 0.0)
    score_explanation = listing.get("score_explanation") if isinstance(listing.get("score_explanation"), dict) else {}
    context = score_explanation.get("context") if isinstance(score_explanation.get("context"), dict) else None
    demand_band = _detail_score_band(demand_score)
    premium_band = _detail_score_band(premium_score)
    if context is not None:
        sample_size = int(context.get("sample_size") or 0)
        percentile = context.get("price_percentile")
        body = (
            f"Le signal demande ressort {demand_band} ({_format_score(demand_score)}), et le signal premium reste {premium_band} ({_format_score(premium_score)}). "
            f"Le contexte prix compare cette annonce à {sample_size} annonces sur {_detail_score_context_label(str(context.get('label') or 'unknown'))} ; son prix y apparaît {_detail_price_percentile_summary(percentile)}."
        )
    else:
        body = (
            f"Le signal demande ressort {demand_band} ({_format_score(demand_score)}). "
            f"Le score premium reste plus prudent ({_format_score(premium_score)}) car le radar n’a pas encore un groupe de comparaison prix assez large pour lire sa tenue de prix solidement."
        )
    return {
        "slug": "market_read",
        "title": "Lecture marché",
        "headline": f"Demande {demand_band} · premium {premium_band}",
        "summary": body,
        "body": body,
        "tone": "info" if context is None else "success",
        "provenance": "scored",
    }


def _build_detail_timing_read(timing: dict[str, Any]) -> dict[str, str]:
    publication_estimated_at = timing.get("publication_estimated_at")
    radar_first_seen_at = _format_optional_timestamp(timing.get("radar_first_seen_at"))
    radar_last_seen_at = _format_optional_timestamp(timing.get("radar_last_seen_at"))
    if publication_estimated_at:
        body = (
            f"Publication estimée autour de {publication_estimated_at}. "
            f"Le radar l’a d’abord vue le {radar_first_seen_at} puis l’a revue au plus tard le {radar_last_seen_at}."
        )
        provenance = "estimated"
    else:
        body = (
            f"Pas d’estimation de publication fiable sur cette carte. "
            f"Le repère le plus sûr reste la fenêtre radar : premier vu le {radar_first_seen_at}, dernier vu le {radar_last_seen_at}."
        )
        provenance = "radar"
    return {
        "slug": "timing",
        "title": "Repères temporels",
        "headline": "Temps public estimé + fenêtre radar",
        "summary": body,
        "body": body,
        "tone": "info",
        "provenance": provenance,
    }


def _build_detail_visibility_read(*, seller: dict[str, Any], engagement: dict[str, Any]) -> dict[str, str]:
    likes = _format_optional_int(engagement.get("visible_likes"))
    views = _format_optional_int(engagement.get("visible_views"))
    seller_display = str(seller.get("login") or seller.get("display") or "Vendeur non exposé")
    missing_fields = sum(1 for value in (engagement.get("visible_likes"), engagement.get("visible_views"), seller.get("login")) if value in {None, ""})
    if missing_fields:
        body = f"Visibilité publique partielle : vendeur {seller_display}, likes {likes}, vues {views}. Certaines cartes n’exposent pas tous les champs publics à chaque passage."
        provenance = "partial"
    else:
        body = f"Visibilité publique exploitable : vendeur {seller_display}, likes {likes}, vues {views}."
        provenance = "observed"
    return {
        "slug": "visibility",
        "title": "Visibilité publique",
        "headline": "Vendeur et engagement visibles",
        "summary": body,
        "body": body,
        "tone": "info",
        "provenance": provenance,
    }


def _build_detail_risk_notes(
    *,
    listing: dict[str, Any],
    latest_probe: dict[str, Any] | None,
    timing: dict[str, Any],
    seller: dict[str, Any],
    engagement: dict[str, Any],
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    basis_kind = str(listing.get("basis_kind") or "unknown")
    confidence_label = str(listing.get("confidence_label") or "unknown")
    score_explanation = listing.get("score_explanation") if isinstance(listing.get("score_explanation"), dict) else {}
    context = score_explanation.get("context") if isinstance(score_explanation.get("context"), dict) else None

    if basis_kind != "observed":
        notes.append(
            {
                "slug": "inferred-state",
                "title": "État non directement constaté",
                "body": "Cette lecture d’état repose en partie sur l’historique radar et les absences de rescans, pas uniquement sur une page produit observée ouverte ou fermée.",
                "tone": "warning",
            }
        )
    if _probe_is_degraded(latest_probe):
        notes.append(
            {
                "slug": "degraded-probe",
                "title": "Dernière probe dégradée",
                "body": _detail_probe_degradation_note(latest_probe),
                "tone": "danger",
            }
        )
    if confidence_label == "low":
        notes.append(
            {
                "slug": "low-confidence",
                "title": "Confiance encore basse",
                "body": "Le radar garde cette lecture, mais le niveau de confiance reste faible ; mieux vaut la lire comme une piste que comme une conclusion ferme.",
                "tone": "danger",
            }
        )
    if timing.get("publication_estimated_at"):
        notes.append(
            {
                "slug": "estimated-publication",
                "title": "Publication seulement estimée",
                "body": "La date de publication visible ici vient du timestamp de l’image principale. C’est utile pour se repérer, mais ce n’est pas un horodatage de publication garanti par Vinted.",
                "tone": "info",
            }
        )
    if context is None:
        notes.append(
            {
                "slug": "thin-premium-context",
                "title": "Lecture premium prudente",
                "body": "Le radar ne dispose pas encore d’un groupe de comparaison prix assez solide pour interpréter fortement la tenue de prix de cette annonce.",
                "tone": "warning",
            }
        )
    if seller.get("login") in {None, ""} or engagement.get("visible_likes") is None or engagement.get("visible_views") is None:
        notes.append(
            {
                "slug": "partial-public-fields",
                "title": "Champs publics incomplets",
                "body": "Certaines informations publiques (vendeur, likes ou vues) manquent sur cette annonce ou sur cette observation. La lecture reste utile, mais moins complète.",
                "tone": "warning",
            }
        )
    return notes


def _build_detail_provenance(
    *,
    listing: dict[str, Any],
    latest_probe: dict[str, Any] | None,
    timing: dict[str, Any],
    history_summary: dict[str, Any] | None,
) -> dict[str, dict[str, str]]:
    latest_probe_outcome = None if latest_probe is None else latest_probe.get("probe_outcome")
    latest_probe_status = None if latest_probe is None else latest_probe.get("response_status")
    state_kind = str(listing.get("basis_kind") or "unknown")
    publication_kind = "estimated" if timing.get("publication_estimated_at") else "missing"
    state_source = "page produit" if latest_probe_outcome in {"active", "sold", "deleted", "unavailable"} else "historique radar"
    if _probe_is_degraded(latest_probe):
        state_source = "historique radar après probe dégradée"
    return {
        "state_signal": {
            "label": "État radar",
            "kind": state_kind,
            "summary": f"Statut {_state_label(listing.get('state_code'))} lu sur une base {_detail_basis_phrase(state_kind)} avec confiance {_confidence_label(listing.get('confidence_label'))}.",
            "source": state_source,
            "latest_probe": "n/a" if latest_probe_status is None else f"{latest_probe_outcome} / HTTP {latest_probe_status}",
        },
        "publication_timing": {
            "label": "Publication visible",
            "kind": publication_kind,
            "summary": "Date estimée via le timestamp de l’image principale." if publication_kind == "estimated" else "Pas de repère public fiable pour estimer la publication.",
            "source": "image principale" if publication_kind == "estimated" else "aucun signal public stable",
            "value": str(timing.get("publication_estimated_at") or "n/a"),
        },
        "radar_window": {
            "label": "Fenêtre radar",
            "kind": "radar",
            "summary": "Horodatages issus du collecteur local, distincts d’une publication Vinted." if history_summary is not None else "Fenêtre radar indisponible.",
            "source": "listing_observations",
            "value": f"premier { _format_optional_timestamp(timing.get('radar_first_seen_at')) } · dernier { _format_optional_timestamp(timing.get('radar_last_seen_at')) }",
        },
    }


def _probe_is_degraded(latest_probe: dict[str, Any] | None) -> bool:
    if not isinstance(latest_probe, dict):
        return False
    detail = latest_probe.get("detail") if isinstance(latest_probe.get("detail"), dict) else {}
    reason = str(detail.get("reason") or "")
    response_status = latest_probe.get("response_status")
    if latest_probe.get("error_message") not in {None, ""}:
        return True
    if reason in {"anti_bot_challenge", "probe_exception"}:
        return True
    if reason.startswith("unexpected_http_") or reason.startswith("http_"):
        return True
    if response_status in {403, 429}:
        return True
    return isinstance(response_status, int) and response_status >= 500


def _detail_probe_degradation_note(latest_probe: dict[str, Any] | None) -> str:
    if not isinstance(latest_probe, dict):
        return "La dernière probe item-page ne donnait pas un signal assez propre pour renforcer la lecture d’état."
    detail = latest_probe.get("detail") if isinstance(latest_probe.get("detail"), dict) else {}
    reason = str(detail.get("reason") or latest_probe.get("probe_outcome") or "unknown")
    response_status = latest_probe.get("response_status")
    if reason == "anti_bot_challenge":
        return f"La dernière probe item-page a rencontré un challenge anti-bot (HTTP {response_status or 'n/a'}) ; l’historique radar redevient donc la base la plus prudente tant qu’une probe propre ne repasse pas."
    if reason == "probe_exception":
        return "La dernière probe item-page a échoué côté transport ; le radar garde la lecture, mais sans nouveau constat direct de page produit."
    if reason.startswith("unexpected_http_") or reason.startswith("http_"):
        return f"La dernière probe item-page s’est terminée sur HTTP {response_status or 'n/a'}, donc le radar ne la traite pas comme une preuve directe d’état."
    return "La dernière probe item-page ne donnait pas un signal assez propre pour renforcer la lecture d’état."


def _detail_state_tone(*, state_code: str, basis_kind: str, confidence_label: str) -> str:
    if state_code in {"deleted", "unknown"}:
        return "danger" if confidence_label == "low" else "warning"
    if basis_kind == "inferred" or confidence_label == "low":
        return "warning"
    if state_code in {"active", "sold_observed"}:
        return "success"
    return "info"


def _detail_score_band(score: float) -> str:
    if score >= 80.0:
        return "très fort"
    if score >= 60.0:
        return "solide"
    if score >= 40.0:
        return "intermédiaire"
    return "encore modéré"


def _detail_score_context_label(value: str) -> str:
    labels = {
        "catalog_brand_condition": "le même catalogue, la même marque et le même état",
        "catalog_condition": "le même catalogue et le même état",
        "catalog_brand": "le même catalogue et la même marque",
        "catalog": "le même catalogue",
        "root_condition": "la même racine et le même état",
        "root": "la même racine",
    }
    return labels.get(value, value.replace("_", " "))


def _detail_price_percentile_summary(value: Any) -> str:
    if value is None:
        return "sans percentile exploitable"
    percentile = float(value)
    if percentile >= 0.85:
        return "plutôt haut placé en prix"
    if percentile >= 0.65:
        return "au-dessus du milieu de gamme"
    if percentile >= 0.35:
        return "dans la zone médiane des prix"
    return "plutôt bas dans son groupe de prix"


def _serialize_explorer_item(
    item: dict[str, Any],
    *,
    route_context: RouteContext | None = None,
    explorer_filters: ExplorerFilters | None = None,
) -> dict[str, Any]:
    route_context = route_context or RouteContext()
    explorer_filters = explorer_filters or ExplorerFilters()
    listing_id = int(item["listing_id"])
    estimated_publication_at = _format_unix_timestamp(item.get("created_at_ts"))
    seller_login = item.get("user_login")
    seller_profile_url = item.get("user_profile_url")
    latest_probe_outcome = item.get("latest_probe_outcome")
    latest_probe_status = item.get("latest_probe_response_status")
    latest_probe_display = "Aucune probe"
    if latest_probe_outcome:
        latest_probe_display = str(latest_probe_outcome)
        if latest_probe_status is not None:
            latest_probe_display = f"{latest_probe_display} ({latest_probe_status})"

    detail_suffix = _explorer_suffix_query(explorer_filters)
    payload = dict(item)
    payload.update(
        {
            "price_display": _format_money(item.get("price_amount_cents"), item.get("price_currency")),
            "total_price_display": _format_money(item.get("total_price_amount_cents"), item.get("total_price_currency")),
            "visible_likes_display": _format_optional_int(item.get("favourite_count")),
            "visible_views_display": _format_optional_int(item.get("view_count")),
            "estimated_publication_at": estimated_publication_at,
            "estimated_publication_note": None if estimated_publication_at is None else "Estimation via le timestamp de l'image principale",
            "radar_first_seen_display": _format_optional_timestamp(item.get("first_seen_at")),
            "radar_last_seen_display": _format_optional_timestamp(item.get("last_seen_at")),
            "seller_display": seller_login or "Vendeur non exposé",
            "seller_profile_url": seller_profile_url,
            "latest_probe_display": latest_probe_display,
            "state_display": _state_label(item.get("state_code")),
            "basis_display": _basis_label(item.get("basis_kind")),
            "confidence_display": _confidence_label(item.get("confidence_label")),
            "explorer_href": _explorer_query(
                explorer_filters,
                base_href=route_context.path("/explorer"),
                overrides={"q": str(listing_id)},
            ),
            "canonical_href": item.get("canonical_url"),
            "detail_href": route_context.path(f"/listings/{listing_id}") + detail_suffix,
            "detail_api": route_context.path(f"/api/listings/{listing_id}") + detail_suffix,
        }
    )
    return payload



def _render_product_nav(diagnostics: dict[str, Any], *, current: str) -> str:
    entries = [
        ("home", "Accueil", diagnostics.get("home")),
        ("explorer", "Explorateur", diagnostics.get("explorer")),
        ("runtime", "Runtime", diagnostics.get("runtime")),
    ]
    nav_items: list[str] = []
    for key, label, href in entries:
        if not href:
            continue
        current_attr = ' aria-current="page"' if current == key else ""
        current_class = " current" if current == key else ""
        nav_items.append(
            f'<a class="button secondary nav-link{current_class}" href="{_escape(str(href))}"{current_attr}>{_escape(label)}</a>'
        )
    if current == "detail" and diagnostics.get("detail_href"):
        nav_items.append(
            f'<a class="button secondary nav-link current" href="{_escape(str(diagnostics["detail_href"]))}" aria-current="page">Fiche annonce</a>'
        )
    return '<nav class="product-nav" aria-label="Navigation principale du produit">' + "".join(nav_items) + "</nav>"



def _shared_shell_styles() -> str:
    return """
    :root {
      --bg: #0f1115;
      --bg-soft: #171b20;
      --panel: rgba(23, 27, 32, 0.94);
      --panel-strong: rgba(19, 23, 28, 0.98);
      --ink: #f5efe6;
      --muted: #c4b7a3;
      --line: rgba(255,255,255,0.08);
      --accent: #d4a267;
      --accent-soft: rgba(212,162,103,0.16);
      --success: #8fd3a7;
      --warning: #ffcf7d;
      --danger: #ff947f;
      --shadow: 0 28px 84px rgba(0,0,0,0.38);
      --radius-lg: 28px;
      --radius-md: 22px;
      --radius-sm: 16px;
    }
    * { box-sizing: border-box; }
    html { color-scheme: dark; -webkit-font-smoothing: antialiased; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(212,162,103,0.14), transparent 26%),
        radial-gradient(circle at bottom right, rgba(143,211,167,0.08), transparent 24%),
        linear-gradient(180deg, #131519 0%, #0f1115 100%);
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 32px 32px;
      mask-image: radial-gradient(circle at center, black, transparent 82%);
      opacity: 0.36;
    }
    a { color: inherit; }
    .skip-link {
      position: absolute;
      left: 16px;
      top: -56px;
      background: var(--panel-strong);
      color: var(--ink);
      padding: 11px 16px;
      border-radius: 999px;
      border: 1px solid var(--line);
      z-index: 30;
      text-decoration: none;
    }
    .skip-link:focus { top: 16px; }
    .shell {
      max-width: 1360px;
      margin: 0 auto;
      padding: 24px;
      position: relative;
    }
    .hero, .panel, .metric, .module, .note, .listing-card, .explorer-item, .cycle-card, .signal {
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }
    .hero {
      border-radius: var(--radius-lg);
      padding: 28px;
      display: grid;
      gap: 18px;
      margin-bottom: 20px;
      background:
        linear-gradient(135deg, rgba(212,162,103,0.18), rgba(255,255,255,0.02)),
        var(--panel);
    }
    .brand-row, .hero-actions, .product-nav, .button-row, .feature-actions, .module-actions, .status-line, .listing-stats, .pagination, .api-links, .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }
    .brand {
      text-transform: uppercase;
      letter-spacing: 0.24em;
      font-size: 11px;
      color: var(--accent);
      font-weight: 700;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 12px;
      color: var(--accent);
      font-weight: 700;
    }
    h1, h2, h3 {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      text-wrap: balance;
    }
    h1 { font-size: clamp(2.2rem, 5vw, 4.3rem); line-height: 0.98; max-width: 13ch; }
    h2 { font-size: clamp(1.35rem, 2.4vw, 2.1rem); line-height: 1.08; }
    h3 { font-size: 1.08rem; line-height: 1.22; }
    p { margin: 0; }
    .lead, .subhead, .muted, .listing-meta, .shell-copy, .panel-head p, .note p, .timeline-item span, .metric ul, .fact span, .link-muted {
      color: var(--muted);
      line-height: 1.6;
      text-wrap: pretty;
    }
    .button {
      min-height: 42px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 16px;
      border-radius: 999px;
      border: 1px solid rgba(212,162,103,0.34);
      background: linear-gradient(135deg, rgba(212,162,103,0.24), rgba(212,162,103,0.08));
      color: var(--ink);
      text-decoration: none;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      transition: transform 140ms ease, border-color 140ms ease, background-color 140ms ease;
    }
    .button:hover { transform: translateY(-1px); border-color: rgba(212,162,103,0.56); }
    .button:active { transform: scale(0.96); }
    .button.secondary {
      background: rgba(255,255,255,0.04);
      border-color: var(--line);
      color: var(--muted);
    }
    .button.secondary.current {
      color: var(--ink);
      border-color: rgba(212,162,103,0.34);
      background: rgba(212,162,103,0.14);
    }
    .button.disabled { opacity: 0.45; pointer-events: none; }
    .story-hero {
      border-radius: var(--radius-lg);
      padding: 22px;
      margin-bottom: 18px;
      border: 1px solid rgba(255,255,255,0.07);
      background:
        linear-gradient(135deg, rgba(212,162,103,0.12), rgba(255,255,255,0.02)),
        rgba(255,255,255,0.02);
      display: grid;
      gap: 12px;
    }
    .story-hero h2 {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(1.7rem, 2vw, 2.35rem);
    }
    .story-card {
      background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.015));
    }
    .proof-stack, .provenance-grid {
      display: grid;
      gap: 14px;
    }
    .provenance-grid {
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .proof-panel {
      border-radius: var(--radius-md);
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.03);
      overflow: hidden;
    }
    .proof-panel summary {
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }
    .proof-panel summary::-webkit-details-marker { display: none; }
    .proof-panel[open] summary {
      border-bottom: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.02);
    }
    .proof-body {
      padding: 18px;
      display: grid;
      gap: 16px;
    }
    .button:focus-visible, .lens-link:focus-visible, .listing-link:focus-visible, .nav-link:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 3px;
    }
    .cards, .stats, .metrics, .detail-grid, .facts, .compact-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
    .cards, .metrics { margin-bottom: 20px; }
    .metric, .explorer-item, .cycle-card, .signal, .fact {
      border-radius: var(--radius-md);
      padding: 18px;
    }
    .metric-label, .signal-label, .fact span {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 11px;
      margin-bottom: 8px;
      display: block;
    }
    .metric-value {
      font-size: 1.9rem;
      font-family: Georgia, "Times New Roman", serif;
      font-variant-numeric: tabular-nums;
      margin-bottom: 10px;
    }
    .metric ul, .bullet-list {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 6px;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.42fr) minmax(300px, 0.92fr);
      gap: 20px;
      align-items: start;
    }
    .stack, .note-list, .note-grid, .listing-grid, .timeline, .explorer-grid, .cycle-grid {
      display: grid;
      gap: 14px;
    }
    .panel {
      border-radius: var(--radius-lg);
      padding: 22px;
    }
    .panel-head {
      display: grid;
      gap: 8px;
      margin-bottom: 16px;
    }
    .module-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }
    .module, .note, .listing-card {
      border-radius: var(--radius-md);
      padding: 18px;
      display: grid;
      gap: 14px;
    }
    .module-header { display: grid; gap: 10px; }
    .badge, .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 32px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      font-variant-numeric: tabular-nums;
    }
    .badge.ok, .pill.success { color: var(--success); }
    .badge.warning, .pill.warning { color: var(--warning); }
    .badge.danger, .pill.danger { color: var(--danger); }
    .pill.info { color: var(--accent); }
    .pill.active { color: var(--success); }
    .pill.sold_observed, .pill.sold_probable { color: var(--warning); }
    .pill.deleted { color: var(--danger); }
    .pill.unavailable_non_conclusive, .pill.unknown { color: var(--muted); }
    .lens-list {
      display: grid;
      gap: 12px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .lens-row {
      border-radius: var(--radius-sm);
      background: rgba(255,255,255,0.035);
      border: 1px solid rgba(255,255,255,0.07);
      padding: 14px;
      display: grid;
      gap: 10px;
    }
    .lens-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .lens-link, .listing-link {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .explorer-item {
      display: grid;
      gap: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    }
    .explorer-head {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: start;
    }
    .meta-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
    .meta-block {
      border-radius: var(--radius-sm);
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.03);
      padding: 14px;
      display: grid;
      gap: 6px;
    }
    .meta-label {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 11px;
    }
    .filters {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      align-items: end;
    }
    label {
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    input, select {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.09);
      border-radius: 14px;
      background: rgba(255,255,255,0.04);
      color: var(--ink);
      padding: 12px 14px;
      font: inherit;
    }
    .timeline-item {
      border-left: 2px solid rgba(212,162,103,0.34);
      padding-left: 14px;
      display: grid;
      gap: 4px;
    }
    .timeline-item strong { color: var(--ink); }
    .empty-state {
      border-radius: var(--radius-md);
      padding: 18px;
      border: 1px dashed rgba(255,255,255,0.12);
      color: var(--muted);
      background: rgba(255,255,255,0.02);
    }
    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    @media (max-width: 1024px) {
      .layout { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .shell { padding: 16px; }
      .hero, .panel, .metric, .explorer-item, .cycle-card, .listing-card, .module, .note { padding: 16px; }
      .hero-actions, .product-nav, .brand-row, .lens-top, .explorer-head { flex-direction: column; align-items: stretch; }
      .button, .nav-link { width: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { scroll-behavior: auto; transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
    }
    """



def _render_product_shell(
    *,
    page_key: str,
    title: str,
    eyebrow: str,
    heading: str,
    intro: str,
    diagnostics: dict[str, Any],
    body_html: str,
    hero_actions: str = "",
    status_html: str = "",
    main_id: str = "product-main",
) -> str:
    nav_html = _render_product_nav(diagnostics, current=page_key)
    actions_html = f'<div class="hero-actions">{hero_actions}</div>' if hero_actions else ""
    status_block = status_html or ""
    return f'''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23131115'/%3E%3Cpath d='M17 46V18h12.5c9.6 0 16.5 5.3 16.5 14 0 8.5-6.5 14-15.9 14H17Zm8-6h4.3c5.1 0 8.7-3 8.7-8s-3.7-8-9-8H25v16Z' fill='%23d4a267'/%3E%3C/svg%3E">
  <style>{_shared_shell_styles()}</style>
</head>
<body>
  <a class="skip-link" href="#{_escape(main_id)}">Aller au contenu</a>
  <main id="{_escape(main_id)}" class="shell">
    <header class="hero">
      <div class="brand-row">
        <span class="brand">Vinted Radar</span>
        <span class="eyebrow">{_escape(eyebrow)}</span>
      </div>
      <h1>{_escape(heading)}</h1>
      <p class="lead">{_escape(intro)}</p>
      {status_block}
      {nav_html}
      {actions_html}
    </header>
    {body_html}
  </main>
</body>
</html>'''



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
    current_runtime_status = (
        freshness.get("current_runtime_status")
        or runtime.get("status")
        or latest_cycle.get("status")
        or freshness.get("latest_runtime_cycle_status")
    )
    acquisition_status = str(freshness.get("acquisition_status") or "unknown")
    runtime_timing_line = None
    if freshness.get("current_runtime_next_resume_at"):
        runtime_timing_line = f"Prochaine reprise : {_format_optional_timestamp(freshness.get('current_runtime_next_resume_at'))}"
    elif freshness.get("current_runtime_paused_at"):
        runtime_timing_line = f"En pause depuis : {_format_optional_timestamp(freshness.get('current_runtime_paused_at'))}"

    freshness_lines = [
        f"Dernière vue annonce : {_format_optional_timestamp(freshness.get('latest_listing_seen_at'))}",
        f"Runtime actuel : {_runtime_status_label(current_runtime_status)}",
        f"Acquisition : {_acquisition_status_label(acquisition_status)}",
    ]
    if runtime_timing_line:
        freshness_lines.append(runtime_timing_line)

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
                freshness_lines,
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
        else '<div class="empty-state"><p>Aucune panne récente d’acquisition n’est remontée dans le dernier run connu.</p></div>'
    )

    diagnostics_links = [
        ("Explorer", diagnostics["explorer"]),
        ("Runtime", diagnostics["runtime"]),
        ("JSON aperçu", diagnostics["dashboard_api"]),
        ("JSON runtime", diagnostics["runtime_api"]),
        ("Santé", diagnostics["health"]),
    ]
    diagnostics_html = "".join(
        f'<a class="button secondary" href="{_escape(href)}">{_escape(label)}</a>'
        for label, href in diagnostics_links
    )

    status_html = (
        '<div class="status-line" role="status" aria-live="polite">'
        f'<span class="pill {_runtime_status_tone(str(current_runtime_status or "idle"))}">{_escape(_runtime_status_label(str(current_runtime_status or "idle")))}</span>'
        f'<span class="pill {_acquisition_status_tone(acquisition_status)}">{_escape(_acquisition_status_label(acquisition_status))}</span>'
        f'<span class="pill">Dernier scan {_escape(_format_optional_timestamp(freshness.get("latest_successful_scan_at")))}</span>'
        f'{"" if not runtime_timing_line else f"<span class=\"pill\">{_escape(runtime_timing_line)}</span>"}'
        '</div>'
    )

    hero_actions = "".join(
        [
            f'<a class="button secondary" href="{_escape(diagnostics["dashboard_api"])}">JSON aperçu</a>',
            f'<a class="button secondary" href="{_escape(diagnostics["health"])}">Santé</a>',
        ]
    )

    body_html = f"""
    <section class="cards" aria-label="Indicateurs clés">{cards_html}</section>
    <div class="layout">
      <div class="stack">
        <section class="panel" aria-labelledby="modules-title">
          <div class="panel-head">
            <h2 id="modules-title">Comparaisons à lire avec contexte</h2>
            <p>Les modules principaux restent visibles même quand le support est fragile. Le doute ne disparaît pas derrière la mise en page.</p>
          </div>
          <div class="module-grid">{modules_html}</div>
        </section>
        <section class="panel" aria-labelledby="listings-title">
          <div class="panel-head">
            <h2 id="listings-title">Annonces à ouvrir ensuite</h2>
            <p>Chaque carte ouvre l’explorateur, la fiche HTML ou le JSON de preuve sans quitter le shell du produit.</p>
          </div>
          {featured_html}
        </section>
      </div>
      <aside class="stack" aria-label="Contexte et honnêteté">
        <section class="panel" aria-labelledby="honesty-title">
          <div class="panel-head">
            <h2 id="honesty-title">Niveau d’honnêteté du signal</h2>
            <p>Approximation, inférence et support faible restent lisibles pour garder une lecture crédible du marché.</p>
          </div>
          <div class="note-list">{notes_html}</div>
        </section>
        <section class="panel" aria-labelledby="runtime-title">
          <div class="panel-head">
            <h2 id="runtime-title">Fraîcheur et incidents récents</h2>
            <p>Le marché affiché ici reflète la dernière vérité persistée, pas une reconstruction optimiste côté navigateur.</p>
          </div>
          {failure_html}
        </section>
        <section class="panel" aria-labelledby="diag-title">
          <div class="panel-head">
            <h2 id="diag-title">Surfaces de diagnostic</h2>
            <p>Quand une route semble incohérente, compare d’abord le HTML et son JSON jumeau sur la même base d’URL.</p>
          </div>
          <div class="button-row">{diagnostics_html}</div>
        </section>
      </aside>
    </div>
    """

    return _render_product_shell(
        page_key="home",
        title="Vinted Radar — aperçu du marché",
        eyebrow="Aperçu du marché",
        heading="Ce qui bouge maintenant sur le radar Vinted.",
        intro="Une lecture française, large et honnête du marché: volumes suivis, fraîcheur réelle, confiance, segments à surveiller et chemins directs vers l’exploration détaillée.",
        diagnostics=diagnostics,
        body_html=body_html,
        hero_actions=hero_actions,
        status_html=status_html,
        main_id="overview-main",
    )



def render_runtime_html(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    latest_cycle = payload.get("latest_cycle") or {}
    recent_cycles = payload.get("recent_cycles") or []
    recent_failures = payload.get("recent_failures") or []
    diagnostics = payload["diagnostics"]
    notes = payload.get("notes") or {}
    heartbeat = summary.get("heartbeat") or {}
    acquisition = payload.get("acquisition") or {}

    status = str(summary.get("status") or "idle")
    acquisition_status = str(summary.get("acquisition_status") or acquisition.get("status") or "unknown")
    status_label = _runtime_status_label(status)
    current_mode = _runtime_mode_label(summary.get("mode") or latest_cycle.get("mode"))
    controller_rows = [
        ("Statut courant", status_label),
        ("Phase", _runtime_phase_label(summary.get("phase"))),
        ("Mode", str(current_mode)),
        ("Dernier heartbeat", _format_optional_timestamp(summary.get("updated_at"))),
        ("Âge du heartbeat", _format_seconds_duration(heartbeat.get("age_seconds"))),
        ("Heartbeat périmé", "oui" if heartbeat.get("is_stale") else "non"),
        ("Cycle actif", str(summary.get("active_cycle_id") or "aucun")),
        ("Dernier cycle lié", str(summary.get("latest_cycle_id") or "aucun")),
    ]
    if summary.get("paused_at"):
        controller_rows.append(("Pause enregistrée à", _format_optional_timestamp(summary.get("paused_at"))))
        controller_rows.append(("Pause écoulée", _format_seconds_duration(summary.get("elapsed_pause_seconds"))))
    if summary.get("next_resume_at"):
        controller_rows.append(("Prochaine reprise", _format_optional_timestamp(summary.get("next_resume_at"))))
        controller_rows.append(("Temps restant", _format_seconds_duration(summary.get("next_resume_in_seconds"))))
    if summary.get("requested_action") and summary.get("requested_action") != "none":
        controller_rows.append(("Action opérateur en attente", str(summary.get("requested_action"))))
        controller_rows.append(("Demande horodatée", _format_optional_timestamp(summary.get("requested_at"))))
    if summary.get("last_error"):
        controller_rows.append(("Dernière erreur contrôleur", str(summary.get("last_error"))))
        controller_rows.append(("Erreur horodatée", _format_optional_timestamp(summary.get("last_error_at"))))

    controller_html = "".join(
        f'<div class="fact"><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
        for label, value in controller_rows
    )

    cycle_cards = "".join(
        f'''
        <article class="cycle-card">
          <div class="explorer-head">
            <div>
              <h3>Cycle {_escape(str(cycle.get('cycle_id') or 'n/a'))}</h3>
              <p class="subhead">{_escape(_runtime_phase_label(cycle.get('phase')))} · {_escape(str(cycle.get('mode') or 'n/a'))}</p>
            </div>
            <span class="pill {_runtime_status_tone(str(cycle.get('status') or 'idle'))}">{_escape(_runtime_status_label(str(cycle.get('status') or 'idle')))}</span>
          </div>
          <div class="meta-grid">
            <div class="meta-block"><span class="meta-label">Démarré</span><strong>{_escape(_format_optional_timestamp(cycle.get('started_at')))}</strong></div>
            <div class="meta-block"><span class="meta-label">Terminé</span><strong>{_escape(_format_optional_timestamp(cycle.get('finished_at')))}</strong></div>
            <div class="meta-block"><span class="meta-label">Annonces</span><strong>{_escape(str(cycle.get('tracked_listings') or 0))}</strong></div>
            <div class="meta-block"><span class="meta-label">Probes</span><strong>{_escape(str(cycle.get('state_probed_count') or 0))}</strong></div>
          </div>
        </article>
        '''
        for cycle in recent_cycles
    ) or '<div class="empty-state"><p>Aucun cycle runtime enregistré.</p></div>'

    failures_html = "".join(
        f"<li><strong>{_escape(str(cycle.get('cycle_id') or 'cycle inconnu'))}</strong><span>{_escape(str(cycle.get('last_error') or 'erreur inconnue'))}</span></li>"
        for cycle in recent_failures[:6]
    ) or '<li><strong>Aucun échec récent</strong><span>Le contrôleur n’a pas conservé de cycle en échec dans la fenêtre demandée.</span></li>'

    acquisition_reasons = list(acquisition.get("reasons") or [])
    acquisition_failures = list(acquisition.get("recent_scan_failures") or [])
    probe_issue_examples = list(acquisition.get("probe_issue_examples") or [])
    acquisition_rows = [
        ("Statut acquisition", _acquisition_status_label(acquisition_status)),
        ("Scans cassés récents", str(int(acquisition.get("recent_scan_failure_count") or 0))),
        ("Cycle acquisition", str(acquisition.get("latest_cycle_id") or "aucun")),
        ("Run discovery lié", str(acquisition.get("latest_discovery_run_id") or "aucun")),
    ]
    state_refresh_summary = acquisition.get("latest_state_refresh_summary") if isinstance(acquisition.get("latest_state_refresh_summary"), dict) else {}
    if state_refresh_summary:
        acquisition_rows.extend(
            [
                ("Probes dégradées", str(int(state_refresh_summary.get("degraded_probe_count") or 0))),
                ("Probes inconclusives", str(int(state_refresh_summary.get("inconclusive_probe_count") or 0))),
                ("Challenges anti-bot", str(int(state_refresh_summary.get("anti_bot_challenge_count") or 0))),
            ]
        )
    acquisition_html = "".join(
        f'<div class="fact"><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
        for label, value in acquisition_rows
    )
    acquisition_reason_html = "".join(
        f"<li><strong>{_escape(f'Raison {index + 1}')}</strong><span> — {_escape(_translate_acquisition_reason(reason))}</span></li>"
        for index, reason in enumerate(acquisition_reasons[:4])
    ) or '<li><strong>Aucun signal critique</strong><span> — La dernière discovery et le dernier state refresh paraissent sains.</span></li>'
    acquisition_failure_html = "".join(
        f"<li><strong>{_escape(str(item.get('catalog_path') or 'Catalogue inconnu'))}</strong><span> — {_escape(str(item.get('error_message') or item.get('response_status') or 'erreur inconnue'))}</span></li>"
        for item in acquisition_failures[:4]
    ) or '<li><strong>Aucun scan cassé</strong><span> — Le dernier run discovery ne garde pas d’échec de scan visible.</span></li>'
    probe_issue_html = "".join(
        f"<li><strong>{_escape(str(item.get('title') or item.get('listing_id') or 'annonce inconnue'))}</strong><span> — {_escape(str(item.get('reason') or item.get('probe_outcome') or 'unknown'))} · HTTP {_escape(str(item.get('response_status') or 'n/a'))}</span></li>"
        for item in probe_issue_examples[:4]
    ) or '<li><strong>Aucune probe dégradée</strong><span> — Les dernières probes persistées n’exposent pas de challenge ou panne critique.</span></li>'

    note_cards = "".join(
        f'<article class="note"><h3>{_escape(title)}</h3><p>{_escape(text)}</p></article>'
        for title, text in (
            ("Planifié", str(notes.get("scheduled") or "")),
            ("En pause", str(notes.get("paused") or "")),
            ("Échec", str(notes.get("failed") or "")),
        )
    )

    totals = payload.get("totals") or {}
    metrics_html = "".join(
        (
            _metric_card(
                "Statut courant",
                _escape(status_label),
                [
                    _runtime_status_description(status),
                    f"Mode {current_mode}",
                ],
            ),
            _metric_card(
                "Dernier heartbeat",
                _escape(_format_optional_timestamp(summary.get("updated_at"))),
                [
                    f"Âge {_format_seconds_duration(heartbeat.get('age_seconds'))}",
                    f"Périmé {'oui' if heartbeat.get('is_stale') else 'non'}",
                ],
            ),
            _metric_card(
                "Pause / reprise",
                _escape(_format_optional_timestamp(summary.get("next_resume_at") or summary.get("paused_at"))),
                [
                    f"Pause {_format_seconds_duration(summary.get('elapsed_pause_seconds'))}",
                    f"Reprise {_format_seconds_duration(summary.get('next_resume_in_seconds'))}",
                ],
            ),
            _metric_card(
                "Historique",
                _escape(str(totals.get("total_cycles") or 0)),
                [
                    f"Complétés {totals.get('completed_cycles') or 0}",
                    f"Échecs {totals.get('failed_cycles') or 0}",
                ],
            ),
        )
    )

    status_html = (
        '<div class="status-line" role="status" aria-live="polite">'
        f'<span class="pill {_runtime_status_tone(status)}">{_escape(status_label)}</span>'
        f'<span class="pill {_acquisition_status_tone(acquisition_status)}">{_escape(_acquisition_status_label(acquisition_status))}</span>'
        f'<span class="pill">Phase {_escape(_runtime_phase_label(summary.get("phase")))}</span>'
        f'<span class="pill">Mode {_escape(str(current_mode))}</span>'
        '</div>'
    )

    hero_actions = "".join(
        [
            f'<a class="button secondary" href="{_escape(diagnostics["runtime_api"])}">JSON runtime</a>',
            f'<a class="button secondary" href="{_escape(diagnostics["health"])}">Santé</a>',
        ]
    )

    body_html = f"""
    <section class="metrics" aria-label="Indicateurs runtime">{metrics_html}</section>
    <div class="layout">
      <div class="stack">
        <section class="panel" aria-labelledby="controller-title">
          <div class="panel-head">
            <h2 id="controller-title">État courant du contrôleur</h2>
            <p>Cette vue répond à la question « que fait le radar maintenant ? » sans confondre attente saine, pause opérateur et dernier résultat de cycle.</p>
          </div>
          <div class="facts">{controller_html}</div>
        </section>
        <section class="panel" aria-labelledby="acquisition-title">
          <div class="panel-head">
            <h2 id="acquisition-title">Santé d’acquisition</h2>
            <p>Le contrôleur peut être sain tout en lisant un marché partiel ou dégradé. Cette section garde visible la faiblesse discovery + probe du dernier cycle exploitable.</p>
          </div>
          <div class="facts">{acquisition_html}</div>
          <div class="layout" style="margin-top:16px; gap:16px;">
            <section class="panel" style="margin:0; padding:18px;" aria-labelledby="acquisition-reasons-title">
              <div class="panel-head"><h3 id="acquisition-reasons-title">Pourquoi ce statut</h3></div>
              <ul class="failure-list">{acquisition_reason_html}</ul>
            </section>
            <section class="panel" style="margin:0; padding:18px;" aria-labelledby="acquisition-failures-title">
              <div class="panel-head"><h3 id="acquisition-failures-title">Scans discovery en échec</h3></div>
              <ul class="failure-list">{acquisition_failure_html}</ul>
            </section>
            <section class="panel" style="margin:0; padding:18px;" aria-labelledby="probe-issues-title">
              <div class="panel-head"><h3 id="probe-issues-title">Exemples de probes dégradées</h3></div>
              <ul class="failure-list">{probe_issue_html}</ul>
            </section>
          </div>
        </section>
        <section class="panel" aria-labelledby="cycles-title">
          <div class="panel-head">
            <h2 id="cycles-title">Cycles récents</h2>
            <p>Les cycles restent l’historique immuable. Le contrôleur au-dessus reste la vérité vivante du scheduler.</p>
          </div>
          <div class="cycle-grid">{cycle_cards}</div>
        </section>
      </div>
      <aside class="stack">
        <section class="panel" aria-labelledby="failures-title">
          <div class="panel-head">
            <h2 id="failures-title">Échecs récents</h2>
            <p>Un échec reste lisible ici même si la boucle repart ensuite en `scheduled`.</p>
          </div>
          <ul class="failure-list">{failures_html}</ul>
        </section>
        <section class="panel" aria-labelledby="semantics-title">
          <div class="panel-head">
            <h2 id="semantics-title">Sémantique du runtime</h2>
            <p>Ces définitions évitent les faux positifs du type « terminé » alors que le scheduler attend simplement la prochaine fenêtre.</p>
          </div>
          <div class="note-grid">{note_cards}</div>
        </section>
      </aside>
    </div>
    """

    return _render_product_shell(
        page_key="runtime",
        title="Vinted Radar — runtime",
        eyebrow="Runtime",
        heading="Le contrôleur vivant du radar, sans deviner à partir du dernier cycle.",
        intro="Statut courant, heartbeat, pause, prochaine reprise, erreurs récentes et séparation nette entre l’état actuel et l’historique immuable des cycles.",
        diagnostics=diagnostics,
        body_html=body_html,
        hero_actions=hero_actions,
        status_html=status_html,
        main_id="runtime-main",
    )



def render_listing_detail_html(detail: dict[str, Any]) -> str:
    diagnostics = detail.get("diagnostics") if isinstance(detail.get("diagnostics"), dict) else {}
    explorer_context = detail.get("explorer_context") if isinstance(detail.get("explorer_context"), dict) else {}
    detail_panel = _render_detail_panel(detail)
    hero_actions = "".join(
        part
        for part in (
            "" if not explorer_context.get("back_href") else f'<a class="button" href="{_escape(str(explorer_context["back_href"]))}">Retour aux résultats</a>',
            f'<a class="button secondary" href="{_escape(str(diagnostics.get("detail_api") or "#"))}">JSON détail</a>',
            "" if not explorer_context.get("back_api") else f'<a class="button secondary" href="{_escape(str(explorer_context["back_api"]))}">JSON explorateur</a>',
        )
    )
    context_summary_pill = ""
    if explorer_context.get("summary"):
        context_summary_pill = f'<span class="pill info">{_escape(str(explorer_context["summary"]))}</span>'
    status_html = (
        '<div class="status-line">'
        f'<span class="pill {_escape(str(detail.get("state_code") or "unknown"))}">{_escape(_state_label(detail.get("state_code")))}</span>'
        f'<span class="pill">{_escape(_basis_label(detail.get("basis_kind")))}</span>'
        f'<span class="pill">Confiance {_escape(_confidence_label(detail.get("confidence_label")))}</span>'
        f'{context_summary_pill}'
        '</div>'
    )
    body_html = f'<section class="panel">{detail_panel}</section>'
    return _render_product_shell(
        page_key="detail",
        title=f"Vinted Radar — annonce {int(detail['listing_id'])}",
        eyebrow="Fiche annonce",
        heading=str(detail.get("title") or f"Annonce {int(detail['listing_id'])}"),
        intro="Une lecture produit d’abord, puis les preuves radar dépliables : l’état, le prix, la temporalité et la chronologie restent inspectables sans prendre toute la page.",
        diagnostics=diagnostics,
        body_html=body_html,
        hero_actions=hero_actions,
        status_html=status_html,
        main_id="listing-main",
    )



def _serialize_overview_listing_item(item: dict[str, Any], *, route_context: RouteContext | None = None) -> dict[str, Any]:
    return _serialize_explorer_item(item, route_context=route_context)



def _build_explorer_context(
    filters: ExplorerFilters,
    *,
    available: dict[str, Any],
    route_context: RouteContext,
) -> dict[str, Any]:
    active_filters: list[dict[str, str]] = []

    def add_filter(key: str, label: str, value: Any, *, available_key: str | None = None) -> None:
        if value in {None, "", "all"}:
            return
        rendered_value = _resolve_explorer_filter_value_label(available, available_key or key, value)
        active_filters.append({"key": key, "label": label, "value": rendered_value})

    add_filter("root", "Racine", filters.root, available_key="roots")
    add_filter("catalog_id", "Catalogue", filters.catalog_id, available_key="catalogs")
    add_filter("brand", "Marque", filters.brand, available_key="brands")
    add_filter("condition", "État", filters.condition, available_key="conditions")
    add_filter("state", "Statut radar", filters.state, available_key="states")
    add_filter("price_band", "Tranche de prix", filters.price_band, available_key="price_bands")
    if filters.query:
        active_filters.append({"key": "q", "label": "Recherche", "value": filters.query})
    if filters.sort != "last_seen_desc":
        active_filters.append(
            {
                "key": "sort",
                "label": "Tri",
                "value": _resolve_explorer_filter_value_label(available, "sorts", filters.sort),
            }
        )
    if filters.page != 1:
        active_filters.append({"key": "page", "label": "Page", "value": str(filters.page)})
    if filters.page_size != DEFAULT_EXPLORER_PAGE_SIZE:
        active_filters.append({"key": "page_size", "label": "Taille de page", "value": str(filters.page_size)})

    back_href = _explorer_query(filters, base_href=route_context.path("/explorer"))
    back_api = route_context.path("/api/explorer") + _explorer_suffix_query(filters)
    summary = "Vue large du corpus suivi" if not active_filters else "Vue active — " + " · ".join(
        f"{item['label']} : {item['value']}" for item in active_filters
    )
    return {
        "active_filters": active_filters,
        "summary": summary,
        "back_href": back_href,
        "back_api": back_api,
        "has_context": bool(filters.to_query_dict()),
    }



def _hydrate_explorer_comparison_links(
    comparisons: dict[str, Any],
    *,
    filters: ExplorerFilters,
    base_href: str,
) -> dict[str, Any]:
    hydrated: dict[str, Any] = {}
    for key, module in comparisons.items():
        if not isinstance(module, dict):
            hydrated[key] = module
            continue
        rows: list[dict[str, Any]] = []
        for row in module.get("rows") or []:
            row_payload = dict(row)
            drilldown = row_payload.get("drilldown") if isinstance(row_payload.get("drilldown"), dict) else {}
            row_filters = drilldown.get("filters") if isinstance(drilldown.get("filters"), dict) else {}
            if not isinstance(row_filters, dict):
                row_filters = {}
            hydrated_drilldown = dict(drilldown)
            hydrated_drilldown["href"] = _explorer_query(
                filters,
                base_href=base_href,
                overrides=row_filters,
            )
            row_payload["drilldown"] = hydrated_drilldown
            rows.append(row_payload)
        hydrated[key] = {**module, "rows": rows}
    return hydrated



def _resolve_explorer_filter_value_label(available: dict[str, Any], available_key: str, value: Any) -> str:
    options = available.get(available_key) if isinstance(available, dict) else None
    if isinstance(options, list):
        for option in options:
            if str(option.get("value")) == str(value):
                return _strip_option_count_suffix(str(option.get("label") or value))
    return _display_explorer_filter_value(available_key, value)



def _strip_option_count_suffix(label: str) -> str:
    head, sep, tail = label.rpartition(" (")
    if sep and tail.endswith(")") and tail[:-1].isdigit():
        return head
    return label



def _display_explorer_filter_value(key: str, value: Any) -> str:
    if key == "states":
        return _state_label(value)
    if key == "price_bands":
        labels = {
            "under_20_eur": "< 20 €",
            "20_to_39_eur": "20–39 €",
            "40_plus_eur": "40 € et plus",
            "unknown": "Prix indisponible",
        }
        return labels.get(str(value), str(value))
    if key == "sorts":
        return _localized_explorer_option_label(str(value))
    if key == "brands" and str(value) == "unknown-brand":
        return "Marque inconnue"
    if key == "conditions" and str(value) == "unknown-condition":
        return "État inconnu"
    return str(value)



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

    probe_issue_count = int(freshness.get("recent_probe_issue_count") or 0)
    inconclusive_probe_count = int(freshness.get("recent_inconclusive_probe_count") or 0)
    acquisition_status = str(freshness.get("acquisition_status") or "")
    if probe_issue_count:
        notes.append(
            {
                "slug": "degraded-state-refresh",
                "level": "danger",
                "title": "Probes item-page dégradées",
                "count": probe_issue_count,
                "description": f"{probe_issue_count} probes récentes ont rencontré un challenge anti-bot, une erreur HTTP, ou une panne transport ; l’historique radar redevient alors le signal le plus prudent.",
            }
        )
    elif acquisition_status == "partial" or inconclusive_probe_count:
        notes.append(
            {
                "slug": "partial-state-refresh",
                "level": "warning",
                "title": "Probes encore partielles",
                "count": inconclusive_probe_count,
                "description": f"{inconclusive_probe_count} probes récentes sont restées inconclusives ; la lecture continue, mais certaines annonces reposent surtout sur l’historique radar.",
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



def _translate_acquisition_reason(reason: str) -> str:
    patterns = (
        (r"^(\d+) failed catalog scans remain visible on the latest discovery run\.$", "{count} scans discovery en échec restent visibles sur le dernier run lié."),
        (r"^(\d+) state-refresh probes hit anti-bot or challenge-shaped pages\.$", "{count} probes de state refresh ont rencontré un anti-bot ou une page de challenge."),
        (r"^(\d+) state-refresh probes failed on transport exceptions\.$", "{count} probes de state refresh ont échoué côté transport."),
        (r"^(\d+) state-refresh probes ended on unexpected HTTP responses\.$", "{count} probes de state refresh se sont terminées sur des réponses HTTP inattendues."),
        (r"^(\d+) latest state-refresh probes stayed inconclusive, so history remains the safer signal\.$", "{count} probes récentes sont restées inconclusives ; l’historique radar reste donc le signal le plus prudent."),
    )
    for pattern, template in patterns:
        match = re.match(pattern, reason)
        if match:
            return template.format(count=match.group(1))
    static = {
        "No discovery run or runtime cycle is recorded yet.": "Aucun run discovery ni cycle runtime n’est encore enregistré.",
        "Latest discovery and state-refresh signals look operationally healthy.": "Les derniers signaux discovery + state refresh paraissent opérationnellement sains.",
    }
    return static.get(reason, reason)



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
    drilldown = row.get("drilldown") if isinstance(row.get("drilldown"), dict) else {}
    filters = drilldown.get("filters") if isinstance(drilldown.get("filters"), dict) else {}
    if not isinstance(filters, dict):
        filters = {}

    average_price = inventory.get("average_price_amount_cents")
    average_price_display = "n/a" if average_price is None else _format_money(round(float(average_price)), "€")
    support_share = float(inventory.get("support_share") or 0.0) * 100.0
    filters_label = _describe_drilldown_filters(filters)
    drilldown_href = drilldown.get("href") or _explorer_href_from_filters(filters, fallback=explorer_href)
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
                <a class="button secondary" href="{_escape(str(item.get("detail_href") or "#"))}">Détail</a>
                <a class="button secondary" href="{_escape(str(item.get("detail_api") or "#"))}">JSON détail</a>
                {canonical_link}
              </div>
            </article>
            '''
        )
    return '<div class="listing-grid">' + "".join(cards) + '</div>'



def _explorer_href_from_filters(filters: dict[str, Any], *, fallback: str = "/explorer") -> str:
    supported_keys = {"root", "catalog_id", "brand", "condition", "price_band", "state", "q", "sort", "page", "page_size"}
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
    active_filters = payload["filters"].get("active") or []
    filter_summary = str(payload["filters"].get("summary") or "Vue large du corpus suivi")
    results = payload["results"]
    diagnostics = payload["diagnostics"]
    notes = payload.get("notes") or {}
    acquisition_status = str(notes.get("acquisition_status") or "unknown")
    acquisition_reasons = list(notes.get("acquisition_reasons") or [])
    items = payload["items"]
    summary = payload.get("summary") or {}
    summary_inventory = summary.get("inventory") if isinstance(summary.get("inventory"), dict) else {}
    summary_honesty = summary.get("honesty") if isinstance(summary.get("honesty"), dict) else {}
    comparisons = payload.get("comparisons") or {}
    filters = ExplorerFilters(
        root=None if selected["root"] == "all" else selected["root"],
        catalog_id=selected["catalog_id"],
        brand=None if selected["brand"] == "all" else selected["brand"],
        condition=None if selected["condition"] == "all" else selected["condition"],
        state=None if selected["state"] == "all" else selected["state"],
        price_band=None if selected["price_band"] == "all" else selected["price_band"],
        query=selected["q"] or None,
        sort=str(selected["sort"]),
        page=int(selected["page"]),
        page_size=int(selected["page_size"]),
    )

    root_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["root"]) for item in available["roots"])
    catalog_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["catalog_id"]) for item in available["catalogs"])
    brand_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["brand"]) for item in available["brands"])
    condition_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["condition"]) for item in available["conditions"])
    state_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["state"]) for item in available["states"])
    price_band_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["price_band"]) for item in available["price_bands"])
    sort_options = "".join(_option_html(item["value"], _localized_explorer_option_label(item["label"]), selected["sort"]) for item in available["sorts"])
    page_size_options = "".join(_option_html(str(value), str(value), selected["page_size"]) for value in (12, 24, 48, 100))
    selected_sort_label = next((_localized_explorer_option_label(item["label"]) for item in available["sorts"] if item["value"] == selected["sort"]), str(selected["sort"]))

    active_filters_html = "".join(
        f'<span class="badge info">{_escape(str(item["label"]))} · {_escape(str(item["value"]))}</span>'
        for item in active_filters
    ) or '<span class="badge ok">Vue large du corpus</span>'

    comparison_modules_html = "".join(
        _render_comparison_module(module, explorer_href=diagnostics["explorer"])
        for module in comparisons.values()
    ) or '<div class="empty-state"><p>Aucun module de comparaison n’est disponible pour cette tranche du corpus.</p></div>'

    explorer_cards = "".join(
        f'''
        <article class="explorer-item">
          <div class="explorer-head">
            <div>
              <h3>{_escape(str(item.get('title') or 'Annonce sans titre'))}</h3>
              <p class="subhead">#{int(item['listing_id'])} · {_escape(str(item.get('brand') or 'Marque inconnue'))}</p>
            </div>
            <div class="listing-stats">
              <span class="badge ok">{_escape(str(item.get('price_display') or 'prix n/a'))}</span>
              <span class="badge">{_escape(_freshness_label(item.get('freshness_bucket')))}</span>
              <span class="badge">{_escape(str(item.get('state_display') or _state_label(item.get('state_code'))))}</span>
              <span class="badge">Confiance {_escape(str(item.get('confidence_display') or _confidence_label(item.get('confidence_label'))))}</span>
            </div>
          </div>
          <div class="meta-grid">
            <div class="meta-block">
              <span class="meta-label">Catalogue</span>
              <strong>{_escape(str(item.get('primary_catalog_path') or item.get('root_title') or 'Catalogue inconnu'))}</strong>
              <span class="link-muted">État {_escape(str(item.get('condition_label') or 'n/a'))}</span>
            </div>
            <div class="meta-block">
              <span class="meta-label">Lecture radar</span>
              <strong>{_escape(str(item.get('state_display') or _state_label(item.get('state_code'))))}</strong>
              <span class="link-muted">Base {_escape(str(item.get('basis_display') or _basis_label(item.get('basis_kind'))))}</span>
            </div>
            <div class="meta-block">
              <span class="meta-label">Vendeur visible</span>
              <strong>{'<a class="listing-link" href="' + _escape(str(item.get('seller_profile_url'))) + '" target="_blank" rel="noreferrer">' + _escape(str(item.get('seller_display') or 'Vendeur non exposé')) + '</a>' if item.get('seller_profile_url') else _escape(str(item.get('seller_display') or 'Vendeur non exposé'))}</strong>
              <span class="link-muted">Likes {_escape(str(item.get('visible_likes_display') or 'n/a'))} · Vues {_escape(str(item.get('visible_views_display') or 'n/a'))}</span>
            </div>
            <div class="meta-block">
              <span class="meta-label">Publication estimée</span>
              <strong>{_escape(str(item.get('estimated_publication_at') or 'n/a'))}</strong>
              <span class="link-muted">{_escape(str(item.get('estimated_publication_note') or 'Signal indisponible'))}</span>
            </div>
            <div class="meta-block">
              <span class="meta-label">Radar</span>
              <strong>{_escape(str(item.get('radar_first_seen_display') or 'n/a'))}</strong>
              <span class="link-muted">Dernière vue {_escape(str(item.get('radar_last_seen_display') or 'n/a'))}</span>
            </div>
            <div class="meta-block">
              <span class="meta-label">Dernière probe</span>
              <strong>{_escape(str(item.get('latest_probe_display') or 'Aucune probe'))}</strong>
              <span class="link-muted">{_escape(str(item.get('observation_count') or 0))} observations · {int(item.get('follow_up_miss_count') or 0)} ratés</span>
            </div>
          </div>
          <div class="actions">
            <a class="button" href="{_escape(str(item.get('detail_href') or '#'))}">Ouvrir la fiche</a>
            <a class="button secondary" href="{_escape(str(item.get('detail_api') or '#'))}">JSON</a>
            <a class="button secondary" href="{_escape(str(item.get('explorer_href') or diagnostics['explorer']))}">Vue ciblée</a>
            {'' if not item.get('canonical_href') else f'<a class="button secondary" href="{_escape(str(item.get("canonical_href")))}" target="_blank" rel="noreferrer">Vinted</a>'}
          </div>
        </article>
        '''
        for item in items
    ) or f'<div class="empty-state"><p>{_escape(str(results.get("empty_reason") or "Aucune annonce suivie ne correspond à ces filtres."))}</p></div>'

    previous_href = _explorer_query(filters, base_href=diagnostics["explorer"], overrides={"page": max(filters.page - 1, 1)})
    next_href = _explorer_query(filters, base_href=diagnostics["explorer"], overrides={"page": filters.page + 1})

    average_price_display = "n/a" if summary_inventory.get("average_price_amount_cents") is None else _format_money(round(float(summary_inventory["average_price_amount_cents"])), "€")
    status_html = (
        '<div class="status-line" role="status" aria-live="polite">'
        f'<span class="pill">{_escape(str(results["total_listings"]))} annonces</span>'
        f'<span class="pill">Page {results["page"]}/{results["total_pages"] or 1}</span>'
        f'<span class="pill">Tri {_escape(str(selected_sort_label))}</span>'
        f'<span class="pill {_acquisition_status_tone(acquisition_status)}">{_escape(_acquisition_status_label(acquisition_status))}</span>'
        f'<span class="pill">Support modules {int(summary_inventory.get("comparison_support_threshold") or 0)}+</span>'
        '</div>'
    )

    acquisition_notice_html = ""
    if acquisition_status in {"partial", "degraded"}:
        acquisition_notice_html = (
            f'<article class="note {_acquisition_status_tone(acquisition_status)}" style="margin-top:16px;">'
            f'<div class="note-title"><strong>{_escape(_acquisition_status_label(acquisition_status))}</strong></div>'
            f'<p class="muted">{_escape(_translate_acquisition_reason(str(acquisition_reasons[0] if acquisition_reasons else "Le radar garde la tranche visible, mais certaines probes ou certains scans récents restent fragiles.")))}</p>'
            '</article>'
        )

    hero_actions = f'<a class="button secondary" href="{_escape(diagnostics["explorer_api"] + _explorer_suffix_query(filters))}">JSON explorateur</a>'

    body_html = f"""
    <section class="panel" aria-labelledby="filters-title">
      <div class="panel-head">
        <h2 id="filters-title">Filtres d’exploration</h2>
        <p>{_escape(filter_summary)}</p>
      </div>
      <form method="get" class="filters">
        <label>Racine<select name="root">{root_options}</select></label>
        <label>Catalogue<select name="catalog_id">{catalog_options}</select></label>
        <label>Marque<select name="brand">{brand_options}</select></label>
        <label>État<select name="condition">{condition_options}</select></label>
        <label>Statut radar<select name="state">{state_options}</select></label>
        <label>Tranche de prix<select name="price_band">{price_band_options}</select></label>
        <label>Recherche<input type="search" name="q" value="{_escape(selected['q'])}" placeholder="Titre, marque, vendeur, ID annonce"></label>
        <label>Tri<select name="sort">{sort_options}</select></label>
        <label>Taille de page<select name="page_size">{page_size_options}</select></label>
        <input type="hidden" name="page" value="1">
        <div class="actions">
          <button class="button" type="submit">Appliquer</button>
          <a class="button secondary" href="{_escape(diagnostics['explorer'])}">Réinitialiser</a>
        </div>
      </form>
      <div class="status-line" style="margin-top:16px;">{active_filters_html}</div>
      {acquisition_notice_html}
      <div class="cards" style="margin-top:16px;">
        {_metric_card("Résultats", _escape(str(summary_inventory.get('matched_listings', 0))), [f"{results['active_filter_count']} filtre(s) actifs", f"Corpus total {available['tracked_listings']}"])}
        {_metric_card("Lecture de vente", _escape(str(summary_inventory.get('sold_like_count', 0))), [f"Actives {summary_inventory.get('state_counts', {}).get('active', 0)}", f"Vendues-like {summary_inventory.get('state_counts', {}).get('sold_observed', 0) + summary_inventory.get('state_counts', {}).get('sold_probable', 0)}"])}
        {_metric_card("Honnêteté", _escape(str(summary_honesty.get('observed_state_count', 0))), [f"Inférées {summary_honesty.get('inferred_state_count', 0)}", f"Signal mince {summary_honesty.get('thin_signal_count', 0)}"])}
        {_metric_card("Prix moyen", _escape(average_price_display), [f"Publication estimée {summary_honesty.get('estimated_publication_count', 0)}", f"Règle {notes.get('support_rule', '')}"])}
      </div>
    </section>

    <section class="panel" aria-labelledby="comparisons-title">
      <div class="panel-head">
        <h2 id="comparisons-title">Comparer la tranche affichée</h2>
        <p>{_escape(str(notes.get('support_rule') or ''))}</p>
      </div>
      <div class="module-grid">{comparison_modules_html}</div>
    </section>

    <section class="panel" aria-labelledby="results-title">
      <div class="panel-head">
        <h2 id="results-title">Annonces du corpus</h2>
        <p>{_escape(str(notes.get('estimated_publication') or ''))}</p>
      </div>
      <div class="explorer-grid">{explorer_cards}</div>
      <div class="pagination" style="margin-top:16px;">
        <a class="button secondary{' disabled' if not results['has_previous_page'] else ''}" href="{_escape(previous_href)}">Page précédente</a>
        <span class="link-muted">Page {results['page']} sur {results['total_pages'] or 1}</span>
        <a class="button secondary{' disabled' if not results['has_next_page'] else ''}" href="{_escape(next_href)}">Page suivante</a>
      </div>
    </section>
    """

    return _render_product_shell(
        page_key="explorer",
        title="Vinted Radar — explorateur",
        eyebrow="Explorateur",
        heading="Parcourir, comparer et filtrer le corpus réel.",
        intro="L’explorateur travaille maintenant sur une tranche SQL complète : filtres, comparaisons, support, pagination et retour contextuel vers la fiche d’annonce.",
        diagnostics=diagnostics,
        body_html=body_html,
        hero_actions=hero_actions,
        status_html=status_html,
        main_id="explorer-main",
    )



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
          <button class=\"button\" type=\"submit\">Appliquer</button>
          <a class=\"button secondary\" href=\"/\">Réinitialiser</a>
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
                <div class=\"link-muted\">{_escape(str(row.get('brand') or 'Marque inconnue'))}</div>
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
        return '<div><h2>Aucune fiche sélectionnée</h2><p class="subhead">Choisis une annonce depuis l’explorateur pour lire son historique, ses scores et sa base d’inférence.</p></div>'

    narrative = detail.get("narrative") if isinstance(detail.get("narrative"), dict) else {}
    provenance = detail.get("provenance") if isinstance(detail.get("provenance"), dict) else {}
    state_explanation = detail.get("state_explanation") if isinstance(detail.get("state_explanation"), dict) else {}
    score_explanation = detail.get("score_explanation") if isinstance(detail.get("score_explanation"), dict) else {}
    score_context = score_explanation.get("context") if isinstance(score_explanation, dict) else None
    score_context_html = (
        f"<li>Contexte {_escape(_detail_score_context_label(str(score_context.get('label') or 'unknown')))} · pairs {score_context.get('sample_size', 0)} · lecture prix {_escape(_detail_price_percentile_summary(score_context.get('price_percentile')))}</li>"
        if score_context is not None
        else "<li>Aucun contexte premium assez solide pour cette annonce pour l’instant.</li>"
    )
    history_rows = detail["history"]["timeline"] if detail.get("history") else []
    history_html = "".join(
        f"<div class=\"timeline-item\"><strong>{_escape(str(row.get('observed_at') or 'inconnu'))}</strong><span>{_escape(_format_money(row.get('price_amount_cents'), row.get('price_currency')))} · {_escape(str(row.get('catalog_path') or 'Catalogue inconnu'))} · apparitions {row.get('sighting_count', 0)}</span></div>"
        for row in history_rows
    ) or "<div class=\"timeline-item\"><span>Aucune timeline d’observation enregistrée.</span></div>"
    transitions_html = "".join(
        f"<div class=\"timeline-item\"><strong>{_escape(str(item['label']))}</strong><span>{_escape(str(item['timestamp']))}</span><br><span>{_escape(str(item['description']))}</span></div>"
        for item in detail["transitions"]
    )
    state_reasons = state_explanation.get("reasons") if isinstance(state_explanation.get("reasons"), list) else []
    score_factors = score_explanation.get("factors") if isinstance(score_explanation.get("factors"), dict) else {}
    seller = detail.get("seller") if isinstance(detail.get("seller"), dict) else {}
    timing = detail.get("timing") if isinstance(detail.get("timing"), dict) else {}
    explorer_context = detail.get("explorer_context") if isinstance(detail.get("explorer_context"), dict) else {}
    context_filters = explorer_context.get("active_filters") if isinstance(explorer_context.get("active_filters"), list) else []
    context_filter_html = "".join(
        f'<span class="badge info">{_escape(str(item.get("label") or "Filtre"))} · {_escape(str(item.get("value") or ""))}</span>'
        for item in context_filters
    ) or '<span class="badge ok">Vue large du corpus</span>'
    seller_html = (
        f'<a class="link-muted" href="{_escape(str(seller.get("profile_url")))}" target="_blank" rel="noreferrer">{_escape(str(seller.get("login") or seller.get("display") or "Vendeur non exposé"))}</a>'
        if seller.get("profile_url")
        else f'<span class="link-muted">{_escape(str(seller.get("display") or "Vendeur non exposé"))}</span>'
    )
    highlight_cards = narrative.get("highlights") if isinstance(narrative.get("highlights"), list) else []
    highlight_html = "".join(
        f'''
        <article class="signal story-card">
          <div class="section-title">
            <span class="signal-label">{_escape(str(item.get("title") or "Lecture"))}</span>
            <span class="badge {_escape(_detail_tone_class(str(item.get("tone") or "info")))}">{_escape(_detail_provenance_label(str(item.get("provenance") or "observed")))}</span>
          </div>
          <strong>{_escape(str(item.get("headline") or item.get("title") or ""))}</strong>
          <p class="shell-copy">{_escape(str(item.get("body") or item.get("summary") or ""))}</p>
        </article>
        '''
        for item in highlight_cards
    )
    risk_notes = narrative.get("risk_notes") if isinstance(narrative.get("risk_notes"), list) else []
    risk_html = "".join(
        f'''
        <article class="note">
          <div class="section-title">
            <h3>{_escape(str(note.get("title") or "Point de prudence"))}</h3>
            <span class="badge {_escape(_detail_tone_class(str(note.get("tone") or "info")))}">prudence</span>
          </div>
          <p>{_escape(str(note.get("body") or ""))}</p>
        </article>
        '''
        for note in risk_notes
    ) or '<div class="empty-state"><p>Aucun point de prudence supplémentaire ne remonte sur cette annonce.</p></div>'
    provenance_cards = "".join(
        f'''
        <article class="fact">
          <span>{_escape(str(item.get("label") or "Provenance"))}</span>
          <strong>{_escape(str(item.get("summary") or "n/a"))}</strong>
          <span class="link-muted">Source { _escape(str(item.get("source") or "n/a")) }</span>
          <span class="link-muted">Valeur { _escape(str(item.get("value") or item.get("latest_probe") or "n/a")) }</span>
        </article>
        '''
        for item in provenance.values()
        if isinstance(item, dict)
    )
    public_fields_html = f'''
      <div class="compact-grid">
        <div class="signal"><span class="signal-label">Prix public</span><strong>{_escape(str(detail.get('price_display') or 'prix n/a'))}</strong><span class="link-muted">total affiché { _escape(str(detail.get('total_price_display') or 'n/a')) }</span></div>
        <div class="signal"><span class="signal-label">Catalogue</span><strong>{_escape(str(detail.get('primary_catalog_path') or detail.get('root_title') or 'Catalogue inconnu'))}</strong><span class="link-muted">Marque { _escape(str(detail.get('brand') or 'Inconnue')) } · Taille { _escape(str(detail.get('size_label') or 'n/a')) } · État { _escape(str(detail.get('condition_label') or 'n/a')) }</span></div>
        <div class="signal"><span class="signal-label">Vendeur visible</span>{seller_html}<span class="link-muted">Likes { _escape(str(detail.get('engagement', {}).get('visible_likes') if isinstance(detail.get('engagement'), dict) else 'n/a')) } · vues { _escape(str(detail.get('engagement', {}).get('visible_views') if isinstance(detail.get('engagement'), dict) else 'n/a')) }</span></div>
      </div>
    '''

    return f"""
      <div class=\"story-hero\">
        <span class=\"eyebrow\">Ce que le radar voit d’abord</span>
        <h2>{_escape(str(narrative.get('headline') or detail.get('title') or '(sans titre)'))}</h2>
        <p class=\"lead\">{_escape(str(narrative.get('summary') or 'Lecture narrative indisponible.'))}</p>
        <p class=\"subhead\">{_escape(str(detail.get('primary_catalog_path') or detail.get('root_title') or 'Catalogue inconnu'))}</p>
        <div class=\"status-line\">
          <span class=\"pill { _escape(str(detail.get('state_code') or 'unknown')) }\">{_escape(_state_label(detail.get('state_code')))}</span>
          <span class=\"pill\">{_escape(_basis_label(detail.get('basis_kind')))}</span>
          <span class=\"pill\">Confiance {_escape(_confidence_label(detail.get('confidence_label')))}</span>
          <span class=\"pill info\">Demande {_escape(_format_score(detail.get('demand_score')))}</span>
          <span class=\"pill info\">Premium {_escape(_format_score(detail.get('premium_score')))}</span>
        </div>
        <div class=\"signal\">
          <span class=\"signal-label\">Contexte explorateur</span>
          <strong>{_escape(str(explorer_context.get('summary') or 'Vue directe sans filtre mémorisé'))}</strong>
          <p class=\"shell-copy\">{_escape(str(narrative.get('explorer_angle') or 'Le contexte actif reste visible pour comprendre pourquoi cette annonce a été ouverte depuis l’explorateur.'))}</p>
          <div class=\"status-line\" style=\"margin-top:10px;\">{context_filter_html}</div>
        </div>
      </div>
      <section class=\"stack\" aria-labelledby=\"story-title\">
        <div class=\"panel-head\">
          <h2 id=\"story-title\">Lecture utile avant la preuve</h2>
          <p>{_escape(str(narrative.get('proof_guide') or 'La preuve détaillée reste disponible plus bas.'))}</p>
        </div>
        <div class=\"detail-grid\">{highlight_html}</div>
      </section>
      <section class=\"stack\" aria-labelledby=\"limits-title\">
        <div class=\"panel-head\">
          <h2 id=\"limits-title\">Repères et limites visibles</h2>
          <p>Le produit garde ici les précautions qui empêchent la fiche de sur-promettre ce que le signal public ne prouve pas encore.</p>
        </div>
        <div class=\"note-grid\">{risk_html}</div>
        <div class=\"provenance-grid\">{provenance_cards}</div>
      </section>
      <section class=\"stack\" aria-labelledby=\"proof-title\">
        <div class=\"panel-head\">
          <h2 id=\"proof-title\">Preuves techniques et détails</h2>
          <p>Déplie seulement ce dont tu as besoin : la lecture produit reste devant, le raisonnement complet reste juste derrière.</p>
        </div>
        <div class=\"proof-stack\">
          {_render_detail_proof_section('Preuve d’état', 'Pourquoi le radar classe cette annonce ainsi.', f'<ul class="bullet-list">{"".join(f"<li>{_escape(_detail_state_reason(reason))}</li>" for reason in state_reasons) or "<li>Aucune explication d’état disponible.</li>"}</ul>')}
          {_render_detail_proof_section('Contexte de score', 'Décomposition du signal demande/premium et contexte de prix.', f'<ul class="bullet-list">{"".join(f"<li>{_escape(_detail_score_factor_label(name))}: {_format_score(value)}</li>" for name, value in score_factors.items())}{score_context_html}</ul>')}
          {_render_detail_proof_section('Chronologie radar', 'Publication estimée, fenêtre radar, transitions et historique d’observation.', f'<div class="stack"><div>{public_fields_html}</div><div><h3>Repères temporels</h3><ul class="bullet-list"><li>Publication estimée : {_escape(str(timing.get("publication_estimated_at") or "n/a"))}</li><li>Premier vu radar : {_escape(_format_optional_timestamp(timing.get("radar_first_seen_at")))}</li><li>Dernier vu radar : {_escape(_format_optional_timestamp(timing.get("radar_last_seen_at")))}</li></ul></div><div><h3>Chemin de transition</h3><div class="timeline">{transitions_html}</div></div><div><h3>Timeline d’observation</h3><div class="timeline">{history_html}</div></div></div>')}
        </div>
      </section>
      <div class=\"api-links\">
        {'' if not detail.get('canonical_url') else f'<a class="button secondary" href="{_escape(str(detail["canonical_url"]))}" target="_blank" rel="noreferrer">Ouvrir l’annonce canonique</a>'}
      </div>
    """


def _render_detail_proof_section(title: str, summary: str, body_html: str) -> str:
    return f'''
    <details class="proof-panel">
      <summary>
        <span>
          <strong>{_escape(title)}</strong><br>
          <span class="link-muted">{_escape(summary)}</span>
        </span>
        <span class="badge info">déplier</span>
      </summary>
      <div class="proof-body">{body_html}</div>
    </details>
    '''


def _detail_tone_class(value: str) -> str:
    if value in {"success", "warning", "danger"}:
        return value
    return "ok" if value == "observed" else "info"


def _detail_provenance_label(value: str) -> str:
    labels = {
        "observed": "observé",
        "inferred": "inféré",
        "unknown": "incertain",
        "estimated": "estimé",
        "radar": "fenêtre radar",
        "partial": "partiel",
        "scored": "score radar",
    }
    return labels.get(value, value)


def _detail_basis_phrase(value: str) -> str:
    labels = {
        "observed": "observée",
        "inferred": "inférée",
        "unknown": "incertaine",
    }
    return labels.get(value, value)


def _detail_state_reason(reason: str) -> str:
    translations = {
        "Item page returned a distinct deletion signal": "La page produit a renvoyé un signal distinct de suppression.",
        "Item page buy signal is closed, so the listing appears sold on the public page.": "Le signal public d’achat est fermé sur la page produit ; le radar lit donc l’annonce comme vendue.",
        "Item page is still publicly buyable, which is direct active evidence.": "La page produit restait publiquement achetable : c’est un signal direct d’annonce encore active.",
        "Item page is reachable but publicly unavailable without a distinct sold/deleted signal.": "La page produit reste atteignable mais publiquement indisponible, sans signal distinct de vente ou de suppression.",
        "The latest item-page probe was inconclusive, so history remains the safer signal.": "La dernière probe de page produit était inconclusive ; l’historique radar reste donc la base la plus prudente.",
        "The listing was observed in the latest successful scan of its primary catalog.": "L’annonce figurait dans le dernier scan réussi de son catalogue principal.",
        "The listing was seen repeatedly before disappearing, which strengthens the sell-through signal.": "L’annonce a été vue plusieurs fois avant de disparaître, ce qui renforce le signal de vente.",
        "The listing missed one follow-up scan after its last sighting, but that is not distinct enough to call sold or deleted.": "L’annonce a manqué un seul rescan après sa dernière apparition, ce qui ne suffit pas pour conclure à une vente ou une suppression.",
        "The listing was seen recently, but there is no newer successful primary-catalog scan yet.": "L’annonce a été vue récemment, mais aucun scan plus récent du catalogue principal ne permet encore de confirmer ou contredire ce point.",
        "The last sighting is too old and there is no distinct contrary evidence, so the current state stays unknown.": "La dernière apparition est trop ancienne et aucun signal contraire distinct ne permet de trancher ; l’état reste inconnu.",
        "There is not enough direct or repeated absence evidence to classify the current state confidently.": "Le radar n’a pas encore assez de preuve directe ou d’absences répétées pour classer l’état avec confiance.",
    }
    for source, target in translations.items():
        if reason.startswith(source):
            return target
    if reason.startswith("The primary catalog was rescanned ") and " times after the last sighting without seeing the listing again." in reason:
        count = reason.removeprefix("The primary catalog was rescanned ").split(" times", 1)[0]
        return f"Le catalogue principal a été rescanné {count} fois après la dernière apparition sans revoir l’annonce."
    return reason


def _detail_score_factor_label(value: str) -> str:
    labels = {
        "state": "état radar",
        "confidence": "confiance",
        "basis": "base de preuve",
        "freshness": "fraîcheur",
        "history_depth": "profondeur d’historique",
        "follow_up_miss": "ratés de suivi",
    }
    return labels.get(value, value.replace("_", " "))


def _detail_observation_label(count: int) -> str:
    return f"{count} observation" if count == 1 else f"{count} observations"


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

    root_options = [{"value": "all", "label": "Toutes les racines"}] + [
        {"value": root, "label": f"{root} ({count})"}
        for root, count in sorted(roots.items())
    ]
    state_options = [{"value": "all", "label": "Tous les statuts"}] + [
        {"value": state, "label": f"{state} ({states[state]})"}
        for state in STATE_ORDER
        if state in states
    ]
    catalog_options = [{"value": "", "label": "Tous les catalogues"}] + sorted(catalogs.values(), key=lambda item: str(item["label"]))
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
    catalog_path = str(listing.get("primary_catalog_path") or listing.get("root_title") or "le catalogue suivi")
    if history_summary is not None:
        events.append(
            {
                "label": "Premier signal radar",
                "timestamp": str(history_summary.get("first_seen_at") or "unknown"),
                "description": f"Entrée dans le suivi depuis {catalog_path}.",
            }
        )
        events.append(
            {
                "label": "Dernière observation",
                "timestamp": str(history_summary.get("last_seen_at") or "unknown"),
                "description": f"Dernière carte visible dans {catalog_path} ({_freshness_label(history_summary.get('freshness_bucket', 'unknown'))}).",
            }
        )
    follow_up_miss_count = int(listing.get("follow_up_miss_count") or 0)
    if follow_up_miss_count:
        events.append(
            {
                "label": "Ratés de suivi",
                "timestamp": str(listing.get("state_explanation", {}).get("evaluated_at") or "unknown"),
                "description": f"{follow_up_miss_count} rescans réussis du catalogue principal n'ont plus revu l'annonce après sa dernière apparition.",
            }
        )
    if isinstance(latest_probe, dict):
        latest_probe_description = f"Résultat {latest_probe.get('probe_outcome') or 'unknown'} avec HTTP {latest_probe.get('response_status') or 'n/a'}."
        if _probe_is_degraded(latest_probe):
            latest_probe_description = _detail_probe_degradation_note(latest_probe)
        events.append(
            {
                "label": "Dernière probe",
                "timestamp": str(latest_probe.get("probed_at") or "unknown"),
                "description": latest_probe_description,
            }
        )
    events.append(
        {
            "label": "État courant",
            "timestamp": str(listing.get("state_explanation", {}).get("evaluated_at") or "unknown"),
            "description": f"Classée {listing.get('state_code')} sur une base {listing.get('basis_kind')} avec confiance {listing.get('confidence_label')}.",
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


_EXPLORER_OPTION_LABELS = {
    "All roots": "Toutes les racines",
    "All catalogs": "Tous les catalogues",
    "All brands": "Toutes les marques",
    "All conditions": "Tous les états",
    "All price bands": "Toutes les tranches de prix",
    "All radar states": "Tous les statuts radar",
    "Recently seen": "Dernière vue radar",
    "Price ↓": "Prix ↓",
    "Price ↑": "Prix ↑",
    "Visible likes ↓": "Likes visibles ↓",
    "Visible views ↓": "Vues visibles ↓",
    "Estimated publication ↓": "Publication estimée ↓",
    "Radar first seen ↓": "Premier vu radar ↓",
}


_STATE_LABELS = {
    "active": "actif",
    "sold_observed": "vendu observé",
    "sold_probable": "vendu probable",
    "unavailable_non_conclusive": "indisponible",
    "deleted": "supprimée",
    "unknown": "inconnu",
}


_BASIS_LABELS = {
    "observed": "observé",
    "inferred": "inféré",
    "unknown": "inconnu",
}


_CONFIDENCE_LABELS = {
    "high": "haute",
    "medium": "moyenne",
    "low": "basse",
    "unknown": "inconnue",
}


_FRESHNESS_LABELS = {
    "first-pass-only": "premier passage",
    "fresh-followup": "suivi frais",
    "aging-followup": "suivi vieillissant",
    "stale-followup": "suivi ancien",
    "unknown": "inconnu",
}



def _localized_explorer_option_label(label: str) -> str:
    return _EXPLORER_OPTION_LABELS.get(label, label)



def _state_label(value: Any) -> str:
    return _STATE_LABELS.get(str(value or "unknown"), str(value or "unknown"))



def _basis_label(value: Any) -> str:
    return _BASIS_LABELS.get(str(value or "unknown"), str(value or "unknown"))



def _confidence_label(value: Any) -> str:
    return _CONFIDENCE_LABELS.get(str(value or "unknown"), str(value or "unknown"))



def _freshness_label(value: Any) -> str:
    return _FRESHNESS_LABELS.get(str(value or "unknown"), str(value or "unknown"))



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


def _explorer_query(
    filters: ExplorerFilters,
    *,
    base_href: str = "/explorer",
    overrides: dict[str, Any] | None = None,
) -> str:
    params = filters.to_query_dict(overrides=overrides)
    if not params:
        return base_href
    return base_href + "?" + urlencode(params)


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


def _format_seconds_duration(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        total_seconds = max(int(round(float(value))), 0)
    except (TypeError, ValueError):
        return str(value)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _runtime_status_label(value: Any) -> str:
    labels = {
        "idle": "au repos",
        "running": "en cours",
        "scheduled": "planifié",
        "paused": "en pause",
        "failed": "en échec",
        "completed": "terminé",
        "interrupted": "interrompu",
    }
    if value is None:
        return "n/a"
    return labels.get(str(value), str(value))


def _runtime_status_tone(value: str) -> str:
    if value in {"running", "completed"}:
        return "success"
    if value in {"scheduled", "paused", "interrupted"}:
        return "warning"
    if value == "failed":
        return "danger"
    return "info"


def _runtime_phase_label(value: Any) -> str:
    labels = {
        "idle": "au repos",
        "waiting": "attente",
        "paused": "pause",
        "starting": "démarrage",
        "discovery": "collecte",
        "state_refresh": "rafraîchissement d'état",
        "summarizing": "synthèse",
        "completed": "terminé",
    }
    if value is None:
        return "n/a"
    return labels.get(str(value), str(value))


def _runtime_mode_label(value: Any) -> str:
    labels = {
        "continuous": "continu",
        "batch": "batch",
    }
    if value is None:
        return "n/a"
    return labels.get(str(value), str(value))


def _runtime_status_description(value: str) -> str:
    descriptions = {
        "idle": "Aucune boucle continue n'est en attente active sur ce contrôleur au moment de la lecture.",
        "running": "Le cycle en cours travaille réellement ; ce n'est ni une attente ni une pause opérateur.",
        "scheduled": "Le runtime attend la prochaine fenêtre de reprise enregistrée en base. C'est un état sain de veille active.",
        "paused": "Le runtime est volontairement gelé avec un horodatage de pause persistant.",
        "failed": "Le contrôleur a gardé un dernier échec explicite. Vérifiez les cycles récents et l'horodatage de l'erreur.",
    }
    return descriptions.get(value, "État runtime non documenté.")


def _acquisition_status_label(value: str) -> str:
    labels = {
        "healthy": "acquisition saine",
        "partial": "acquisition partielle",
        "degraded": "acquisition dégradée",
        "unknown": "acquisition inconnue",
    }
    return labels.get(str(value or "unknown"), str(value or "unknown"))


def _acquisition_status_tone(value: str) -> str:
    if value == "healthy":
        return "ok"
    if value == "partial":
        return "warning"
    if value == "degraded":
        return "danger"
    return "info"


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
