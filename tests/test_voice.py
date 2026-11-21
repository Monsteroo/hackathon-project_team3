import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.app import app
from backend.voice import cleanup, stt
from backend.voice.errors import VoiceError


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    s = config.get_settings()
    monkeypatch.setattr(config, "get_settings", lambda: s.__class__(**{**s.__dict__, "groq_api_key": "test"}))
    for mod in (cleanup, stt):
        monkeypatch.setattr(mod, "get_settings", config.get_settings)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def llm_reply(content: dict, status=200):
    return httpx.Response(status, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
                                        "usage": {"total_tokens": 120}})


# --- правила mode/radius ---------------------------------------------------------------

@pytest.mark.parametrize("text,mode,radius", [
    ("молоко і хліб, далеко йти не хочу", "walk", 1.0),
    ("сирники, щоб недалеко", "walk", 1.0),
    ("на машині в радіусі трьох кілометрів", "car", 3.0),
    ("пішки до 500 метрів", "walk", 0.5),
    ("в радіусі 2,5 км", None, 2.5),
    ("кава і 1 л молока за 200 гривень", None, None),
    ("поруч, але не далі півтора кілометра", "walk", 1.5),
])
def test_rule_constraints(text, mode, radius):
    assert cleanup.rule_constraints(text) == {"mode": mode, "radius_km": radius}


# --- захист від галюцинацій ---------------------------------------------------------------

def test_guard_allows_numbers_units_and_case_changes():
    raw = "ееее молоко галичина літр і два десятки яєць бюджет двісті п'ятдесят гривень"
    assert cleanup.new_content_words(raw, "Молоко Галичина 1 л, 20 яйця, бюджет 250 грн.") == []


def test_guard_catches_added_product():
    raw = "молоко і хліб"
    assert cleanup.new_content_words(raw, "молоко, хліб і цукор") == ["цукор"]


def test_clean_text_uses_llm_when_guard_ok():
    def h(req):
        return llm_reply({"text": "Молоко Галичина 1 л", "mode": "walk", "radius_km": 1})
    r = cleanup.clean_text("ну молоко галичина літр недалеко", client=client(h))
    assert r["text"] == "Молоко Галичина 1 л" and r["raw_text"].startswith("ну молоко")
    assert (r["mode"], r["radius_km"]) == ("walk", 1.0)
    assert r["cleanup"]["guard"] == "ok" and r["cleanup"]["model"] == "qwen/qwen3.8-27b"


def test_clean_text_rejects_hallucination_returns_raw():
    r = cleanup.clean_text("молоко і хліб", client=client(lambda req: llm_reply(
        {"text": "молоко, хліб, ковбаса", "mode": None, "radius_km": None})))
    assert r["text"] == "молоко і хліб" and r["cleanup"]["guard"] == "rejected"
    assert r["cleanup"]["new_words"] == ["ковбаса"]


def test_clean_text_falls_back_to_second_model_then_rules():
    seen = []

    def h(req):
        model = json.loads(req.content)["model"]
        seen.append(model)
        if model.startswith("qwen"):
            return httpx.Response(500)
        return llm_reply({"text": "хліб", "mode": None, "radius_km": None})
    r = cleanup.clean_text("ну хліб", client=client(h))
    assert seen == ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"] and r["cleanup"]["model"] == "openai/gpt-oss-120b"

    r = cleanup.clean_text("хліб на машині", client=client(lambda req: httpx.Response(503)))
    assert r["text"] == "хліб на машині" and r["mode"] == "car" and r["cleanup"]["guard"] == "llm_unavailable"


def test_llm_invalid_values_are_ignored():
    r = cleanup.clean_text("хліб", client=client(lambda req: llm_reply(
        {"text": "хліб", "mode": "bike", "radius_km": 999})))
    assert r["mode"] is None and r["radius_km"] is None


# --- STT ---------------------------------------------------------------------------------

def test_transcribe_sends_ukrainian_and_parses():
    seen = {}

    def h(req):
        seen["body"] = req.content
        return httpx.Response(200, json={"text": " молоко і хліб ", "duration": 2.4,
                                         "segments": [{"no_speech_prob": 0.01}]})
    r = stt.transcribe(b"abc", "a.webm", "audio/webm", client=client(h))
    assert r == {"text": "молоко і хліб", "duration_s": 2.4}
    assert b'name="language"\r\n\r\nuk' in seen["body"] and b"whisper-large-v3" in seen["body"]


@pytest.mark.parametrize("status,code", [(429, "stt_rate_limited"), (500, "stt_unavailable"), (400, "audio_unsupported")])
def test_transcribe_maps_errors(status, code):
    with pytest.raises(VoiceError) as e:
        stt.transcribe(b"abc", "a.webm", "audio/webm", client=client(lambda r: httpx.Response(status, text="x")))
    assert e.value.code == code


def test_transcribe_silence_is_no_speech():
    h = lambda r: httpx.Response(200, json={"text": "Дякую за перегляд!", "segments": [{"no_speech_prob": 0.95}]})  # noqa: E731
    with pytest.raises(VoiceError) as e:
        stt.transcribe(b"abc", "a.webm", None, client=client(h))
    assert e.value.code == "no_speech" and e.value.fallback is False


def test_transcribe_limits():
    with pytest.raises(VoiceError, match="Порожній"):
        stt.transcribe(b"", "a.webm", None)
    with pytest.raises(VoiceError) as e:
        stt.transcribe(b"x" * (stt.MAX_AUDIO_BYTES + 1), "a.webm", None)
    assert e.value.status == 413


# --- API ---------------------------------------------------------------------------------

def test_api_transcribe_error_shape(monkeypatch):
    def boom(*a, **k):
        raise VoiceError("stt_rate_limited", "Ліміт", status=429)
    monkeypatch.setattr("backend.routes_voice.transcribe", boom)
    r = TestClient(app).post("/api/transcribe", files={"audio": ("a.webm", b"abc", "audio/webm")})
    assert r.status_code == 429 and r.json()["error"] == {"code": "stt_rate_limited", "message": "Ліміт", "fallback": True}


def test_api_parse_text(monkeypatch):
    monkeypatch.setattr("backend.routes_voice.clean_text",
                        lambda t: {"text": t, "raw_text": t, "mode": None, "radius_km": None, "cleanup": {}})
    r = TestClient(app).post("/api/parse-text", json={"text": "хліб", "source": "web_speech"})
    assert r.status_code == 200 and r.json()["source"] == "web_speech"
