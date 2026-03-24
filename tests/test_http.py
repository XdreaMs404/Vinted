from __future__ import annotations

import asyncio

import pytest

from vinted_radar.http import VINTED_HOME, VintedHttpClient


class _FakeResponse:
    def __init__(self, url: str, status_code: int, text: str) -> None:
        self.url = url
        self.status_code = status_code
        self.text = text


class _Recorder:
    def __init__(self) -> None:
        self.sync_calls: list[tuple[str | None, str]] = []
        self.async_calls: list[tuple[str | None, str]] = []
        self.sync_response_factory = lambda proxy, url: _FakeResponse(url, 200, f"sync:{proxy or 'direct'}")
        self.async_response_factory = lambda proxy, url: _FakeResponse(url, 200, f"async:{proxy or 'direct'}")


@pytest.fixture
def transport_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()

    class FakeSyncSession:
        def __init__(self, *, impersonate: str, proxy: str | None = None) -> None:
            self.impersonate = impersonate
            self.proxy = proxy
            self.cookies: dict[str, str] = {}

        def get(self, url: str, timeout: float):
            recorder.sync_calls.append((self.proxy, url))
            if url == VINTED_HOME:
                self.cookies["access_token_web"] = "cookie"
                return _FakeResponse(url, 200, "home")
            return recorder.sync_response_factory(self.proxy, url)

        def close(self) -> None:
            return None

    class FakeAsyncSession:
        def __init__(self, *, impersonate: str, proxy: str | None = None) -> None:
            self.impersonate = impersonate
            self.proxy = proxy
            self.cookies: dict[str, str] = {}

        async def get(self, url: str, timeout: float):
            recorder.async_calls.append((self.proxy, url))
            await asyncio.sleep(0)
            if url == VINTED_HOME:
                self.cookies["access_token_web"] = "cookie"
                return _FakeResponse(url, 200, "home")
            return recorder.async_response_factory(self.proxy, url)

        async def close(self) -> None:
            return None

    monkeypatch.setattr("vinted_radar.http.Session", FakeSyncSession)
    monkeypatch.setattr("vinted_radar.http.AsyncSession", FakeAsyncSession)
    return recorder


def test_http_client_spreads_async_requests_across_multiple_proxies(transport_recorder: _Recorder) -> None:
    async def _exercise() -> list[object]:
        proxies = [
            "1.1.1.1:8000:alice:secret",
            "2.2.2.2:8000:bob:token",
        ]
        client = VintedHttpClient(request_delay=0.0, proxies=proxies)
        try:
            return await asyncio.gather(
                *(client.get_text_async("https://example.com/data") for _ in range(4))
            )
        finally:
            await client.close_async()
            client.close()

    pages = asyncio.run(_exercise())

    assert all(page.status_code == 200 for page in pages)
    data_calls = [proxy for proxy, url in transport_recorder.async_calls if url != VINTED_HOME]
    assert set(data_calls) == {
        "http://alice:secret@1.1.1.1:8000",
        "http://bob:token@2.2.2.2:8000",
    }



def test_http_client_retries_retryable_status_on_another_route(transport_recorder: _Recorder) -> None:
    first_proxy = "http://alice:secret@1.1.1.1:8000"
    second_proxy = "http://bob:token@2.2.2.2:8000"

    def sync_response_factory(proxy: str | None, url: str) -> _FakeResponse:
        if proxy == first_proxy:
            return _FakeResponse(url, 403, "blocked")
        return _FakeResponse(url, 200, "ok")

    transport_recorder.sync_response_factory = sync_response_factory
    client = VintedHttpClient(
        request_delay=0.0,
        proxies=[
            "1.1.1.1:8000:alice:secret",
            "2.2.2.2:8000:bob:token",
        ],
        max_retries=2,
    )
    try:
        page = client.get_text("https://example.com/data")
    finally:
        client.close()

    assert page.status_code == 200
    data_calls = [proxy for proxy, url in transport_recorder.sync_calls if url != VINTED_HOME]
    assert data_calls == [first_proxy, second_proxy]
