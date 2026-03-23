from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


def normalize_base_path(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if cleaned in {"", "/"}:
        return ""
    return "/" + cleaned.strip("/")


def normalize_public_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().rstrip("/")
    return cleaned or None


def _normalize_route_path(path: str) -> str:
    cleaned = (path or "/").strip()
    if not cleaned or cleaned == "/":
        return "/"
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    return cleaned


@dataclass(frozen=True, slots=True)
class RouteContext:
    base_path: str = ""
    public_base_url: str | None = None

    @classmethod
    def from_options(
        cls,
        *,
        base_path: str | None = None,
        public_base_url: str | None = None,
    ) -> RouteContext:
        normalized_public_base_url = normalize_public_base_url(public_base_url)
        normalized_base_path = normalize_base_path(base_path)
        derived_base_path = ""
        if normalized_public_base_url is not None:
            derived_base_path = normalize_base_path(urlsplit(normalized_public_base_url).path)
        if normalized_base_path and derived_base_path and normalized_base_path != derived_base_path:
            raise ValueError(
                "public_base_url path must match base_path when both are provided"
            )
        return cls(
            base_path=normalized_base_path or derived_base_path,
            public_base_url=normalized_public_base_url,
        )

    def path(self, route_path: str) -> str:
        normalized_route = _normalize_route_path(route_path)
        if not self.base_path:
            return normalized_route
        if normalized_route == "/":
            return f"{self.base_path}/"
        return f"{self.base_path}{normalized_route}"

    def url(self, route_path: str) -> str:
        if self.public_base_url is None:
            return self.path(route_path)
        normalized_route = _normalize_route_path(route_path)
        if normalized_route == "/":
            return f"{self.public_base_url}/"
        return f"{self.public_base_url}{normalized_route}"


def build_dashboard_urls(
    host: str,
    port: int,
    *,
    base_path: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, str]:
    route_context = RouteContext.from_options(base_path=base_path, public_base_url=public_base_url)
    advertised_context = route_context
    if advertised_context.public_base_url is None:
        local_base = f"http://{host}:{port}{advertised_context.base_path}"
        advertised_context = RouteContext.from_options(public_base_url=local_base)
    return {
        "dashboard": advertised_context.url("/"),
        "home": advertised_context.url("/"),
        "dashboard_api": advertised_context.url("/api/dashboard"),
        "explorer": advertised_context.url("/explorer"),
        "runtime": advertised_context.url("/runtime"),
        "runtime_api": advertised_context.url("/api/runtime"),
        "detail": advertised_context.url("/listings/<id>"),
        "detail_api": advertised_context.url("/api/listings/<id>"),
        "health": advertised_context.url("/health"),
    }
