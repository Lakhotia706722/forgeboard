"""
Twilio implementation of TelephonyProvider.

Uses the Twilio REST API for call management and TwiML for call control.
WebSocket media streams are opened by Twilio and handled in the call_ws endpoint.
"""
from typing import Any

import httpx
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Connect, VoiceResponse, Stream

from app.core.config import settings
from app.voice.interfaces import CallRecord, TelephonyProvider


class TwilioProvider(TelephonyProvider):

    def __init__(self) -> None:
        self._client = TwilioClient(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )

    async def place_outbound_call(
        self,
        to: str,
        from_: str,
        webhook_url: str,
        extra: dict[str, Any] | None = None,
    ) -> CallRecord:
        """
        Place an outbound call. Twilio will POST to webhook_url when the call
        is answered so we can return TwiML to start the audio stream.
        """
        call = self._client.calls.create(
            to=to,
            from_=from_,
            url=webhook_url,
            method="POST",
            status_callback=f"{settings.TWILIO_WEBHOOK_BASE_URL}/api/v1/voice/status",
            status_callback_method="POST",
            **(extra or {}),
        )
        return CallRecord(
            call_sid=call.sid,
            from_number=from_,
            to_number=to,
            direction="outbound",
            status=call.status,
            raw={"sid": call.sid, "status": call.status},
        )

    async def hang_up(self, call_sid: str) -> None:
        self._client.calls(call_sid).update(status="completed")

    async def transfer_to_human(
        self,
        call_sid: str,
        human_number: str,
        context_twiml: str | None = None,
    ) -> None:
        """
        Warm transfer via TwiML <Dial> redirect.
        If context_twiml is provided, Twilio will say it to the human agent
        before bridging.
        """
        vr = VoiceResponse()
        if context_twiml:
            vr.say(context_twiml, voice="Polly.Joanna")
        vr.dial(human_number)

        self._client.calls(call_sid).update(
            twiml=str(vr),
            method="POST",
        )

    def generate_answer_twiml(
        self,
        websocket_stream_url: str,
        welcome_message: str | None = None,
    ) -> str:
        """
        Returns TwiML that:
        1. Optionally says a welcome message
        2. Opens a bidirectional <Stream> to our WebSocket endpoint
        """
        vr = VoiceResponse()
        if welcome_message:
            vr.say(welcome_message, voice="Polly.Joanna")
        connect = Connect()
        stream = Stream(url=websocket_stream_url)
        stream.parameter(name="track", value="both_tracks")
        connect.append(stream)
        vr.append(connect)
        return str(vr)
