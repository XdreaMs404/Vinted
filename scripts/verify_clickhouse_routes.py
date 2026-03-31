from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from vinted_radar.dashboard import start_dashboard_server


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RouteCheck:
    backend: str
    label: str
    url: str
    status: int
    content_type: str
    duration_ms: float


_REPRESENTATIVE_DASHBOARD_QUERY = {"state": "active"}
_REPRESENTATIVE_EXPLORER_QUERY = {"q": "robe", "page_size": 2}
_REPRESENTATIVE_DETAIL_QUERY = {"root": "Femmes", "state": "active", "price_band": "40_plus_eur", "page_size": 12}
_HTML_MARKERS = {
    "dashboard_html": ["Navigation principale du produit", "Ce qui bouge maintenant sur le radar Vinted."],
    "explorer_html": ["Filtres d’exploration", "Annonces du corpus"],
    "detail_html": ["Fiche annonce", "Ce que le radar voit d’abord"],
}
_EXPLORER_ITEM_PARITY_DROP_KEYS = {
    "last_observed_run_id",
    "latest_follow_up_miss_at",
    "latest_primary_scan_at",
    "latest_primary_scan_run_id",
    "latest_probe",
    "price_band_sort_order",
    "primary_root_catalog_id",
    "seen_in_latest_primary_scan",
    "state_explanation",
    "state_sort_order",
}


def _route_url(base_url: str, path: str, query: dict[str, Any] | None = None) -> str:
    normalized_base_url = base_url.rstrip("/")
    route = "/" if path == "/" else path
    if query:
        return f"{normalized_base_url}{route}?{urlencode(query)}"
    return f"{normalized_base_url}{route}"


def _fetch(url: str, *, timeout: float) -> tuple[int, str, str, float]:
    request = Request(url, headers={"User-Agent": "vinted-radar-clickhouse-verify/1.0"})
    started = perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            duration_ms = round((perf_counter() - started) * 1000.0, 2)
            return (
                int(response.status),
                response.headers.get("Content-Type", ""),
                response.read().decode("utf-8", errors="replace"),
                duration_ms,
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise VerificationError(f"{url} returned HTTP {exc.code}: {body[:280]}") from exc
    except URLError as exc:
        raise VerificationError(f"failed to reach {url}: {exc.reason}") from exc


def _fetch_json_route(
    *,
    backend: str,
    base_url: str,
    label: str,
    path: str,
    query: dict[str, Any] | None,
    timeout: float,
) -> tuple[RouteCheck, dict[str, Any]]:
    url = _route_url(base_url, path, query)
    status, content_type, body, duration_ms = _fetch(url, timeout=timeout)
    if status != 200:
        raise VerificationError(f"{label} returned unexpected HTTP {status} at {url}")
    if "application/json" not in content_type:
        raise VerificationError(f"{label} did not return JSON at {url}: {content_type}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{label} did not return valid JSON at {url}: {exc}") from exc
    return (
        RouteCheck(
            backend=backend,
            label=label,
            url=url,
            status=status,
            content_type=content_type,
            duration_ms=duration_ms,
        ),
        payload,
    )


def _fetch_html_route(
    *,
    backend: str,
    base_url: str,
    label: str,
    path: str,
    query: dict[str, Any] | None,
    timeout: float,
    markers: list[str],
) -> RouteCheck:
    url = _route_url(base_url, path, query)
    status, content_type, body, duration_ms = _fetch(url, timeout=timeout)
    if status != 200:
        raise VerificationError(f"{label} returned unexpected HTTP {status} at {url}")
    if "text/html" not in content_type:
        raise VerificationError(f"{label} did not return HTML at {url}: {content_type}")
    for marker in markers:
        if marker not in body:
            raise VerificationError(f"{label} missing expected marker {marker!r} at {url}")
    return RouteCheck(
        backend=backend,
        label=label,
        url=url,
        status=status,
        content_type=content_type,
        duration_ms=duration_ms,
    )


def _normalize_explorer_item_for_parity(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    for key in _EXPLORER_ITEM_PARITY_DROP_KEYS:
        normalized.pop(key, None)
    return normalized


def normalize_dashboard_payload_for_parity(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    request = dict(normalized.get("request") or {})
    request.pop("primary_payload_source", None)
    normalized["request"] = request
    normalized["featured_listings"] = [
        _normalize_explorer_item_for_parity(dict(item))
        for item in (normalized.get("featured_listings") or [])
    ]
    return normalized


def normalize_explorer_payload_for_parity(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["items"] = [
        _normalize_explorer_item_for_parity(dict(item))
        for item in (normalized.get("items") or [])
    ]
    filters = dict(normalized.get("filters") or {})
    available = dict(filters.get("available") or {})
    for key in ("price_bands", "states"):
        options = []
        for option in available.get(key) or []:
            option_payload = dict(option)
            option_payload.pop("sort_rank", None)
            options.append(option_payload)
        if options:
            available[key] = options
    if available:
        filters["available"] = available
        normalized["filters"] = filters
    return normalized


def normalize_detail_payload_for_parity(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("source_url", None)
    latest_probe = normalized.get("latest_probe")
    if isinstance(latest_probe, dict):
        latest_probe = dict(latest_probe)
        latest_probe.pop("probe_id", None)
        normalized["latest_probe"] = latest_probe
    return normalized


def normalize_health_payload_for_parity(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload)


def _assert_equal(label: str, left: dict[str, Any], right: dict[str, Any]) -> None:
    if left == right:
        return
    left_dump = json.dumps(left, ensure_ascii=False, indent=2, sort_keys=True)
    right_dump = json.dumps(right, ensure_ascii=False, indent=2, sort_keys=True)
    raise VerificationError(
        f"{label} parity mismatch between repository and ClickHouse payloads.\n"
        f"--- repository ---\n{left_dump}\n"
        f"--- clickhouse ---\n{right_dump}"
    )


def _collect_json_snapshot(
    *,
    backend: str,
    base_url: str,
    listing_id: int,
    timeout: float,
    dashboard_query: dict[str, Any],
    explorer_query: dict[str, Any],
    detail_query: dict[str, Any],
) -> tuple[list[RouteCheck], dict[str, dict[str, Any]]]:
    checks: list[RouteCheck] = []
    payloads: dict[str, dict[str, Any]] = {}
    for label, path, query in (
        ("dashboard_api", "/api/dashboard", dashboard_query),
        ("explorer_api", "/api/explorer", explorer_query),
        ("detail_api", f"/api/listings/{listing_id}", detail_query),
        ("health", "/health", None),
    ):
        check, payload = _fetch_json_route(
            backend=backend,
            base_url=base_url,
            label=label,
            path=path,
            query=query,
            timeout=timeout,
        )
        checks.append(check)
        payloads[label] = payload
    return checks, payloads


def _collect_clickhouse_html_checks(
    *,
    base_url: str,
    listing_id: int,
    timeout: float,
    dashboard_query: dict[str, Any],
    explorer_query: dict[str, Any],
    detail_query: dict[str, Any],
) -> list[RouteCheck]:
    return [
        _fetch_html_route(
            backend="clickhouse",
            base_url=base_url,
            label="dashboard_html",
            path="/",
            query=dashboard_query,
            timeout=timeout,
            markers=_HTML_MARKERS["dashboard_html"],
        ),
        _fetch_html_route(
            backend="clickhouse",
            base_url=base_url,
            label="explorer_html",
            path="/explorer",
            query=explorer_query,
            timeout=timeout,
            markers=_HTML_MARKERS["explorer_html"],
        ),
        _fetch_html_route(
            backend="clickhouse",
            base_url=base_url,
            label="detail_html",
            path=f"/listings/{listing_id}",
            query=detail_query,
            timeout=timeout,
            markers=_HTML_MARKERS["detail_html"],
        ),
    ]


def _route_dicts(checks: list[RouteCheck]) -> list[dict[str, Any]]:
    return [asdict(check) for check in checks]


def verify_clickhouse_routes(
    *,
    db_path: str | Path,
    listing_id: int,
    now: str | None = None,
    timeout: float = 30.0,
    host: str = "127.0.0.1",
    port: int = 0,
    clickhouse_client: object | None = None,
    clickhouse_database: str | None = None,
    dashboard_query: dict[str, Any] | None = None,
    explorer_query: dict[str, Any] | None = None,
    detail_query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard_query = dict(_REPRESENTATIVE_DASHBOARD_QUERY if dashboard_query is None else dashboard_query)
    explorer_query = dict(_REPRESENTATIVE_EXPLORER_QUERY if explorer_query is None else explorer_query)
    detail_query = dict(_REPRESENTATIVE_DETAIL_QUERY if detail_query is None else detail_query)

    repository_server = start_dashboard_server(
        db_path=db_path,
        host=host,
        port=port,
        now=now,
        enable_polyglot_reads=False,
    )
    clickhouse_server = start_dashboard_server(
        db_path=db_path,
        host=host,
        port=port,
        now=now,
        clickhouse_client=clickhouse_client,
        clickhouse_database=clickhouse_database,
        enable_polyglot_reads=True if clickhouse_client is None else None,
    )
    try:
        repository_base_url = f"http://{repository_server.host}:{repository_server.port}"
        clickhouse_base_url = f"http://{clickhouse_server.host}:{clickhouse_server.port}"

        repository_checks, repository_payloads = _collect_json_snapshot(
            backend="repository",
            base_url=repository_base_url,
            listing_id=listing_id,
            timeout=timeout,
            dashboard_query=dashboard_query,
            explorer_query=explorer_query,
            detail_query=detail_query,
        )
        clickhouse_checks, clickhouse_payloads = _collect_json_snapshot(
            backend="clickhouse",
            base_url=clickhouse_base_url,
            listing_id=listing_id,
            timeout=timeout,
            dashboard_query=dashboard_query,
            explorer_query=explorer_query,
            detail_query=detail_query,
        )
        html_checks = _collect_clickhouse_html_checks(
            base_url=clickhouse_base_url,
            listing_id=listing_id,
            timeout=timeout,
            dashboard_query=dashboard_query,
            explorer_query=explorer_query,
            detail_query=detail_query,
        )
    finally:
        repository_server.stop()
        clickhouse_server.stop()

    repository_source = ((repository_payloads["dashboard_api"].get("request") or {}).get("primary_payload_source"))
    clickhouse_source = ((clickhouse_payloads["dashboard_api"].get("request") or {}).get("primary_payload_source"))
    if repository_source != "repository.overview_snapshot":
        raise VerificationError(f"repository dashboard source drifted: {repository_source!r}")
    if clickhouse_source != "clickhouse.overview_snapshot":
        raise VerificationError(f"clickhouse dashboard source drifted: {clickhouse_source!r}")

    normalized_repository = {
        "dashboard_api": normalize_dashboard_payload_for_parity(repository_payloads["dashboard_api"]),
        "explorer_api": normalize_explorer_payload_for_parity(repository_payloads["explorer_api"]),
        "detail_api": normalize_detail_payload_for_parity(repository_payloads["detail_api"]),
        "health": normalize_health_payload_for_parity(repository_payloads["health"]),
    }
    normalized_clickhouse = {
        "dashboard_api": normalize_dashboard_payload_for_parity(clickhouse_payloads["dashboard_api"]),
        "explorer_api": normalize_explorer_payload_for_parity(clickhouse_payloads["explorer_api"]),
        "detail_api": normalize_detail_payload_for_parity(clickhouse_payloads["detail_api"]),
        "health": normalize_health_payload_for_parity(clickhouse_payloads["health"]),
    }
    for label in ("dashboard_api", "explorer_api", "detail_api", "health"):
        _assert_equal(label, normalized_repository[label], normalized_clickhouse[label])

    return {
        "queries": {
            "dashboard": dashboard_query,
            "explorer": explorer_query,
            "detail": detail_query,
        },
        "repository": {
            "base_url": repository_base_url,
            "dashboard_source": repository_source,
            "routes": _route_dicts(repository_checks),
            "total_duration_ms": round(sum(check.duration_ms for check in repository_checks), 2),
        },
        "clickhouse": {
            "base_url": clickhouse_base_url,
            "dashboard_source": clickhouse_source,
            "routes": _route_dicts(clickhouse_checks + html_checks),
            "total_duration_ms": round(sum(check.duration_ms for check in clickhouse_checks + html_checks), 2),
        },
        "parity": {
            "dashboard_api": "match",
            "explorer_api": "match",
            "detail_api": "match",
            "health": "match",
        },
    }


def _print_human_summary(proof: dict[str, Any]) -> None:
    print("ClickHouse route verification passed:")
    print(
        f"- repository: source={proof['repository']['dashboard_source']} · total={proof['repository']['total_duration_ms']}ms"
    )
    for route in proof["repository"]["routes"]:
        print(f"  - {route['label']}: HTTP {route['status']} · {route['duration_ms']}ms · {route['url']}")
    print(
        f"- clickhouse: source={proof['clickhouse']['dashboard_source']} · total={proof['clickhouse']['total_duration_ms']}ms"
    )
    for route in proof["clickhouse"]["routes"]:
        print(f"  - {route['label']}: HTTP {route['status']} · {route['duration_ms']}ms · {route['url']}")
    print("- parity: dashboard_api, explorer_api, detail_api, and health all matched after contract normalization")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ClickHouse-backed dashboard/explorer/detail routes against the SQLite-era route contract.")
    parser.add_argument("--db-path", required=True, help="SQLite database path used by the dashboard application.")
    parser.add_argument("--listing-id", required=True, type=int, help="Representative listing ID to verify through the detail route.")
    parser.add_argument("--now", help="Fixed ISO-8601 time used while rendering payloads.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout per route in seconds.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for the temporary verification servers.")
    parser.add_argument("--port", type=int, default=0, help="Bind port for the temporary verification servers. Use 0 for ephemeral ports.")
    parser.add_argument("--clickhouse-database", help="Override the ClickHouse database name when using the real configured client.")
    parser.add_argument("--json", action="store_true", help="Emit the verification proof as JSON.")
    args = parser.parse_args()

    try:
        proof = verify_clickhouse_routes(
            db_path=Path(args.db_path),
            listing_id=args.listing_id,
            now=args.now,
            timeout=args.timeout,
            host=args.host,
            port=args.port,
            clickhouse_database=args.clickhouse_database,
        )
    except VerificationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human_summary(proof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
