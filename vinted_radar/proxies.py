from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

DEFAULT_PROXY_FILE = Path("data/proxies.txt")
DEFAULT_PROXY_POOL_ENV = "VINTED_RADAR_PROXY_POOL"
DEFAULT_PROXY_FILE_ENV = "VINTED_RADAR_PROXY_FILE"


def normalize_proxy_entry(value: str, *, default_scheme: str = "http") -> str:
    """Normalize one proxy entry into ``scheme://user:pass@host:port`` form.

    Accepted inputs:
    - ``http://user:pass@host:port``
    - ``host:port:user:pass`` (Webshare export format)
    - ``host:port``
    - ``user:pass@host:port``
    """
    candidate = str(value).strip()
    if not candidate:
        raise ValueError("Proxy entry cannot be empty.")

    if "://" in candidate:
        return _normalize_proxy_url(candidate)

    if "@" in candidate:
        return _normalize_proxy_url(f"{default_scheme}://{candidate}")

    parts = candidate.split(":")
    if len(parts) == 2:
        host, port = parts
        return _build_proxy_url(
            scheme=default_scheme,
            host=host,
            port=port,
            username=None,
            password=None,
        )
    if len(parts) >= 4:
        host = parts[0]
        port = parts[1]
        username = parts[2]
        password = ":".join(parts[3:])
        return _build_proxy_url(
            scheme=default_scheme,
            host=host,
            port=port,
            username=username,
            password=password,
        )

    raise ValueError(
        "Unsupported proxy entry format. Expected URL or host:port:user:pass."
    )


def parse_proxy_entries(
    entries: Iterable[str] | None,
    *,
    default_scheme: str = "http",
) -> list[str]:
    if entries is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for token in _iter_proxy_tokens(entries):
        proxy_url = normalize_proxy_entry(token, default_scheme=default_scheme)
        if proxy_url in seen:
            continue
        normalized.append(proxy_url)
        seen.add(proxy_url)
    return normalized


def load_proxy_file(path: str | Path, *, default_scheme: str = "http") -> list[str]:
    proxy_path = Path(path)
    content = proxy_path.read_text(encoding="utf-8")
    return parse_proxy_entries(content.splitlines(), default_scheme=default_scheme)


def resolve_proxy_pool(
    *,
    inline: Iterable[str] | None = None,
    proxy_file: str | Path | None = None,
    default_file: str | Path | None = DEFAULT_PROXY_FILE,
    env: Mapping[str, str] | None = None,
    default_scheme: str = "http",
) -> list[str]:
    environment = os.environ if env is None else env
    merged: list[str] = []

    inline_values = [] if inline is None else [str(item) for item in inline]
    merged.extend(inline_values)

    env_pool = environment.get(DEFAULT_PROXY_POOL_ENV)
    if env_pool:
        merged.append(env_pool)

    resolved_file: Path | None = None
    if proxy_file is not None:
        resolved_file = _resolve_proxy_file_path(
            explicit_path=proxy_file,
            default_file=None,
            env=environment,
        )
    elif not inline_values and not env_pool:
        resolved_file = _resolve_proxy_file_path(
            explicit_path=None,
            default_file=default_file,
            env=environment,
        )

    if resolved_file is not None:
        merged.extend(load_proxy_file(resolved_file, default_scheme=default_scheme))

    return parse_proxy_entries(merged, default_scheme=default_scheme)


def mask_proxy_url(value: str) -> str:
    proxy_url = normalize_proxy_entry(value)
    parts = urlsplit(proxy_url)
    host = parts.hostname or "unknown"
    port = f":{parts.port}" if parts.port is not None else ""
    if parts.username is not None or parts.password is not None:
        netloc = f"***@{host}{port}"
    else:
        netloc = f"{host}{port}"
    return urlunsplit((parts.scheme, netloc, "", "", ""))


def proxy_pool_metadata(proxies: Iterable[str] | None) -> dict[str, object]:
    items = parse_proxy_entries(proxies)
    return {
        "transport_mode": "proxy-pool" if items else "direct",
        "proxy_pool_size": len(items),
    }


def _iter_proxy_tokens(entries: Iterable[str]) -> Iterable[str]:
    for entry in entries:
        if entry is None:
            continue
        for line in str(entry).splitlines():
            for token in line.replace(",", "\n").replace(";", "\n").splitlines():
                candidate = token.strip()
                if not candidate or candidate.startswith("#"):
                    continue
                yield candidate


def _resolve_proxy_file_path(
    *,
    explicit_path: str | Path | None,
    default_file: str | Path | None,
    env: Mapping[str, str],
) -> Path | None:
    if explicit_path is not None:
        proxy_path = Path(explicit_path)
        if not proxy_path.exists():
            raise FileNotFoundError(f"Proxy file not found: {proxy_path}")
        return proxy_path

    env_path = env.get(DEFAULT_PROXY_FILE_ENV)
    if env_path:
        proxy_path = Path(env_path)
        if not proxy_path.exists():
            raise FileNotFoundError(f"Proxy file not found: {proxy_path}")
        return proxy_path

    if default_file is None:
        return None
    proxy_path = Path(default_file)
    return proxy_path if proxy_path.exists() else None


def _normalize_proxy_url(value: str) -> str:
    parts = urlsplit(value)
    if not parts.scheme:
        raise ValueError("Proxy URL is missing a scheme.")
    if not parts.hostname:
        raise ValueError("Proxy URL is missing a hostname.")
    if parts.port is None:
        raise ValueError("Proxy URL is missing a port.")
    return _build_proxy_url(
        scheme=parts.scheme,
        host=parts.hostname,
        port=str(parts.port),
        username=parts.username,
        password=parts.password,
    )


def _build_proxy_url(
    *,
    scheme: str,
    host: str,
    port: str,
    username: str | None,
    password: str | None,
) -> str:
    normalized_host = host.strip()
    if not normalized_host:
        raise ValueError("Proxy host cannot be empty.")

    try:
        port_number = int(str(port).strip())
    except ValueError as exc:  # pragma: no cover - defensive only
        raise ValueError(f"Invalid proxy port: {port}") from exc
    if port_number < 1 or port_number > 65535:
        raise ValueError(f"Invalid proxy port: {port}")

    userinfo = ""
    if username is not None:
        userinfo = quote(username, safe="")
        if password is not None:
            userinfo += f":{quote(password, safe='')}"
        userinfo += "@"

    return f"{scheme}://{userinfo}{normalized_host}:{port_number}"
