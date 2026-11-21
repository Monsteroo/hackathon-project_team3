import json

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app
from app.voice import cleanup, stt
from app.voice.errors import VoiceError
from app.voice.numbers import normalize_numbers


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def api():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "test-api-key"})


def llm_reply(content: dict, status=200):
    return httpx.Response(
        status,
        json={
            "choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
            "usage": {"total_tokens": 120},
        },
    )


# --- правила mode/radius ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text,mode,radius",
    [
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
        ("підгузки, пішки, не більше, щоб було одного кілометра", "walk", 1.0),
        ("пішки, не більше, щоб відстань складала 2 кілометри", "walk", 2.0),
        ("сирники, ну десь в районі, щоб був магазин", "walk", 1.0),
        ("на авто в районі, щоб не було далі 10 кілометрів", "car", 10.0),
        ("на авто в районі, щоб був магазин, не далі 10 кілометрів", "car", 10.0),
        ("куплю чай в районі театру", None, None),
        ("не більше двох кілограмів картоплі", None, None),
    ],
)
def test_rule_constraints(text, mode, radius):
    assert cleanup.rule_constraints(text) == {"mode": mode, "radius_km": radius}


# --- захист від галюцинацій ---------------------------------------------------------------


def test_guard_allows_numbers_units_and_case_changes():
    raw = "ееее молоко галичина літр і два десятки яєць бюджет двісті п'ятдесят гривень"
    assert cleanup.guard_issues(raw, "Молоко Галичина 1 л, 20 яєць, бюджет 250 грн.") == {}


@pytest.mark.parametrize(
    "raw,cleaned,issue",
    [
        ("купи хліб і молоко", "купи хліб, молоко і масло", "new_words"),
        ("купи хліб і молоко", "хліб, молоко, пиво", "new_words"),
        ("кава і молоко", "кава, молоко і какао", "new_words"),
        ("сир і хліб", "сир, хліб і сирок", "new_words"),
        ("два кіло картоплі", "5 кг картоплі", "new_numbers"),
        ("молоко без лактози і хліб", "молоко і хліб", "lost_restrictions"),
        ("молоко і хліб, тільки свіжий", "молоко і хліб, свіжий", "lost_restrictions"),
        ("молоко і не солодкий чай", "молоко і солодкий чай", "lost_restrictions"),
        ("сметана, гречка і кефір", "сметана і кефір", "lost_words"),
        ("кава і молоко", "какао і молоко", "new_words"),
        ("пиво і хліб", "печиво і хліб", "new_words"),
        ("ярчиця і батон", "ярчиця, гірчиця і батон", "new_words"),
        ("ярчиця і батон", "гірчиця, морозиво і батон", "new_words"),
    ],
)
def test_guard_catches_qa_cases(raw, cleaned, issue):
    assert issue in cleanup.guard_issues(raw, cleaned)


@pytest.mark.parametrize(
    "raw,cleaned",
    [
        ("два кіло картоплі", "2 кг картоплі"),
        ("хочу сирники без цукру на чотири людини, щоб недалеко йти", "сирники без цукру на 4 людини"),
        ("продукти на вечерю для двох до трьохсот гривень, поруч з домом", "продукти на вечерю для 2 до 300 грн"),
        ("дитяче пюре, пішки не більше одного кілометра", "дитяче пюре"),
        ("яблука, банани, ой ні, апельсини", "апельсини"),
        ("ну мені каву і сиру", "кава і сир"),
        ("риба сто п'ятдесят грам і пів літра молока", "риба 150 г і 0,5 л молока"),
        ("кілограм гречки, півтора кіло курячого філе і десяток яйця", "1 кг гречки, 1,5 кг курячого філе і 10 яєць"),
        ("сосиски, ярчиця і батон", "сосиски, гірчиця і батон"),
        ("вода морщинська", "вода Моршинська"),
        ("сирники, ну десь в районі, щоб був магазин", "сирники"),
    ],
)
def test_guard_accepts_legit_cleanup(raw, cleaned):
    assert cleanup.guard_issues(raw, cleaned) == {}


async def test_llm_radius_wins_over_rules():
    r = await cleanup.clean_text(
        "хліб в радіусі 2 км", client=client(lambda req: llm_reply({"text": "хліб", "mode": None, "radius_km": 3}))
    )
    assert r["radius_km"] == 3.0


@pytest.mark.parametrize(
    "raw",
    [
        "короче кава розчинна і шоколад рошен з фундуком, пішки",  # v06
        "молоко без лактози і хліб, не хочу їхати на машині, піду пішки",  # x03
        "кетчуп і майонез, поїду на машині",
    ],
)
async def test_llm_radius_ignored_without_distance_cue(raw):
    """Регресія v06/x03: на «пішки» без відстані LLM ставила 1 км → пошук вужчий за типові 2 км."""
    r = await cleanup.clean_text(
        raw, client=client(lambda req: llm_reply({"text": "x", "mode": "walk", "radius_km": 1}))
    )
    assert r["radius_km"] is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("хліб, щоб недалеко", 1.0),
        ("хліб, ну десь в районі, щоб був магазин", 1.0),
        ("хліб, пішки не більше, щоб було одного кілометра", 1.0),
        ("хліб у радіусі трьох кілометрів", 1.0),  # явна межа є → беремо відповідь LLM
        ("молоко, на авто до десяти кілометрів", 1.0),
    ],
)
async def test_llm_radius_kept_with_distance_cue(raw, expected):
    r = await cleanup.clean_text(
        raw, client=client(lambda req: llm_reply({"text": "хліб", "mode": None, "radius_km": 1}))
    )
    assert r["radius_km"] == expected


def test_guard_catches_added_product():
    raw = "молоко і хліб"
    assert cleanup.new_content_words(raw, "молоко, хліб і цукор") == ["цукор"]


async def test_clean_text_uses_llm_when_guard_ok():
    def h(req):
        return llm_reply({"text": "Молоко Галичина 1 л", "mode": "walk", "radius_km": 1})

    r = await cleanup.clean_text("ну молоко галичина літр недалеко", client=client(h))
    assert r["text"] == "Молоко Галичина 1 л" and r["raw_text"].startswith("ну молоко")
    assert (r["mode"], r["radius_km"]) == ("walk", 1.0)
    assert r["cleanup"]["guard"] == "ok" and r["cleanup"]["model"] == "qwen/qwen3.8-27b"


async def test_clean_text_rejects_hallucination_returns_raw():
    r = await cleanup.clean_text(
        "молоко і хліб",
        client=client(lambda req: llm_reply({"text": "молоко, хліб, ковбаса", "mode": None, "radius_km": None})),
    )
    assert r["text"] == "молоко і хліб" and r["cleanup"]["guard"] == "rejected"
    assert r["cleanup"]["new_words"] == ["ковбаса"]


async def test_clean_text_rejection_normalizes_numbers_and_retains_valid_llm_constraints():
    raw = "десяток яєць і півтора кіло борошна, до трьохсот гривень"
    r = await cleanup.clean_text(
        raw, client=client(lambda req: llm_reply({"text": "яйця, борошно й масло", "mode": "car", "radius_km": 3}))
    )
    assert r["cleanup"]["guard"] == "rejected"
    assert r["raw_text"] == raw and r["text"] == "10 яєць і 1,5 кг борошна, до 300 грн"
    # mode від LLM зберігаємо; радіус — ні, бо людина не згадувала відстань («до 300 грн» — це бюджет)
    assert (r["mode"], r["radius_km"]) == ("car", None)


async def test_clean_text_rejection_uses_rules_for_invalid_llm_constraints():
    r = await cleanup.clean_text(
        "хліб, пішки до 2 км",
        client=client(lambda req: llm_reply({"text": "хліб і масло", "mode": "bike", "radius_km": True})),
    )
    assert r["cleanup"]["guard"] == "rejected"
    assert (r["mode"], r["radius_km"]) == ("walk", 2.0)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Кілограм гречки, два десятки яєць", "1 кг гречки, 20 яєць"),
        ("Півтора кіло, до трьохсот гривень", "1,5 кг, до 300 грн"),
        ("Молоко 2,5 відсотка і 1 літр води", "Молоко 2,5% і 1 л води"),
        ("2 десятки яєць і дві тисячі п’ятсот гривень", "20 яєць і 2500 грн"),
        ("Дві, три штуки м’яса", "2, 3 шт м’яса"),
        ("дві три штуки і пів яблука", "дві три штуки і пів яблука"),
    ],
)
def test_normalize_numbers(raw, expected):
    assert normalize_numbers(raw) == expected


async def test_clean_text_falls_back_to_second_model_then_rules():
    seen = []

    def h(req):
        model = json.loads(req.content)["model"]
        seen.append(model)
        if model.startswith("qwen"):
            return httpx.Response(500)
        return llm_reply({"text": "хліб", "mode": None, "radius_km": None})

    r = await cleanup.clean_text("ну хліб", client=client(h))
    assert seen == ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"] and r["cleanup"]["model"] == "openai/gpt-oss-120b"

    r = await cleanup.clean_text("хліб на машині", client=client(lambda req: httpx.Response(503)))
    assert r["text"] == "хліб на машині" and r["mode"] == "car" and r["cleanup"]["guard"] == "llm_unavailable"


async def test_llm_invalid_values_are_ignored():
    r = await cleanup.clean_text(
        "хліб", client=client(lambda req: llm_reply({"text": "хліб", "mode": "bike", "radius_km": 999}))
    )
    assert r["mode"] is None and r["radius_km"] is None


# --- STT ---------------------------------------------------------------------------------


async def test_transcribe_sends_ukrainian_and_parses():
    seen = {}

    def h(req):
        seen["body"] = req.content
        return httpx.Response(
            200, json={"text": " молоко і хліб ", "duration": 2.4, "segments": [{"no_speech_prob": 0.01}]}
        )

    r = await stt.transcribe(b"abc", "a.webm", "audio/webm", client=client(h))
    assert r == {"text": "молоко і хліб", "duration_s": 2.4}
    assert b'name="language"\r\n\r\nuk' in seen["body"] and b"whisper-large-v3" in seen["body"]


@pytest.mark.parametrize(
    "status,code", [(429, "stt_rate_limited"), (500, "stt_unavailable"), (400, "audio_unsupported")]
)
async def test_transcribe_maps_errors(status, code):
    with pytest.raises(VoiceError) as e:
        await stt.transcribe(b"abc", "a.webm", "audio/webm", client=client(lambda r: httpx.Response(status, text="x")))
    assert e.value.code == code


async def test_transcribe_silence_is_no_speech():
    h = lambda r: httpx.Response(200, json={"text": "Дякую за перегляд!", "segments": [{"no_speech_prob": 0.95}]})  # noqa: E731
    with pytest.raises(VoiceError) as e:
        await stt.transcribe(b"abc", "a.webm", None, client=client(h))
    assert e.value.code == "no_speech" and e.value.fallback is False


async def test_transcribe_limits():
    with pytest.raises(VoiceError, match="empty"):
        await stt.transcribe(b"", "a.webm", None)
    with pytest.raises(VoiceError) as e:
        await stt.transcribe(b"x" * (stt.MAX_AUDIO_BYTES + 1), "a.webm", None)
    assert e.value.status == 413


# --- API ---------------------------------------------------------------------------------


async def test_api_transcribe_error_shape(monkeypatch):
    async def boom(*a, **k):
        raise VoiceError("stt_rate_limited", "quota", status=429)

    monkeypatch.setattr("app.voice.service.transcribe", boom)
    async with api() as c:
        r = await c.post("/voice/transcribe", files={"audio": ("a.webm", b"abc", "audio/webm")})
    assert r.status_code == 429
    assert r.json()["detail"] == {"code": "stt_rate_limited", "message": "quota", "fallback": True}


async def test_api_parse_text(monkeypatch):
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
        r = await c.post("/voice/parse-text", json={"text": "хліб", "source": "web_speech"})
        unauth = await AsyncClient(transport=ASGITransport(app=app), base_url="http://test").post(
            "/voice/parse-text", json={"text": "хліб"}
        )
    assert r.status_code == 200 and r.json()["source"] == "web_speech"
    assert unauth.status_code == 401
