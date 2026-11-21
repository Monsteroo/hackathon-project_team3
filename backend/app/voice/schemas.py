"""Схеми модуля voice — контракт з фронтом і агентом. Приклади: mocks/voice_*.json."""

from typing import Literal

from pydantic import BaseModel


class CleanupInfo(BaseModel):
    model: str | None  # яка LLM чистила текст (None — LLM не викликалась)
    guard: Literal["ok", "rejected", "skipped", "llm_unavailable"]  # rejected → text = raw_text
    new_words: list[str] = []
    issues: dict[str, list] = {}  # чому відхилено: new_words / new_numbers / lost_restrictions / lost_words
    tokens: int = 0


class VoiceResult(BaseModel):
    text: str  # очищений запит → агенту (Учасник 5)
    raw_text: str  # що почули — для показу користувачу
    mode: Literal["walk", "car"] | None  # null — не згадано, лишити перемикач як є
    radius_km: float | None  # null — не згадано, береться дефолт /geo
    duration_s: float | None  # тривалість запису, с
    source: str  # groq_whisper | manual | web_speech
    cleanup: CleanupInfo


class VoiceErrorDetail(BaseModel):
    code: str  # див. HANDOFF.md: stt_rate_limited, no_speech, audio_too_large, rate_limited, …
    message: str  # англійською; текст для людини UI бере за code
    fallback: bool  # true → запропонувати Web Speech у браузері або ручний ввід
