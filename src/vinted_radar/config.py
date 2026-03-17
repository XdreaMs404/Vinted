from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

BASE_URL = "https://www.vinted.com"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_EXTRACTOR_VERSION = "s01-bootstrap-v1"
DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "User-Agent": "vinted-radar/0.1 (+https://www.vinted.com)",
}
ROOT_ALIASES: dict[str, int] = {
    "men": 5,
    "women": 1904,
}


@dataclass(slots=True, frozen=True)
class CollectorConfig:
    base_url: str = BASE_URL
    request_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    extractor_version: str = DEFAULT_EXTRACTOR_VERSION
    default_headers: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    root_aliases: Mapping[str, int] = field(default_factory=lambda: dict(ROOT_ALIASES))


def resolve_root_alias(root: str | int) -> int:
    if isinstance(root, int):
        return root

    normalized = str(root).strip().lower()
    if normalized.isdigit():
        return int(normalized)

    try:
        return ROOT_ALIASES[normalized]
    except KeyError as exc:
        raise KeyError(
            f"Unknown root alias '{root}'. Expected one of: men, women, or a numeric catalog id."
        ) from exc
