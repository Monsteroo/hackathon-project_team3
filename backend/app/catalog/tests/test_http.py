"""Http: повтори й спільна пауза на 429, без справжньої мережі (httpx.MockTransport)."""

import httpx

from app.catalog.etl.http import Http


async def test_retries_after_429_and_honours_retry_after():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    http = Http(delay=0, backoff=0.01)
    http._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        assert await http.get_json("https://api.test/search") == {"ok": True}
    finally:
        await http.aclose()
    assert len(calls) == 2
    assert (http.rate_limited, http.failures) == (1, 0)


async def test_404_is_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    http = Http(delay=0, backoff=0.01)
    http._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        try:
            await http.get_json("https://api.test/missing")
            raise AssertionError("expected HTTPStatusError")
        except httpx.HTTPStatusError:
            pass
    finally:
        await http.aclose()
    assert len(calls) == 1 and http.failures == 1
