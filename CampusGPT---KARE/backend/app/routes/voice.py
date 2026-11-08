"""Voice API - Speech-to-Text (ElevenLabs Scribe) and Text-to-Speech (ElevenLabs / edge-tts)."""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.voice_service import speech_to_text
from app.services.tts_service import text_to_speech, get_available_indian_voices

router = APIRouter()


@router.post("/voice")
async def voice_to_text(file: UploadFile = File(...)):
    """
    Speech-to-Text: Upload audio (webm from browser MediaRecorder).
    Uses ElevenLabs Scribe when ELEVENLABS_API_KEY is set (no ffmpeg needed).
    Falls back to local Whisper + ffmpeg/pydub if ElevenLabs is unavailable.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    content_type = file.content_type or "audio/webm"
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        text = await speech_to_text(content, content_type)
        return {"text": text, "engine": "elevenlabs_or_whisper"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None  # ElevenLabs voice id or edge-tts en-IN-* name


@router.post("/tts")
async def tts_endpoint(req: TTSRequest):
    """
    Text-to-Speech: ElevenLabs when configured, else edge-tts Indian English.
    Returns MP3 audio.
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    text = req.text.strip()[:5000]
    try:
        audio_bytes = await text_to_speech(text, req.voice)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tts/voices")
async def list_tts_voices():
    """List available Indian English TTS voices."""
    voices = await get_available_indian_voices()
    return {"voices": voices}
