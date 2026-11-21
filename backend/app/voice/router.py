"""HTTP API модуля voice (prefix /voice): аудіо → чистий текст + mode/radius_km; те саме для набраного тексту."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.voice import service
from app.voice.ratelimit import check_voice_limit
from app.voice.schemas import TextIn, VoiceErrorDetail, VoiceResult

router = APIRouter(prefix="/voice", tags=["voice"])

ERRORS = {code: {"model": dict[str, VoiceErrorDetail]} for code in (400, 413, 422, 429, 502, 503, 504)}


def _http(e: service.VoiceError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.to_detail())


@router.post("/transcribe", response_model=VoiceResult, responses=ERRORS)
async def transcribe_audio(
    request: Request,
    audio: Annotated[UploadFile, File(description="webm/opus, mp4/aac, wav, mp3; до 60 с, до 1.5 MB")],
) -> dict:
    try:
        check_voice_limit(request)
        data = await audio.read(service.MAX_AUDIO_BYTES + 1)
        return await service.transcribe_and_clean(data, audio.filename or "audio.webm", audio.content_type)
    except service.VoiceError as e:
        raise _http(e) from e


@router.post("/parse-text", response_model=VoiceResult, responses={429: ERRORS[429]})
async def parse_text(request: Request, body: TextIn) -> dict:
    """Для ручного вводу та fallback Web Speech: та сама чистка і витяг mode/radius_km."""
    try:
        check_voice_limit(request)
    except service.VoiceError as e:
        raise _http(e) from e
    return await service.parse_text(body.text, body.source)
