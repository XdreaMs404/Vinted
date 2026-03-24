"""HTTP transport layer for Vinted Radar.

Uses *curl_cffi* with TLS impersonation to avoid WAF fingerprint
blocks. A single ``VintedHttpClient`` instance now manages a pool of
route-local sync/async sessions:

* **Session warm-up** per route – acquires the Vinted session cookie on
  the specific direct/proxy lane that will carry the request.
* **Route-local throttling** – request delay is tracked per route rather
  than globally, so a healthy proxy pool can provide real throughput.
* **Retry-aware cooldowns** – retryable HTTP/network failures degrade
  only the affected route instead of resetting the whole transport.
* **Proxy pool support** – accepts normalized proxy URLs and raw
  Webshare ``host:port:user:pass`` entries.
* **Safe diagnostics** – route logs use masked proxy labels and never
  emit credentials or cookie values.

Both **synchronous** (``get_text``) and **asynchronous**
(``get_text_async``) interfaces are provided. Discovery uses the async
path so concurrent catalog scans can spread across multiple warmed proxy
routes instead of pinning the whole run to one active proxy until
failure.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field

from curl_cffi.requests import AsyncSession, Session

from vinted_radar.proxies import mask_proxy_url, parse_proxy_entries

logger = logging.getLogger(__name__)

VINTED_HOME = "https://www.vinted.fr/"
SESSION_COOKIE_NAMES = ("access_token_web", "_vinted_fr_session")
DEFAULT_HEADERS = {
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}

_WARMUP_MAX_RETRIES = 3
_WARMUP_BACKOFF_BASE = 2.0
_DEFAULT_MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = frozenset({403, 429})
_ROUTE_COOLDOWN_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status_code: int
    text: str


@dataclass(slots=True)
class _TransportRoute:
    index: int
    proxy_url: str | None
    label: str
    session: Session | None = None
    async_session: AsyncSession | None = None
    sync_warmed_up: bool = False
    async_warmed_up: bool = False
    sync_rebuild_required: bool = False
    async_rebuild_required: bool = False
    last_request_at_sync: float = 0.0
    last_request_at_async: float = 0.0
    request_count_sync: int = 0
    request_count_async: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    disabled_until_monotonic: float = 0.0
    async_requests_in_flight: int = 0
    sync_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    async_lock: asyncio.Lock | None = field(default=None, repr=False)

    def ensure_async_lock(self) -> asyncio.Lock:
        if self.async_lock is None:
            self.async_lock = asyncio.Lock()
        return self.async_lock


class VintedHttpClient:
    """Thin HTTP wrapper with TLS impersonation, session management,
    and real multi-route proxy pool support.

    Parameters
    ----------
    request_delay:
        Minimum gap (seconds) between two consecutive HTTP requests on
        the same route.
    timeout_seconds:
        Per-request read/connect timeout.
    impersonate:
        Browser fingerprint profile forwarded to *curl_cffi*.
    warmup_retries:
        How many times each route warm-up retries before raising.
    proxies:
        Optional list of proxy URLs or raw Webshare
        ``host:port:user:pass`` entries.
    max_retries:
        Maximum number of retry attempts for a single request when a
        retryable error occurs (403, 429, network).
    """

    def __init__(
        self,
        *,
        request_delay: float = 3.0,
        timeout_seconds: float = 20.0,
        impersonate: str = "chrome120",
        warmup_retries: int = _WARMUP_MAX_RETRIES,
        proxies: list[str] | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self.request_delay = max(request_delay, 0.0)
        self.timeout_seconds = timeout_seconds
        self._warmup_retries = max(warmup_retries, 1)
        self._impersonate = impersonate
        self._max_retries = max(max_retries, 1)

        normalized_proxies = parse_proxy_entries(proxies)
        self._routes: list[_TransportRoute] = []
        if normalized_proxies:
            for index, proxy_url in enumerate(normalized_proxies):
                self._routes.append(
                    _TransportRoute(
                        index=index,
                        proxy_url=proxy_url,
                        label=mask_proxy_url(proxy_url),
                    )
                )
        else:
            self._routes.append(_TransportRoute(index=0, proxy_url=None, label="direct"))

        self._async_pool_lock: asyncio.Lock | None = None

    # ------------------------------------------------------------------
    # Public diagnostics
    # ------------------------------------------------------------------
    @property
    def proxy_pool_size(self) -> int:
        return sum(1 for route in self._routes if route.proxy_url is not None)

    @property
    def transport_mode(self) -> str:
        return "proxy-pool" if self.proxy_pool_size else "direct"

    # ------------------------------------------------------------------
    # Session factories
    # ------------------------------------------------------------------
    def _make_sync_session(self, route: _TransportRoute) -> Session:
        if route.proxy_url:
            return Session(impersonate=self._impersonate, proxy=route.proxy_url)
        return Session(impersonate=self._impersonate)

    def _make_async_session(self, route: _TransportRoute) -> AsyncSession:
        if route.proxy_url:
            return AsyncSession(impersonate=self._impersonate, proxy=route.proxy_url)
        return AsyncSession(impersonate=self._impersonate)

    def _ensure_sync_session(self, route: _TransportRoute) -> Session:
        if route.session is None or route.sync_rebuild_required:
            if route.session is not None:
                try:
                    route.session.close()
                except Exception:  # noqa: BLE001
                    pass
            route.session = self._make_sync_session(route)
            route.sync_rebuild_required = False
            route.sync_warmed_up = False
        return route.session

    async def _ensure_async_session(self, route: _TransportRoute) -> AsyncSession:
        if route.async_session is None or route.async_rebuild_required:
            if route.async_session is not None:
                try:
                    await route.async_session.close()
                except Exception:  # noqa: BLE001
                    pass
            route.async_session = self._make_async_session(route)
            route.async_rebuild_required = False
            route.async_warmed_up = False
        return route.async_session

    # ------------------------------------------------------------------
    # Route selection
    # ------------------------------------------------------------------
    def _candidate_routes(self, *, exclude: set[int]) -> list[_TransportRoute]:
        now = time.monotonic()
        candidates = [route for route in self._routes if route.index not in exclude]
        active = [route for route in candidates if route.disabled_until_monotonic <= now]
        return active or candidates

    def _select_sync_route(self, *, exclude: set[int]) -> _TransportRoute:
        candidates = self._candidate_routes(exclude=exclude)
        now = time.monotonic()
        return min(
            candidates,
            key=lambda route: (
                max(route.disabled_until_monotonic - now, 0.0),
                max(route.last_request_at_sync + self.request_delay - now, 0.0),
                route.request_count_sync,
                route.index,
            ),
        )

    def _ensure_async_pool_lock(self) -> asyncio.Lock:
        if self._async_pool_lock is None:
            self._async_pool_lock = asyncio.Lock()
        return self._async_pool_lock

    async def _reserve_async_route(self, *, exclude: set[int]) -> _TransportRoute:
        pool_lock = self._ensure_async_pool_lock()
        while True:
            async with pool_lock:
                now = time.monotonic()
                candidates = self._candidate_routes(exclude=exclude)
                best_route: _TransportRoute | None = None
                best_key: tuple[float, int, int, int] | None = None
                for route in candidates:
                    wait = 0.0
                    if route.disabled_until_monotonic > now:
                        wait = route.disabled_until_monotonic - now
                    elif self.request_delay:
                        wait = max(route.last_request_at_async + self.request_delay - now, 0.0)
                    key = (wait, route.async_requests_in_flight, route.request_count_async, route.index)
                    if best_key is None or key < best_key:
                        best_key = key
                        best_route = route
                if best_route is None or best_key is None:  # pragma: no cover - defensive only
                    raise ConnectionError("No transport route is available.")
                wait_seconds = best_key[0]
                if wait_seconds <= 0:
                    best_route.async_requests_in_flight += 1
                    best_route.request_count_async += 1
                    best_route.last_request_at_async = now
                    return best_route
            await asyncio.sleep(max(wait_seconds, 0.01))

    async def _release_async_route(self, route: _TransportRoute) -> None:
        pool_lock = self._ensure_async_pool_lock()
        async with pool_lock:
            route.async_requests_in_flight = max(route.async_requests_in_flight - 1, 0)

    # ------------------------------------------------------------------
    # Warm-up helpers
    # ------------------------------------------------------------------
    def warm_up(self) -> None:
        route = self._select_sync_route(exclude=set())
        with route.sync_lock:
            self._ensure_sync_route_ready(route)

    def _ensure_sync_route_ready(self, route: _TransportRoute) -> None:
        self._ensure_sync_session(route)
        if route.sync_warmed_up:
            return
        self._do_warm_up(route)

    def _do_warm_up(self, route: _TransportRoute) -> None:
        session = self._ensure_sync_session(route)
        last_exc: Exception | None = None
        for attempt in range(1, self._warmup_retries + 1):
            try:
                logger.info(
                    "Session warm-up attempt %d/%d – GET %s (route: %s)",
                    attempt,
                    self._warmup_retries,
                    VINTED_HOME,
                    route.label,
                )
                route.last_request_at_sync = time.monotonic()
                response = session.get(VINTED_HOME, timeout=self.timeout_seconds)

                if self._extract_session_cookie(route):
                    logger.info(
                        "Session cookie acquired for %s (status %s)",
                        route.label,
                        response.status_code,
                    )
                else:
                    logger.warning(
                        "No session cookies (%s) in response for %s (status %s) — subsequent requests may be rejected",
                        ", ".join(SESSION_COOKIE_NAMES),
                        route.label,
                        response.status_code,
                    )
                route.sync_warmed_up = True
                return
            except Exception as exc:
                last_exc = exc
                wait_seconds = _WARMUP_BACKOFF_BASE * attempt
                logger.warning(
                    "Warm-up attempt %d/%d failed on %s (%s) — retrying in %.1fs",
                    attempt,
                    self._warmup_retries,
                    route.label,
                    exc,
                    wait_seconds,
                )
                if attempt < self._warmup_retries:
                    time.sleep(wait_seconds)
        raise ConnectionError(
            f"Session warm-up failed after {self._warmup_retries} attempts on {route.label}"
        ) from last_exc

    def _extract_session_cookie(self, route: _TransportRoute) -> str | None:
        if route.session is None:
            return None
        for name in SESSION_COOKIE_NAMES:
            value = route.session.cookies.get(name)
            if value:
                return value
        return None

    async def warm_up_async(self) -> None:
        route = await self._reserve_async_route(exclude=set())
        try:
            await self._ensure_async_route_ready(route)
        finally:
            await self._release_async_route(route)

    async def _ensure_async_route_ready(self, route: _TransportRoute) -> None:
        lock = route.ensure_async_lock()
        async with lock:
            await self._ensure_async_session(route)
            if route.async_warmed_up:
                return
            await self._do_warm_up_async(route)

    async def _do_warm_up_async(self, route: _TransportRoute) -> None:
        session = await self._ensure_async_session(route)
        last_exc: Exception | None = None
        for attempt in range(1, self._warmup_retries + 1):
            try:
                logger.info(
                    "Async session warm-up attempt %d/%d – GET %s (route: %s)",
                    attempt,
                    self._warmup_retries,
                    VINTED_HOME,
                    route.label,
                )
                route.last_request_at_async = time.monotonic()
                response = await session.get(VINTED_HOME, timeout=self.timeout_seconds)
                if self._extract_async_session_cookie(route):
                    logger.info(
                        "Async session cookie acquired for %s (status %s)",
                        route.label,
                        response.status_code,
                    )
                else:
                    logger.warning(
                        "No async session cookies (%s) in response for %s (status %s) — subsequent requests may be rejected",
                        ", ".join(SESSION_COOKIE_NAMES),
                        route.label,
                        response.status_code,
                    )
                route.async_warmed_up = True
                return
            except Exception as exc:
                last_exc = exc
                wait_seconds = _WARMUP_BACKOFF_BASE * attempt
                logger.warning(
                    "Async warm-up attempt %d/%d failed on %s (%s) — retrying in %.1fs",
                    attempt,
                    self._warmup_retries,
                    route.label,
                    exc,
                    wait_seconds,
                )
                if attempt < self._warmup_retries:
                    await asyncio.sleep(wait_seconds)
        raise ConnectionError(
            f"Async session warm-up failed after {self._warmup_retries} attempts on {route.label}"
        ) from last_exc

    def _extract_async_session_cookie(self, route: _TransportRoute) -> str | None:
        if route.async_session is None:
            return None
        for name in SESSION_COOKIE_NAMES:
            value = route.async_session.cookies.get(name)
            if value:
                return value
        return None

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------
    def get_text(self, url: str) -> FetchedPage:
        last_exc: Exception | None = None
        last_page: FetchedPage | None = None
        attempted_routes: set[int] = set()

        for attempt in range(1, self._max_retries + 1):
            route = self._select_sync_route(exclude=attempted_routes)
            attempted_routes.add(route.index)
            try:
                page = self._get_text_via_sync_route(route, url)
                if page.status_code not in _RETRYABLE_STATUS_CODES:
                    self._mark_route_success(route)
                    return page
                last_page = page
                self._mark_route_failure(route, failure=f"HTTP {page.status_code}")
                logger.warning(
                    "Attempt %d/%d – HTTP %d for %s via %s, trying another route…",
                    attempt,
                    self._max_retries,
                    page.status_code,
                    url,
                    route.label,
                )
            except Exception as exc:
                last_exc = exc
                self._mark_route_failure(route, failure=str(exc))
                logger.warning(
                    "Attempt %d/%d – network error for %s via %s (%s), trying another route…",
                    attempt,
                    self._max_retries,
                    url,
                    route.label,
                    exc,
                )
            if attempt >= self._max_retries:
                break

        if last_page is not None:
            return last_page
        raise ConnectionError(
            f"All {self._max_retries} retry attempts exhausted for {url}"
        ) from last_exc

    def _get_text_via_sync_route(self, route: _TransportRoute, url: str) -> FetchedPage:
        with route.sync_lock:
            self._ensure_sync_route_ready(route)
            response = self._throttled_get(route, url)
        return FetchedPage(url=str(response.url), status_code=response.status_code, text=response.text)

    def _throttled_get(self, route: _TransportRoute, url: str):
        now = time.monotonic()
        elapsed = now - route.last_request_at_sync
        if self.request_delay and elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        route.request_count_sync += 1
        route.last_request_at_sync = time.monotonic()
        session = self._ensure_sync_session(route)
        return session.get(url, timeout=self.timeout_seconds)

    async def get_text_async(self, url: str) -> FetchedPage:
        last_exc: Exception | None = None
        last_page: FetchedPage | None = None
        attempted_routes: set[int] = set()

        for attempt in range(1, self._max_retries + 1):
            route = await self._reserve_async_route(exclude=attempted_routes)
            attempted_routes.add(route.index)
            try:
                page = await self._get_text_via_async_route(route, url)
                if page.status_code not in _RETRYABLE_STATUS_CODES:
                    self._mark_route_success(route)
                    return page
                last_page = page
                self._mark_route_failure(route, failure=f"HTTP {page.status_code}")
                logger.warning(
                    "Async attempt %d/%d – HTTP %d for %s via %s, trying another route…",
                    attempt,
                    self._max_retries,
                    page.status_code,
                    url,
                    route.label,
                )
            except Exception as exc:
                last_exc = exc
                self._mark_route_failure(route, failure=str(exc))
                logger.warning(
                    "Async attempt %d/%d – network error for %s via %s (%s), trying another route…",
                    attempt,
                    self._max_retries,
                    url,
                    route.label,
                    exc,
                )
            finally:
                await self._release_async_route(route)
            if attempt >= self._max_retries:
                break

        if last_page is not None:
            return last_page
        raise ConnectionError(
            f"All {self._max_retries} async retry attempts exhausted for {url}"
        ) from last_exc

    async def _get_text_via_async_route(self, route: _TransportRoute, url: str) -> FetchedPage:
        await self._ensure_async_route_ready(route)
        response = await self._async_get(route, url)
        return FetchedPage(url=str(response.url), status_code=response.status_code, text=response.text)

    async def _async_get(self, route: _TransportRoute, url: str):
        session = await self._ensure_async_session(route)
        return await session.get(url, timeout=self.timeout_seconds)

    # ------------------------------------------------------------------
    # Route health
    # ------------------------------------------------------------------
    def _mark_route_success(self, route: _TransportRoute) -> None:
        route.success_count += 1
        route.consecutive_failures = 0
        route.disabled_until_monotonic = 0.0

    def _mark_route_failure(self, route: _TransportRoute, *, failure: str) -> None:
        route.failure_count += 1
        route.consecutive_failures += 1
        route.disabled_until_monotonic = time.monotonic() + _ROUTE_COOLDOWN_SECONDS
        route.sync_warmed_up = False
        route.async_warmed_up = False
        route.sync_rebuild_required = True
        route.async_rebuild_required = True
        logger.warning(
            "Route %s marked degraded after %s (cooldown %.1fs)",
            route.label,
            failure,
            _ROUTE_COOLDOWN_SECONDS,
        )

    # ------------------------------------------------------------------
    # Resource cleanup
    # ------------------------------------------------------------------
    def close(self) -> None:
        for route in self._routes:
            if route.session is None:
                continue
            try:
                route.session.close()
            except Exception:  # noqa: BLE001
                pass
            route.session = None
            route.sync_warmed_up = False

    async def close_async(self) -> None:
        for route in self._routes:
            if route.async_session is None:
                continue
            try:
                await route.async_session.close()
            except Exception:  # noqa: BLE001
                pass
            route.async_session = None
            route.async_warmed_up = False
