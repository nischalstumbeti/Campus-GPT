"""Text-to-Speech: ElevenLabs when enabled; otherwise edge-tts (Indian English)."""
import io
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _eleven_enabled() -> bool:
    key = (settings.ELEVENLABS_API_KEY or "").strip()
    if not key:
        return False
    return bool(getattr(settings, "ELEVENLABS_ENABLED", True))


async def text_to_speech(text: str, voice: str = None) -> bytes:
    """
    Convert text to speech.
    Uses ElevenLabs when ELEVENLABS_API_KEY (+ ENABLED) is set; otherwise Microsoft Edge TTS.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    if _eleven_enabled():
        voice_id = (voice if voice and len(voice) > 10 else None) or (
            settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"
        )
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY.strip(),
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        # Try modern multilingual model first, then classic
        for model_id in ("eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_monolingual_v1"):
            payload = {
                "text": text.strip()[:2500],
                "model_id": model_id,
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
            }
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post(url, headers=headers, json=payload)
                if r.status_code < 400 and r.content:
                    return r.content
                # Free plans often block premade library voices (402) — fall through to edge-tts
                logger.warning(
                    "ElevenLabs TTS %s -> %s %s",
                    model_id,
                    r.status_code,
                    (r.text or "")[:160],
                )
                if r.status_code in (401, 402, 403):
                    break
            except Exception as exc:
                logger.warning("ElevenLabs TTS error (%s): %s", model_id, exc)

    import edge_tts

    edge_voice = voice if voice and voice.startswith("en-") else settings.TTS_VOICE
    communicate = edge_tts.Communicate(text.strip(), edge_voice)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    out = audio_buffer.getvalue()
    if not out:
        raise RuntimeError("TTS produced empty audio")
    return out


INDIAN_VOICES_FALLBACK = [
    {"id": "en-IN-NeerjaNeural", "name": "Neerja (Female)", "gender": "Female"},
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat (Male)", "gender": "Male"},
    {"id": "en-IN-NeerjaExpressiveNeural", "name": "Neerja Expressive (Female)", "gender": "Female"},
    {"id": "en-IN-SamNeural", "name": "Sam (Male)", "gender": "Male"},
]


async def get_available_indian_voices() -> list[dict]:
    """List available Indian English voices."""
    try:
        import edge_tts

        voices = await edge_tts.list_voices()
        indian = [v for v in voices if v.get("Locale", "").startswith("en-IN")]
        if indian:
            return [
                {"id": v["ShortName"], "name": v["ShortName"], "gender": v.get("Gender", "")}
                for v in indian
            ]
    except Exception:
        pass
    return INDIAN_VOICES_FALLBACK
