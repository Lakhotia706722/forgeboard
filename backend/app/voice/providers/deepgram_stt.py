"""
Deepgram implementation of STTProvider.

Uses Deepgram's streaming WebSocket API for real-time transcription of
phone-quality audio (8kHz μ-law from Twilio media streams).
"""
import json
import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.voice.interfaces import STTProvider, TranscriptSegment


class DeepgramSTT(STTProvider):
    """
    Stateful STT session for a single call leg.
    Maintains a WebSocket connection to Deepgram for the call's duration.
    """

    DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self) -> None:
        self._ws: Any = None
        self._segments: list[TranscriptSegment] = []
        self._lock = asyncio.Lock()

    async def _ensure_connected(self) -> None:
        if self._ws is not None:
            return
        import websockets
        params = (
            "?model=nova-2-phonecall"
            "&encoding=mulaw"
            "&sample_rate=8000"
            "&channels=1"
            "&punctuate=true"
            "&interim_results=true"
            "&endpointing=300"
        )
        self._ws = await websockets.connect(
            self.DEEPGRAM_WS_URL + params,
            extra_headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"},
        )

    async def transcribe_stream(
        self,
        audio_chunk: bytes,
        sample_rate: int = 8000,
        encoding: str = "mulaw",
    ) -> list[TranscriptSegment]:
        await self._ensure_connected()

        # Send audio bytes
        await self._ws.send(audio_chunk)

        # Collect any available responses (non-blocking drain)
        segments: list[TranscriptSegment] = []
        try:
            while True:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=0.05)
                data = json.loads(raw)
                channel = data.get("channel", {})
                alts = channel.get("alternatives", [{}])
                text = alts[0].get("transcript", "").strip() if alts else ""
                is_final = data.get("is_final", False)
                confidence = alts[0].get("confidence", 1.0) if alts else 1.0

                if text:
                    segments.append(
                        TranscriptSegment(
                            speaker="human",
                            text=text,
                            is_final=is_final,
                            confidence=confidence,
                        )
                    )
        except (asyncio.TimeoutError, Exception):
            pass  # No more messages right now — normal

        return segments

    async def close(self) -> None:
        if self._ws:
            try:
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
