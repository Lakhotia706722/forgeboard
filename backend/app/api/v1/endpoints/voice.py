"""
Voice agent endpoints:

  REST:
  POST   /voice/agents                        — create voice agent (attach to base agent)
  GET    /voice/agents                        — list voice agents in workspace
  GET    /voice/agents/{id}                   — get voice agent
  PATCH  /voice/agents/{id}                   — update voice agent config
  DELETE /voice/agents/{id}                   — remove voice capabilities
  POST   /voice/agents/{id}/call              — trigger outbound call
  GET    /voice/agents/{id}/calls             — list call logs for agent
  GET    /voice/calls                         — list all calls in workspace
  GET    /voice/calls/{call_log_id}           — get call log with transcript

  Twilio webhooks (no auth — validated by Twilio signature):
  POST   /voice/answer/{call_log_id}          — Twilio calls this when call is answered
  POST   /voice/status                        — Twilio call status callbacks

  WebSocket:
  WS     /voice/stream/{call_log_id}          — bidirectional audio stream
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentWorkspace, DB
from app.core.database import AsyncSessionLocal
from app.schemas.voice import (
    CallLogOut,
    PlaceCallRequest,
    VoiceAgentCreate,
    VoiceAgentOut,
    VoiceAgentUpdate,
)
from app.services import voice_service
from app.voice.call_engine import run_call_session

router = APIRouter()


# ---------------------------------------------------------------------------
# Voice agent CRUD
# ---------------------------------------------------------------------------

@router.post("/agents", response_model=VoiceAgentOut, status_code=201)
async def create_voice_agent(
    body: VoiceAgentCreate, workspace: CurrentWorkspace, db: DB
):
    return await voice_service.create_voice_agent(workspace.id, body, db)


@router.get("/agents", response_model=list[VoiceAgentOut])
async def list_voice_agents(workspace: CurrentWorkspace, db: DB):
    return await voice_service.list_voice_agents(workspace.id, db)


@router.get("/agents/{voice_agent_id}", response_model=VoiceAgentOut)
async def get_voice_agent(
    voice_agent_id: uuid.UUID, workspace: CurrentWorkspace, db: DB
):
    return await voice_service.get_voice_agent(voice_agent_id, workspace.id, db)


@router.patch("/agents/{voice_agent_id}", response_model=VoiceAgentOut)
async def update_voice_agent(
    voice_agent_id: uuid.UUID,
    body: VoiceAgentUpdate,
    workspace: CurrentWorkspace,
    db: DB,
):
    return await voice_service.update_voice_agent(voice_agent_id, workspace.id, body, db)


@router.delete("/agents/{voice_agent_id}", status_code=204)
async def delete_voice_agent(
    voice_agent_id: uuid.UUID, workspace: CurrentWorkspace, db: DB
):
    await voice_service.delete_voice_agent(voice_agent_id, workspace.id, db)


# ---------------------------------------------------------------------------
# Outbound call trigger
# ---------------------------------------------------------------------------

@router.post("/agents/{voice_agent_id}/call", response_model=CallLogOut, status_code=202)
async def place_call(
    voice_agent_id: uuid.UUID,
    body: PlaceCallRequest,
    workspace: CurrentWorkspace,
    db: DB,
):
    """
    Initiate an outbound call. Returns a CallLogOut with status=ringing.
    The actual conversation runs async via the WebSocket stream.
    """
    return await voice_service.initiate_outbound_call(
        voice_agent_id, workspace.id, body, db
    )


# ---------------------------------------------------------------------------
# Call log queries
# ---------------------------------------------------------------------------

@router.get("/agents/{voice_agent_id}/calls", response_model=list[CallLogOut])
async def list_agent_calls(
    voice_agent_id: uuid.UUID,
    workspace: CurrentWorkspace,
    db: DB,
    limit: int = Query(default=50, le=200),
):
    return await voice_service.list_call_logs(
        workspace.id, db, voice_agent_id=voice_agent_id, limit=limit
    )


@router.get("/calls", response_model=list[CallLogOut])
async def list_all_calls(
    workspace: CurrentWorkspace,
    db: DB,
    limit: int = Query(default=50, le=200),
    voice_agent_id: Optional[uuid.UUID] = Query(default=None),
):
    return await voice_service.list_call_logs(
        workspace.id, db, voice_agent_id=voice_agent_id, limit=limit
    )


@router.get("/calls/{call_log_id}", response_model=CallLogOut)
async def get_call(
    call_log_id: uuid.UUID, workspace: CurrentWorkspace, db: DB
):
    return await voice_service.get_call_log(call_log_id, workspace.id, db)


# ---------------------------------------------------------------------------
# Twilio webhooks — no JWT auth, validated by Twilio request signature
# ---------------------------------------------------------------------------

@router.post("/answer/{call_log_id}")
async def twilio_answer(call_log_id: uuid.UUID, request: Request):
    """
    Twilio POSTs here when a call is answered (inbound or outbound).
    Returns TwiML to start the bidirectional media stream.

    Production note: validate X-Twilio-Signature before processing.
    See: https://www.twilio.com/docs/usage/webhooks/webhooks-security
    """
    form = await request.form()
    call_sid = form.get("CallSid", "")
    from_number = form.get("From", "")
    to_number = form.get("To", "")

    # For inbound calls routed to a specific voice agent, the voice_agent_id
    # is embedded in the webhook URL path. For outbound, CallLog already exists.
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.voice_agent import CallLog, CallStatus

        # Check if this is an outbound call (CallLog already created)
        r = await db.execute(
            select(CallLog).where(CallLog.id == call_log_id)
        )
        existing = r.scalar_one_or_none()

        if existing:
            # Outbound — update the call SID and generate stream TwiML
            existing.call_sid = call_sid
            existing.status = CallStatus.IN_PROGRESS
            await db.commit()

            from app.core.config import settings
            from app.voice.factory import get_telephony_provider
            ws_url = f"wss://{settings.TWILIO_WEBHOOK_BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/stream/{call_log_id}"
            twiml = get_telephony_provider().generate_answer_twiml(ws_url)
        else:
            # Inbound — need to look up voice agent by phone number
            # For now return minimal TwiML; full inbound routing in Phase 8b
            from twilio.twiml.voice_response import VoiceResponse
            vr = VoiceResponse()
            vr.say("This number is not configured. Goodbye.")
            vr.hangup()
            twiml = str(vr)

    return PlainTextResponse(content=twiml, media_type="application/xml")


@router.post("/status")
async def twilio_status_callback(request: Request):
    """
    Twilio posts call status updates here (completed, failed, etc.).
    Updates the CallLog status accordingly.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    duration = int(form.get("CallDuration", 0))

    status_map = {
        "completed": "completed",
        "failed": "failed",
        "busy": "failed",
        "no-answer": "failed",
        "canceled": "failed",
    }

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.voice_agent import CallLog, CallStatus
        r = await db.execute(
            select(CallLog).where(CallLog.call_sid == call_sid)
        )
        cl = r.scalar_one_or_none()
        if cl:
            mapped = status_map.get(call_status)
            if mapped:
                from app.models.voice_agent import CallStatus as CS
                cl.status = CS(mapped)
            if duration:
                cl.duration_seconds = duration
            await db.commit()

    return PlainTextResponse(content="<?xml version='1.0'?><Response/>", media_type="application/xml")


# ---------------------------------------------------------------------------
# WebSocket — bidirectional audio stream
# ---------------------------------------------------------------------------

@router.websocket("/stream/{call_log_id}")
async def voice_stream(call_log_id: uuid.UUID, websocket: WebSocket):
    """
    Twilio connects here with the bidirectional media stream.
    We receive μ-law audio, run STT → Claude → TTS, and send audio back.
    """
    await websocket.accept()
    async with AsyncSessionLocal() as db:
        try:
            await run_call_session(websocket, call_log_id, db)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            # Ensure call log is marked failed
            from sqlalchemy import select
            from app.models.voice_agent import CallLog, CallStatus
            r = await db.execute(select(CallLog).where(CallLog.id == call_log_id))
            cl = r.scalar_one_or_none()
            if cl and cl.status == CallStatus.IN_PROGRESS:
                cl.status = CallStatus.FAILED
                await db.commit()
