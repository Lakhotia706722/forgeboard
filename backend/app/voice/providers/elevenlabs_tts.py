"""
ElevenLabs implementation of TTSProvider.

Calls the ElevenLabs REST API to synthesize speech from text.
Returns μ-law 8kHz audio suitable for Twilio media streams.
"""
import httpx

from app.core.config import settings
from app.voice.interfaces import TTSProvider, TTSAudio


class ElevenLabsTTS(TTSProvider):

    BASE_URL = "https://api.elevenlabs.io/v1"

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        speed: float = 1.0,
    ) -> TTSAudio:
        vid = voice_id or settings.ELEVENLABS_VOICE_ID

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/text-to-speech/{vid}",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "speed": speed,
                    },
                    "output_format": "ulaw_8000",  # phone-compatible
                },
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs TTS error {resp.status_code}: {resp.text[:200]}"
            )

        return TTSAudio(
            audio_bytes=resp.content,
            mime_type="audio/basic",  # μ-law
            duration_ms=0,            # ElevenLabs doesn't return duration
        )
