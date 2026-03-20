"""HTTP transport layer for Vinted Radar.

Uses *curl_cffi* with TLS-impersonation to avoid WAF fingerprint
blocks.  A single ``VintedHttpClient`` instance manages:

* **Session warm-up** – hits the Vinted homepage to acquire the
  ``_vinted_fr_session`` cookie, with configurable retry + backoff.
* **Automatic re-warm-up** – transparently re-acquires the cookie
  whenever the server responds with a 403.
* **Rate-limiting** – enforces a minimum delay between requests.
* **Thread-safety** – the warm-up path is guarded by a lock so the
  client can safely be shared across threads.
* **Proxy pool** – optional list of residential proxies; on retryable
  errors (403 / 429 / network) the client rotates to the next proxy,
  rebuilds the session, re-warms, and retries the request.

Both **synchronous** (``get_text``) and **asynchronous** (``get_text_async``)
interfaces are provided.  The async path uses ``curl_cffi.requests.AsyncSession``
and ``asyncio.Lock`` / ``asyncio.sleep`` for cooperative concurrency.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass

from curl_cffi.requests import AsyncSession, Session

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
VINTED_HOME = "https://www.vinted.fr/"
SESSION_COOKIE_NAME = "_vinted_fr_session"

# We only force the locale; all other headers (User-Agent, Accept,
# sec-ch-ua, …) are injected by curl_cffi's impersonation engine.
DEFAULT_HEADERS = {
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}

# Warm-up retry defaults
_WARMUP_MAX_RETRIES = 3
_WARMUP_BACKOFF_BASE = 2.0  # seconds – multiplied by attempt number

# Retry-with-rotation defaults
_DEFAULT_MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = frozenset({403, 429})


# ------------------------------------------------------------------
# Value object returned by every fetch
# ------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status_code: int
    text: str


# ------------------------------------------------------------------
# HTTP client
# ------------------------------------------------------------------
class VintedHttpClient:
    """Thin HTTP wrapper with TLS impersonation, session management,
    and optional proxy rotation.

    Parameters
    ----------
    request_delay:
        Minimum gap (seconds) between two consecutive HTTP requests.
    timeout_seconds:
        Per-request read/connect timeout.
    impersonate:
        Browser fingerprint profile forwarded to *curl_cffi*.
    warmup_retries:
        How many times ``warm_up`` retries before raising.
    proxies:
        Optional list of proxy URLs (``http://user:pass@host:port``).
        When set, every request is routed through a proxy from this
        pool.  On retryable errors the client rotates to the next
        proxy, rebuilds the underlying session, and re-warms.
    max_retries:
        Maximum number of retry-with-rotation attempts for a single
        request when a retryable error occurs (403, 429, network).
    """

    def __init__(
        self,
        *,
        request_delay: float = 0.5,
        timeout_seconds: float = 20.0,
        impersonate: str = "chrome116",
        warmup_retries: int = _WARMUP_MAX_RETRIES,
        proxies: list[str] | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self.request_delay = max(request_delay, 0.0)
        self.timeout_seconds = timeout_seconds
        self._warmup_retries = max(warmup_retries, 1)
        self._impersonate = impersonate
        self._max_retries = max(max_retries, 1)

        # --- Proxy pool ---
        self._proxies: list[str] = list(proxies) if proxies else []
        self._proxy_index: int = 0

        # --- Sync transport ---
        self._session = self._make_sync_session()
        self._last_request_at = 0.0
        self._warmed_up = False
        self._lock = threading.Lock()

        # --- Async transport (lazily initialised) ---
        self._async_session: AsyncSession | None = None
        self._async_warmed_up = False
        self._async_lock: asyncio.Lock | None = None
        self._last_request_at_async = 0.0

    # ==================================================================
    # Proxy helpers
    # ==================================================================
    @property
    def _current_proxy(self) -> str | None:
        """Return the current proxy URL, or ``None`` if no proxies."""
        if not self._proxies:
            return None
        return self._proxies[self._proxy_index % len(self._proxies)]

    def _advance_proxy(self) -> str | None:
        """Move to the next proxy in the pool (round-robin).

        Returns the newly selected proxy URL, or ``None`` if the pool
        is empty.
        """
        if not self._proxies:
            return None
        self._proxy_index = (self._proxy_index + 1) % len(self._proxies)
        proxy = self._proxies[self._proxy_index]
        logger.info("Rotated to proxy %d/%d", self._proxy_index + 1, len(self._proxies))
        return proxy

    # ==================================================================
    # Session factories
    # ==================================================================
    def _make_sync_session(self) -> Session:
        """Build a fresh sync ``Session`` with the current proxy."""
        proxy = self._current_proxy
        sess = Session(impersonate=self._impersonate, proxy=proxy) if proxy else Session(impersonate=self._impersonate)
        sess.headers.update(DEFAULT_HEADERS)
        return sess

    def _make_async_session(self) -> AsyncSession:
        """Build a fresh async ``AsyncSession`` with the current proxy."""
        proxy = self._current_proxy
        sess = AsyncSession(impersonate=self._impersonate, proxy=proxy) if proxy else AsyncSession(impersonate=self._impersonate)
        sess.headers.update(DEFAULT_HEADERS)
        return sess

    def _rebuild_sync_session(self) -> None:
        """Close & recreate the sync session (e.g. after proxy rotation)."""
        try:
            self._session.close()
        except Exception:  # noqa: BLE001
            pass
        self._session = self._make_sync_session()
        self._warmed_up = False

    async def _rebuild_async_session(self) -> None:
        """Close & recreate the async session (e.g. after proxy rotation)."""
        if self._async_session is not None:
            try:
                await self._async_session.close()
            except Exception:  # noqa: BLE001
                pass
        self._async_session = self._make_async_session()
        self._async_warmed_up = False

    # ==================================================================
    # Async helpers – lazy init
    # ==================================================================
    def _ensure_async_session(self) -> AsyncSession:
        """Create the ``AsyncSession`` on first async call."""
        if self._async_session is None:
            self._async_session = self._make_async_session()
        return self._async_session

    def _ensure_async_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    # ==================================================================
    # SYNC – original interface (unchanged behaviour + retry rotation)
    # ==================================================================
    def warm_up(self) -> None:
        """Ping the Vinted homepage to acquire the session cookie.

        Retries up to ``warmup_retries`` times with linear backoff.
        The method is idempotent: concurrent callers wait on the lock,
        and only the first one actually performs the network call.
        """
        with self._lock:
            if self._warmed_up:
                return
            self._do_warm_up()

    def _do_warm_up(self) -> None:
        """Internal warm-up — must be called while holding ``_lock``."""
        last_exc: Exception | None = None
        for attempt in range(1, self._warmup_retries + 1):
            try:
                proxy_label = self._current_proxy or "direct"
                logger.info(
                    "Session warm-up attempt %d/%d – GET %s (proxy: %s)",
                    attempt,
                    self._warmup_retries,
                    VINTED_HOME,
                    proxy_label,
                )
                resp = self._session.get(VINTED_HOME, timeout=self.timeout_seconds)
                self._last_request_at = time.monotonic()

                cookie_value = self._extract_session_cookie()
                if cookie_value:
                    logger.info(
                        "Session cookie acquired (%s…), status %s",
                        cookie_value[:12],
                        resp.status_code,
                    )
                else:
                    logger.warning(
                        "No '%s' cookie in response (status %s) – "
                        "subsequent requests may be rejected",
                        SESSION_COOKIE_NAME,
                        resp.status_code,
                    )
                self._warmed_up = True
                return

            except Exception as exc:
                last_exc = exc
                wait = _WARMUP_BACKOFF_BASE * attempt
                logger.warning(
                    "Warm-up attempt %d/%d failed (%s) – retrying in %.1fs",
                    attempt,
                    self._warmup_retries,
                    exc,
                    wait,
                )
                if attempt < self._warmup_retries:
                    time.sleep(wait)

        # All retries exhausted
        raise ConnectionError(
            f"Session warm-up failed after {self._warmup_retries} attempts"
        ) from last_exc

    def _extract_session_cookie(self) -> str | None:
        """Return the session cookie value, or *None* if absent."""
        return self._session.cookies.get(SESSION_COOKIE_NAME)

    def get_text(self, url: str) -> FetchedPage:
        """Fetch *url* and return a :class:`FetchedPage`.

        * Lazily triggers ``warm_up`` on the first call.
        * On a retryable status (403, 429) or a network error, rotates
          to the next proxy, rebuilds the session, re-warms, and retries
          up to ``max_retries`` times.
        * Respects ``request_delay`` between consecutive calls.
        """
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                if not self._warmed_up:
                    self.warm_up()

                response = self._throttled_get(url)

                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    return FetchedPage(
                        url=str(response.url),
                        status_code=response.status_code,
                        text=response.text,
                    )

                # Retryable HTTP status ---------------------------------
                logger.warning(
                    "Attempt %d/%d – HTTP %d for %s, rotating proxy…",
                    attempt,
                    self._max_retries,
                    response.status_code,
                    url,
                )
                if attempt < self._max_retries:
                    self._rotate_and_rewarm_sync()
                    continue

                # Last attempt exhausted: return the error page as-is.
                return FetchedPage(
                    url=str(response.url),
                    status_code=response.status_code,
                    text=response.text,
                )

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Attempt %d/%d – network error for %s (%s), rotating proxy…",
                    attempt,
                    self._max_retries,
                    url,
                    exc,
                )
                if attempt < self._max_retries:
                    self._rotate_and_rewarm_sync()
                    continue
                raise

        # Should not be reached, but satisfy the type checker.
        raise ConnectionError(  # pragma: no cover
            f"All {self._max_retries} retry attempts exhausted for {url}"
        ) from last_exc

    def _throttled_get(self, url: str):
        """GET with rate-limit delay.  Returns the raw curl_cffi Response."""
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if self.request_delay and elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

        resp = self._session.get(url, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        return resp

    def _rotate_and_rewarm_sync(self) -> None:
        """Advance proxy, rebuild session, and re-warm (sync)."""
        self._advance_proxy()
        with self._lock:
            self._rebuild_sync_session()
            self._do_warm_up()

    def _invalidate_and_rewarm(self) -> None:
        """Reset warm-up flag and re-acquire the session cookie."""
        with self._lock:
            self._warmed_up = False
            self._do_warm_up()

    # ==================================================================
    # ASYNC – interface for concurrent discovery + retry rotation
    # ==================================================================
    async def warm_up_async(self) -> None:
        """Async variant of :meth:`warm_up`.

        Uses ``asyncio.Lock`` so multiple coroutines sharing the same
        client cooperate correctly within the event loop.
        """
        lock = self._ensure_async_lock()
        async with lock:
            if self._async_warmed_up:
                return
            await self._do_warm_up_async()

    async def _do_warm_up_async(self) -> None:
        """Internal async warm-up — must be called while holding the async lock."""
        session = self._ensure_async_session()
        last_exc: Exception | None = None
        for attempt in range(1, self._warmup_retries + 1):
            try:
                proxy_label = self._current_proxy or "direct"
                logger.info(
                    "Async session warm-up attempt %d/%d – GET %s (proxy: %s)",
                    attempt,
                    self._warmup_retries,
                    VINTED_HOME,
                    proxy_label,
                )
                resp = await session.get(VINTED_HOME, timeout=self.timeout_seconds)

                cookie_value = self._extract_async_session_cookie()
                if cookie_value:
                    logger.info(
                        "Async session cookie acquired (%s…), status %s",
                        cookie_value[:12],
                        resp.status_code,
                    )
                else:
                    logger.warning(
                        "No '%s' cookie in async response (status %s) – "
                        "subsequent requests may be rejected",
                        SESSION_COOKIE_NAME,
                        resp.status_code,
                    )
                self._async_warmed_up = True
                return

            except Exception as exc:
                last_exc = exc
                wait = _WARMUP_BACKOFF_BASE * attempt
                logger.warning(
                    "Async warm-up attempt %d/%d failed (%s) – retrying in %.1fs",
                    attempt,
                    self._warmup_retries,
                    exc,
                    wait,
                )
                if attempt < self._warmup_retries:
                    await asyncio.sleep(wait)

        raise ConnectionError(
            f"Async session warm-up failed after {self._warmup_retries} attempts"
        ) from last_exc

    def _extract_async_session_cookie(self) -> str | None:
        """Return the async session cookie value, or *None* if absent."""
        if self._async_session is None:
            return None
        return self._async_session.cookies.get(SESSION_COOKIE_NAME)

    async def get_text_async(self, url: str) -> FetchedPage:
        """Async variant of :meth:`get_text`.

        * Lazily triggers :meth:`warm_up_async` on the first call.
        * On a retryable status (403, 429) or a network error, rotates
          to the next proxy, rebuilds the async session, re-warms, and
          retries up to ``max_retries`` times.
        """
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                if not self._async_warmed_up:
                    await self.warm_up_async()

                response = await self._async_get(url)

                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    return FetchedPage(
                        url=str(response.url),
                        status_code=response.status_code,
                        text=response.text,
                    )

                # Retryable HTTP status ---------------------------------
                logger.warning(
                    "Async attempt %d/%d – HTTP %d for %s, rotating proxy…",
                    attempt,
                    self._max_retries,
                    response.status_code,
                    url,
                )
                if attempt < self._max_retries:
                    await self._rotate_and_rewarm_async()
                    continue

                # Last attempt exhausted: return the error page as-is.
                return FetchedPage(
                    url=str(response.url),
                    status_code=response.status_code,
                    text=response.text,
                )

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Async attempt %d/%d – network error for %s (%s), rotating proxy…",
                    attempt,
                    self._max_retries,
                    url,
                    exc,
                )
                if attempt < self._max_retries:
                    await self._rotate_and_rewarm_async()
                    continue
                raise

        # Should not be reached, but satisfy the type checker.
        raise ConnectionError(  # pragma: no cover
            f"All {self._max_retries} async retry attempts exhausted for {url}"
        ) from last_exc

    async def _async_get(self, url: str):
        """Async GET.  Rate control is handled by the caller's semaphore and async sleep."""
        now = time.monotonic()
        elapsed = now - self._last_request_at_async
        if self.request_delay and elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)

        session = self._ensure_async_session()
        resp = await session.get(url, timeout=self.timeout_seconds)
        self._last_request_at_async = time.monotonic()
        return resp

    async def _rotate_and_rewarm_async(self) -> None:
        """Advance proxy, rebuild async session, and re-warm."""
        self._advance_proxy()
        lock = self._ensure_async_lock()
        async with lock:
            await self._rebuild_async_session()
            await self._do_warm_up_async()

    async def _invalidate_and_rewarm_async(self) -> None:
        """Reset async warm-up flag and re-acquire the cookie."""
        lock = self._ensure_async_lock()
        async with lock:
            self._async_warmed_up = False
            await self._do_warm_up_async()

    async def close_async(self) -> None:
        """Close the async session and free resources."""
        if self._async_session is not None:
            await self._async_session.close()
            self._async_session = None
