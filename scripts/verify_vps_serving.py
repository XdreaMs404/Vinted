from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class CheckResult:
    label: str
    url: str
    status: int
    details: str


class VerificationError(RuntimeError):
    pass


def _normalize_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        raise VerificationError("base-url must not be empty")
    return cleaned


def _route_url(base_url: str, route: str) -> str:
    if route == "/":
        return base_url + "/"
    return base_url + route


def _fetch(url: str, *, timeout: float) -> tuple[int, str, str]:
    request = Request(url, headers={"User-Agent": "vinted-radar-vps-verify/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8", errors="replace")
            return status, content_type, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise VerificationError(f"{url} returned HTTP {exc.code}: {body[:280]}") from exc
    except URLError as exc:
        raise VerificationError(f"failed to reach {url}: {exc.reason}") from exc


def _expect_contains(body: str, needle: str, *, label: str, url: str) -> None:
    if needle not in body:
        raise VerificationError(f"{label} missing expected marker {needle!r} at {url}")


def _expect_json(body: str, *, label: str, url: str) -> dict[str, Any]:
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{label} did not return valid JSON at {url}: {exc}") from exc


def verify(base_url: str, *, listing_id: int, timeout: float) -> list[CheckResult]:
    prefix = urlsplit(base_url).path.rstrip("/")
    results: list[CheckResult] = []

    html_checks = [
        (
            "overview",
            "/",
            [
                "Ce qui bouge maintenant sur le radar Vinted.",
                f'href="{prefix}/explorer"' if prefix else 'href="/explorer"',
                f'href="{prefix}/runtime"' if prefix else 'href="/runtime"',
            ],
        ),
        (
            "explorer",
            "/explorer",
            [
                "Filtres d’exploration",
                "Annonces du corpus",
                f'href="{prefix}/"' if prefix else 'href="/"',
            ],
        ),
        (
            "runtime",
            "/runtime",
            [
                "Le contrôleur vivant du radar",
                f'href="{prefix}/api/runtime"' if prefix else 'href="/api/runtime"',
            ],
        ),
        (
            "listing-detail",
            f"/listings/{listing_id}",
            [
                "Repères et limites visibles",
                f'href="{prefix}/api/listings/{listing_id}"' if prefix else f'href="/api/listings/{listing_id}"',
            ],
        ),
    ]

    for label, route, markers in html_checks:
        url = _route_url(base_url, route)
        status, content_type, body = _fetch(url, timeout=timeout)
        if status != 200:
            raise VerificationError(f"{label} returned unexpected HTTP {status} at {url}")
        if "text/html" not in content_type:
            raise VerificationError(f"{label} did not return HTML at {url}: {content_type}")
        for marker in markers:
            _expect_contains(body, marker, label=label, url=url)
        results.append(CheckResult(label=label, url=url, status=status, details="html ok"))

    detail_api_url = _route_url(base_url, f"/api/listings/{listing_id}")
    detail_api_status, detail_api_type, detail_api_body = _fetch(detail_api_url, timeout=timeout)
    if "application/json" not in detail_api_type:
        raise VerificationError(f"listing detail API did not return JSON at {detail_api_url}: {detail_api_type}")
    detail_payload = _expect_json(detail_api_body, label="listing-detail-api", url=detail_api_url)
    if int(detail_payload.get("listing_id") or -1) != listing_id:
        raise VerificationError(f"listing detail API returned wrong listing_id at {detail_api_url}")
    results.append(CheckResult(label="listing-detail-api", url=detail_api_url, status=detail_api_status, details="json ok"))

    health_url = _route_url(base_url, "/health")
    health_status, health_type, health_body = _fetch(health_url, timeout=timeout)
    if "application/json" not in health_type:
        raise VerificationError(f"health did not return JSON at {health_url}: {health_type}")
    health_payload = _expect_json(health_body, label="health", url=health_url)
    if health_payload.get("status") != "ok":
        raise VerificationError(f"health payload is not ok at {health_url}: {health_payload}")
    serving = health_payload.get("serving") or {}
    expected_home = f"{prefix}/" if prefix else "/"
    if serving.get("home") != expected_home:
        raise VerificationError(
            f"health serving.home drifted at {health_url}: expected {expected_home!r}, got {serving.get('home')!r}"
        )
    results.append(CheckResult(label="health", url=health_url, status=health_status, details="json ok"))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the proxy-aware Vinted Radar serving contract.")
    parser.add_argument("--base-url", required=True, help="Base URL prefix for the served product, e.g. http://127.0.0.1:8782 or https://radar.example.com/radar")
    parser.add_argument("--listing-id", required=True, type=int, help="Listing ID to verify through the HTML and JSON detail routes.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds per request.")
    args = parser.parse_args()

    try:
        results = verify(_normalize_base_url(args.base_url), listing_id=args.listing_id, timeout=args.timeout)
    except VerificationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("VPS serving verification passed:")
    for result in results:
        print(f"- {result.label}: HTTP {result.status} · {result.details} · {result.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
