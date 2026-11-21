"""HTTP API голосу: аудіо → чистий текст + mode/radius_km; той самий розбір для набраного тексту."""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.voice.cleanup import clean_text
from backend.voice.errors import VoiceError
from backend.voice.stt import MAX_AUDIO_BYTES, transcribe

router = APIRouter(prefix="/api", tags=["voice"])


def _error(e: VoiceError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"error": e.to_dict()})


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(..., description="webm/opus, mp4/aac, wav, mp3; до 60 с")):
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    try:
        stt = transcribe(data, audio.filename or "audio.webm", audio.content_type)
    except VoiceError as e:
        return _error(e)
    return {**clean_text(stt["text"]), "duration_s": stt["duration_s"], "source": "groq_whisper"}


class TextIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    source: str = Field("manual", description="manual | web_speech")


@router.post("/parse-text")
def parse_text(body: TextIn):
    """Для ручного вводу та fallback Web Speech: та сама чистка і витяг mode/radius_km."""
    return {**clean_text(body.text), "duration_s": None, "source": body.source}
