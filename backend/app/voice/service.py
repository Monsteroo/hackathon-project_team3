"""Публічний сервіс модуля voice. Агент може викликати напряму: `await app.voice.service.parse_text("...")`."""

from app.voice.cleanup import clean_text
from app.voice.errors import VoiceError
from app.voice.stt import MAX_AUDIO_BYTES, transcribe

__all__ = ["MAX_AUDIO_BYTES", "VoiceError", "parse_text", "transcribe_and_clean"]


async def transcribe_and_clean(audio: bytes, filename: str, content_type: str | None) -> dict:
    """Whisper → чистка → {text, raw_text, mode, radius_km, duration_s, source, cleanup}. Кидає VoiceError."""
    stt = await transcribe(audio, filename, content_type)
    return {**(await clean_text(stt["text"])), "duration_s": stt["duration_s"], "source": "groq_whisper"}


async def parse_text(text: str, source: str = "manual") -> dict:
    """Для ручного вводу та Web Speech: та сама чистка і витяг mode/radius_km."""
    return {**(await clean_text(text)), "duration_s": None, "source": source}
