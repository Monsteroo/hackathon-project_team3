"""Голос → текст: Groq Whisper (`whisper-large-v3`), мова примусово українська.

Підказка (prompt) зі словником брендів підвищує точність назв. Словник — `backend/data/stt_vocabulary.txt`
(по одному слову на рядок); поки порожній — чекаємо брендів з БД Учасника 2 (PRODUCTS.brand).
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from backend.config import DATA_DIR, get_settings
from backend.voice.errors import VoiceError

log = logging.getLogger(__name__)

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
VOCAB_FILE = DATA_DIR / "stt_vocabulary.txt"
MAX_AUDIO_BYTES = 1_500_000         # 60 с opus 32 кбіт/с ≈ 0.25 MB, mp4/aac із Safari ≈ 0.5–1 MB; запас без зловживань
MAX_DURATION_S = 60                 # рішення команди 21.11 (фронт зупиняє запис на 60 с)
DURATION_LIMIT_S = 65               # сервер приймає з невеликим запасом на кодування
NO_SPEECH_THRESHOLD = 0.8
TIMEOUT_S = 20.0


@lru_cache
def vocabulary_prompt() -> str:
    if not VOCAB_FILE.exists():
        return ""
    words = [w.strip() for w in VOCAB_FILE.read_text(encoding="utf-8").splitlines()
             if w.strip() and not w.startswith("#")]
    # Whisper бере до 224 токенів підказки — тримаємо коротко
    return ("Список покупок: " + ", ".join(words))[:600] if words else ""


def transcribe(audio: bytes, filename: str, content_type: str | None, client: httpx.Client | None = None) -> dict:
    settings = get_settings()
    if not settings.groq_api_key:
        raise VoiceError("stt_not_configured", "Розпізнавання голосу не налаштоване", status=503)
    if not audio:
        raise VoiceError("audio_empty", "Порожній запис", status=400, fallback=False)
    if len(audio) > MAX_AUDIO_BYTES:
        raise VoiceError("audio_too_large", f"Запис завеликий (максимум {MAX_DURATION_S} с)", status=413, fallback=False)

    data = {"model": settings.groq_stt_model, "language": "uk", "temperature": "0",
            "response_format": "verbose_json"}
    if prompt := vocabulary_prompt():
        data["prompt"] = prompt

    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        r = client.post(GROQ_STT_URL, headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                        data=data, files={"file": (filename or "audio.webm", audio, content_type or "audio/webm")})
    except httpx.TimeoutException as e:
        raise VoiceError("stt_timeout", "Сервіс розпізнавання не відповів вчасно", status=504) from e
    except httpx.HTTPError as e:
        raise VoiceError("stt_unavailable", "Сервіс розпізнавання недоступний", status=502) from e
    finally:
        if own:
            client.close()

    if r.status_code == 429:
        raise VoiceError("stt_rate_limited", "Ліміт розпізнавання вичерпано, спробуйте за хвилину", status=429)
    if r.status_code == 400:
        log.warning("Groq STT HTTP 400")
        raise VoiceError("audio_unsupported", "Не вдалося прочитати аудіо. Спробуйте ще раз", status=400)
    if r.status_code >= 300:
        log.warning("Groq STT HTTP %s", r.status_code)
        raise VoiceError("stt_unavailable", "Сервіс розпізнавання недоступний", status=502)

    try:
        j = r.json()
    except ValueError as e:
        log.warning("Groq STT: invalid JSON")
        raise VoiceError("stt_unavailable", "Сервіс розпізнавання повернув некоректну відповідь", status=502) from e
    if (j.get("duration") or 0) > DURATION_LIMIT_S:
        raise VoiceError("audio_too_long", f"Запис задовгий (максимум {MAX_DURATION_S} с)", status=413, fallback=False)
    segments = j.get("segments") or []
    text = (j.get("text") or "").strip()
    # Whisper на тиші іноді «галюцинує» фрази на кшталт «Дякую за перегляд» — відсікаємо за no_speech_prob
    if segments and all(s.get("no_speech_prob", 0) > NO_SPEECH_THRESHOLD for s in segments):
        text = ""
    if not text:
        raise VoiceError("no_speech", "Не почули мови. Спробуйте ще раз ближче до мікрофона", status=422,
                         fallback=False)
    return {"text": text, "duration_s": j.get("duration")}
