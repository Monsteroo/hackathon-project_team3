"""Публічний сервіс модуля voice: аудіо → чистий текст. Набраний текст розбирає агент (app.agent)."""

from app.voice.cleanup import clean_text
from app.voice.errors import VoiceError
from app.voice.stt import MAX_AUDIO_BYTES, transcribe

__all__ = ["MAX_AUDIO_BYTES", "VoiceError", "transcribe_and_clean"]


async def transcribe_and_clean(audio: bytes, filename: str, content_type: str | None) -> dict:
    """Whisper → чистка → {text, raw_text, mode, radius_km, duration_s, source, cleanup}. Кидає VoiceError."""
    stt = await transcribe(audio, filename, content_type)
    return {**(await clean_text(stt["text"])), "duration_s": stt["duration_s"], "source": "groq_whisper"}
