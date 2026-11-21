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
    # QA H2: «близько» без «до дому» — не відстань; «м'ясного» — не метри; число з «м» без контексту — не радіус
    ("близько 2 кг цукру", None, None),
    ("300 м'ясного фаршу", None, None),
    ("2 м ковбаси і в радіусі 500 м", None, 0.5),
    ("не хочу їхати на машині, піду пішки", "walk", None),
    ("близько до дому", "walk", 1.0),
    ("в радіусі п'ятисот метрів", None, 0.5),
])
def test_rule_constraints(text, mode, radius):
    assert cleanup.rule_constraints(text) == {"mode": mode, "radius_km": radius}


# --- захист від галюцинацій ---------------------------------------------------------------

def test_guard_allows_numbers_units_and_case_changes():
    raw = "ееее молоко галичина літр і два десятки яєць бюджет двісті п'ятдесят гривень"
    assert cleanup.guard_issues(raw, "Молоко Галичина 1 л, 20 яєць, бюджет 250 грн.") == {}


@pytest.mark.parametrize("raw,cleaned,issue", [
    ("купи хліб і молоко", "купи хліб, молоко і масло", "new_words"),
    ("купи хліб і молоко", "хліб, молоко, пиво", "new_words"),
    ("кава і молоко", "кава, молоко і какао", "new_words"),
    ("сир і хліб", "сир, хліб і сирок", "new_words"),
    ("два кіло картоплі", "5 кг картоплі", "new_numbers"),
    ("молоко без лактози і хліб", "молоко і хліб", "lost_restrictions"),
    ("молоко і хліб, тільки свіжий", "молоко і хліб, свіжий", "lost_restrictions"),
    ("сметана, гречка і кефір", "сметана і кефір", "lost_words"),
])
def test_guard_catches_qa_cases(raw, cleaned, issue):
    assert issue in cleanup.guard_issues(raw, cleaned)


@pytest.mark.parametrize("raw,cleaned", [
    ("два кіло картоплі", "2 кг картоплі"),
    ("хочу сирники без цукру на чотири людини, щоб недалеко йти", "сирники без цукру на 4 людини"),
    ("продукти на вечерю для двох до трьохсот гривень, поруч з домом", "продукти на вечерю для 2 до 300 грн"),
    ("дитяче пюре, пішки не більше одного кілометра", "дитяче пюре"),
    ("яблука, банани, ой ні, апельсини", "апельсини"),
    ("ну мені каву і сиру", "кава і сир"),
    ("риба сто п'ятдесят грам і пів літра молока", "риба 150 г і 0,5 л молока"),
])
def test_guard_accepts_legit_cleanup(raw, cleaned):
    assert cleanup.guard_issues(raw, cleaned) == {}


def test_llm_radius_wins_over_rules():
    r = cleanup.clean_text("хліб в радіусі 2 км", client=client(lambda req: llm_reply(
        {"text": "хліб", "mode": None, "radius_km": 3})))
    assert r["radius_km"] == 3.0


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
