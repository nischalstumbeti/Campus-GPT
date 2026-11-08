"""Speech-to-Text: ElevenLabs Scribe (preferred) with Whisper fallback."""
from __future__ import annotations

import asyncio
import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_pipeline = None


def _eleven_enabled() -> bool:
    key = (settings.ELEVENLABS_API_KEY or "").strip()
    if not key:
        return False
    # Treat missing flag as enabled when a key is present
    return bool(getattr(settings, "ELEVENLABS_ENABLED", True))


def _ext_for_content_type(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "wav" in ct:
        return "wav"
    if "mpeg" in ct or "mp3" in ct:
        return "mp3"
    if "ogg" in ct:
        return "ogg"
    if "mp4" in ct or "m4a" in ct:
        return "m4a"
    return "webm"


async def _elevenlabs_stt(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """Transcribe with ElevenLabs Scribe — accepts webm/mp3/wav directly (no ffmpeg)."""
    if not _eleven_enabled():
        raise RuntimeError("ElevenLabs STT not configured")

    ext = _ext_for_content_type(content_type)
    filename = f"audio.{ext}"
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY.strip()}
    preferred = (getattr(settings, "ELEVENLABS_STT_MODEL", None) or "scribe_v2").strip()
    model_ids = tuple(dict.fromkeys([preferred, "scribe_v2", "scribe_v1"]))

    last_detail = ""
    async with httpx.AsyncClient(timeout=90.0) as client:
        for model_id in model_ids:
            files = {
                "file": (filename, audio_bytes, content_type or f"audio/{ext}"),
            }
            data = {
                "model_id": model_id,
                # Helps Indian-English campus speech
                "language_code": "en",
            }
            r = await client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers=headers,
                data=data,
                files=files,
            )
            if r.status_code >= 400:
                last_detail = (r.text or "")[:300]
                # Unknown model → try next; auth/quota errors stop early
                if r.status_code in (400, 404, 422) and "model" in last_detail.lower():
                    continue
                raise RuntimeError(f"ElevenLabs STT failed ({r.status_code}): {last_detail}")
            payload = r.json() if r.content else {}
            text = (
                (payload.get("text") if isinstance(payload, dict) else None)
                or (payload.get("transcript") if isinstance(payload, dict) else None)
                or ""
            )
            text = str(text).strip()
            if text:
                return text
            # Empty transcript is still a successful call
            return ""
    raise RuntimeError(f"ElevenLabs STT failed: {last_detail or 'no model accepted'}")


def _ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def _convert_with_ffmpeg(audio_bytes: bytes, src_format: str) -> bytes:
    """Convert audio to wav via ffmpeg CLI (no pydub required)."""
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not installed")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"in.{src_format}"
        dst = Path(td) / "out.wav"
        src.write_bytes(audio_bytes)
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(dst)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not dst.exists():
            raise RuntimeError(proc.stderr[-400:] if proc.stderr else "ffmpeg conversion failed")
        return dst.read_bytes()


def _convert_with_pydub(audio_bytes: bytes, src_format: str) -> bytes:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=src_format)
    wav_buffer = io.BytesIO()
    audio.export(wav_buffer, format="wav")
    return wav_buffer.getvalue()


def _to_wav(audio_bytes: bytes, content_type: str) -> bytes:
    ct = (content_type or "").lower()
    if "wav" in ct:
        return audio_bytes
    fmt = "webm"
    if "ogg" in ct:
        fmt = "ogg"
    elif "mpeg" in ct or "mp3" in ct:
        fmt = "mp3"
    elif "mp4" in ct or "m4a" in ct:
        fmt = "mp4"

    errors: list[str] = []
    try:
        return _convert_with_ffmpeg(audio_bytes, fmt)
    except Exception as exc:
        errors.append(f"ffmpeg: {exc}")
    try:
        return _convert_with_pydub(audio_bytes, fmt)
    except Exception as exc:
        errors.append(f"pydub: {exc}")
    raise RuntimeError(
        "Audio conversion failed. Install ffmpeg, or enable ElevenLabs STT. "
        + "; ".join(errors)
    )


def _get_pipeline():
    """Lazy load Whisper pipeline (local fallback)."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline

        _pipeline = pipeline(
            "automatic-speech-recognition",
            model=settings.WHISPER_MODEL,
            chunk_length_s=30,
            stride_length_s=5,
        )
    return _pipeline


async def _whisper_stt(audio_bytes: bytes, content_type: str = "webm") -> str:
    wav_bytes = _to_wav(audio_bytes, content_type)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        temp_path = f.name
    try:
        pipe = _get_pipeline()
        result = await asyncio.to_thread(pipe, temp_path)
        text = result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()
        return text if text else ""
    finally:
        Path(temp_path).unlink(missing_ok=True)


async def speech_to_text(audio_bytes: bytes, content_type: str = "webm") -> str:
    """
    Transcribe browser audio (usually webm) to text.
    Preference: ElevenLabs Scribe (uses your ELEVENLABS_API_KEY) → local Whisper.
    """
    if not audio_bytes:
        raise ValueError("Empty audio")

    errors: list[str] = []

    if _eleven_enabled():
        try:
            return await _elevenlabs_stt(audio_bytes, content_type)
        except Exception as exc:
            logger.warning("ElevenLabs STT failed, trying Whisper: %s", exc)
            errors.append(f"ElevenLabs: {exc}")

    try:
        return await _whisper_stt(audio_bytes, content_type)
    except Exception as exc:
        errors.append(f"Whisper: {exc}")
        raise RuntimeError(
            "Transcription failed: "
            + (" | ".join(errors) if errors else str(exc))
        ) from exc
