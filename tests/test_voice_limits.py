import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.app import app
from backend.ratelimit import RateLimiter
from backend.voice import stt
from backend.voice.errors import VoiceError


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    s = config.get_settings()
    monkeypatch.setattr(stt, "get_settings", lambda: s.__class__(**{**s.__dict__, "groq_api_key": "test"}))


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_rate_limiter_window():
    rl = RateLimiter(2, 60)
    assert rl.allow("ip", 0) and rl.allow("ip", 1) and not rl.allow("ip", 2)
    assert rl.allow("other", 2)          # окремий ліміт на кожен IP
    assert rl.allow("ip", 61)            # вікно зсунулось


def test_parse_text_limited_to_10_per_minute(monkeypatch):
    monkeypatch.setattr("backend.routes_voice.clean_text",
                        lambda t: {"text": t, "raw_text": t, "mode": None, "radius_km": None, "cleanup": {}})
    c = TestClient(app)
    codes = [c.post("/api/parse-text", json={"text": "хліб"}).status_code for _ in range(11)]
    assert codes == [200] * 10 + [429]
    r = c.post("/api/parse-text", json={"text": "хліб"}, headers={"X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 200          # інший клієнт за проксі Vercel


def test_transcribe_rate_limited_error_shape(monkeypatch):
    monkeypatch.setattr("backend.routes_voice.transcribe", lambda *a, **k: {"text": "хліб", "duration_s": 1})
    monkeypatch.setattr("backend.routes_voice.clean_text", lambda t: {"text": t})
    c = TestClient(app)
    for _ in range(10):
        c.post("/api/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")})
    r = c.post("/api/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"


def test_audio_over_1_5_mb_rejected():
    assert stt.MAX_AUDIO_BYTES <= 1_600_000
    with pytest.raises(VoiceError) as e:
        stt.transcribe(b"x" * (stt.MAX_AUDIO_BYTES + 1), "a.webm", None)
    assert e.value.code == "audio_too_large"


def test_duration_over_65s_rejected():
    h = lambda r: httpx.Response(200, json={"text": "хліб", "duration": 70.2, "segments": []})  # noqa: E731
    with pytest.raises(VoiceError) as e:
        stt.transcribe(b"x", "a.webm", None, client=client(h))
    assert e.value.code == "audio_too_long" and e.value.status == 413


def test_invalid_json_from_groq_is_clean_error():
    with pytest.raises(VoiceError) as e:
        stt.transcribe(b"x", "a.webm", None, client=client(lambda r: httpx.Response(200, text="<html>")))
    assert e.value.code == "stt_unavailable"


def test_transcribe_does_not_block_event_loop(monkeypatch):
    """Повільний виклик Groq (0.6 с) не має затримувати інші запити: ендпоінт синхронний → пул потоків."""
    def slow(*a, **k):
        time.sleep(0.6)
        return {"text": "хліб", "duration_s": 1}
    monkeypatch.setattr("backend.routes_voice.transcribe", slow)
    monkeypatch.setattr("backend.routes_voice.clean_text", lambda t: {"text": t})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as ac:
            t0 = time.perf_counter()
            slow_task = asyncio.create_task(
                ac.post("/api/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}))
            await asyncio.sleep(0.05)
            health = await ac.get("/api/health")
            fast = time.perf_counter() - t0   # блокуючий ендпоінт дав би ≥ 0.6 с
            await slow_task
            return health.status_code, fast

    status, fast = asyncio.run(scenario())
    assert status == 200 and fast < 0.3
