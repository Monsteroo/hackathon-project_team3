import asyncio
import time

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app
from app.voice import stt
from app.voice.errors import VoiceError
from app.voice.ratelimit import RateLimiter


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("VOICE_RATE_LIMIT_PER_MIN", "10")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def api(**headers):
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "test-api-key", **headers}
    )


def test_rate_limiter_window():
    rl = RateLimiter(60)
    assert rl.allow("ip", 2, 0) and rl.allow("ip", 2, 1) and not rl.allow("ip", 2, 2)
    assert rl.allow("other", 2, 2)  # окремий ліміт на кожен IP
    assert rl.allow("ip", 2, 61)  # вікно зсунулось


async def test_parse_text_limited_to_10_per_minute(monkeypatch):
    async def fake_clean(t):
        return {
            "text": t,
            "raw_text": t,
            "mode": None,
            "radius_km": None,
            "cleanup": {"model": None, "guard": "skipped"},
        }

    monkeypatch.setattr("app.voice.service.clean_text", fake_clean)
    async with api() as c:
        codes = [(await c.post("/voice/parse-text", json={"text": "хліб"})).status_code for _ in range(11)]
        last = await c.post("/voice/parse-text", json={"text": "хліб"})
    assert codes == [200] * 10 + [429]
    assert last.json()["detail"]["code"] == "rate_limited"
    async with api(**{"X-Forwarded-For": "203.0.113.7"}) as c:  # інший клієнт за проксі
        assert (await c.post("/voice/parse-text", json={"text": "хліб"})).status_code == 200


async def test_audio_over_1_5_mb_rejected():
    assert stt.MAX_AUDIO_BYTES <= 1_600_000
    with pytest.raises(VoiceError) as e:
        await stt.transcribe(b"x" * (stt.MAX_AUDIO_BYTES + 1), "a.webm", None)
    assert e.value.code == "audio_too_large"


async def test_duration_over_65s_rejected():
    def h(r):
        return httpx.Response(200, json={"text": "хліб", "duration": 70.2, "segments": []})

    with pytest.raises(VoiceError) as e:
        await stt.transcribe(b"x", "a.webm", None, client=client(h))
    assert e.value.code == "audio_too_long" and e.value.status == 413


async def test_invalid_json_from_groq_is_clean_error():
    with pytest.raises(VoiceError) as e:
        await stt.transcribe(b"x", "a.webm", None, client=client(lambda r: httpx.Response(200, text="<html>")))
    assert e.value.code == "stt_unavailable"


async def test_slow_transcription_does_not_block_other_requests(monkeypatch):
    """Повільний Groq (0.6 с) не має затримувати інші запити: виклики асинхронні."""

    async def slow(*a, **k):
        await asyncio.sleep(0.6)
        return {"text": "хліб", "duration_s": 1}

    async def fake_clean(t):
        return {
            "text": t,
            "raw_text": t,
            "mode": None,
            "radius_km": None,
            "cleanup": {"model": None, "guard": "skipped"},
        }

    monkeypatch.setattr("app.voice.service.transcribe", slow)
    monkeypatch.setattr("app.voice.service.clean_text", fake_clean)
    async with api() as c:
        t0 = time.perf_counter()
        task = asyncio.create_task(c.post("/voice/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}))
        await asyncio.sleep(0.05)
        health = await c.get("/health")
        fast = time.perf_counter() - t0  # блокуючий виклик дав би ≥ 0.6 с
        assert (await task).status_code == 200
    assert health.status_code == 200 and fast < 0.3
