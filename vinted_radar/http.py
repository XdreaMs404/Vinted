from __future__ import annotations

from dataclasses import dataclass
import time

import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status_code: int
    text: str


class VintedHttpClient:
    def __init__(self, *, request_delay: float = 0.5, timeout_seconds: float = 20.0) -> None:
        self.request_delay = max(request_delay, 0.0)
        self.timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        self._last_request_at = 0.0

    def get_text(self, url: str) -> FetchedPage:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if self.request_delay and elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        response = self._session.get(url, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        return FetchedPage(url=response.url, status_code=response.status_code, text=response.text)
