"""Vinted Radar collector package."""

from .config import (
    BASE_URL,
    DEFAULT_EXTRACTOR_VERSION,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_SECONDS,
    ROOT_ALIASES,
    CollectorConfig,
    resolve_root_alias,
)

__all__ = [
    "BASE_URL",
    "CollectorConfig",
    "DEFAULT_EXTRACTOR_VERSION",
    "DEFAULT_HEADERS",
    "DEFAULT_TIMEOUT_SECONDS",
    "ROOT_ALIASES",
    "resolve_root_alias",
]
