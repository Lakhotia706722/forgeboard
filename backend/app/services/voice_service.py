"""
Voice agent service — CRUD for VoiceAgent/CallLog + call lifecycle management.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent, AgentStatus
from app.models.run import AgentRun, RunStatus
from app.models.voice_agent import CallLog, CallStatus, VoiceAgent
from app.schemas.voice import (
    CallLogOut,
    PlaceCallRequest,
    TranscriptEntry,
    VoiceAgentCreate,
    VoiceAgentOut,
    VoiceAgentUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# VoiceAgent CRUD
# ---------------------------------------------------------------------------

async def create_voice_agent(
    workspace_id: uuid.UUID, data: VoiceAgentCreate, db: AsyncSession
) -> VoiceAgentOut:
    # Verify base agent exists and belongs to workspace
    ag = await db.execute(
        select(Agent).where(Agent.id == data.agent_id, Agent.workspace_id == workspace_id)
    )
    if not ag.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Base agent not found.")

    # Check not already a voice agent
    existing = await db.execute(
        select(VoiceAgent).where(VoiceAgent.agent_id == data.agent_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This agent already has voice capabilities.")

    va = VoiceAgent(
        agent_id=data.agent_id,
        workspace_id=workspace_id,
        phone_number=data.phone_number or settings.TWILIO_PHONE_NUMBER or None,
        voice_mode=data.voice_mode,
        tts_voice_id=data.tts_voice_id,
        stt_language=data.stt_language,
        max_concurrent_calls=data.max_concurrent_calls,
    )
    db.add(va)
    await db.flush()
    return VoiceAgentOut.model_validate(va)


async def list_voice_agents(workspace_id: uuid.UUID, db: AsyncSession) -> list[VoiceAgentOut]:
    result = await db.execute(
        select(VoiceAgent).where(VoiceAgent.workspace_id == workspace_id)
    )
    return [VoiceAgentOut.model_validate(v) for v in result.scalars().all()]


async def get_voice_agent(
    voice_agent_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> VoiceAgentOut:
    va = await _load_va(voice_agent_id, workspace_id, db)
    return VoiceAgentOut.model_validate(va)


async def update_voice_agent(
    voice_agent_id: uuid.UUID, workspace_id: uuid.UUID,
    data: VoiceAgentUpdate, db: AsyncSession
) -> VoiceAgentOut:
    va = await _load_va(voice_agent_id, workspace_id, db)
    if data.phone_number is not None:
        va.phone_number = data.phone_number
    if data.voice_mode is not None:
        va.voice_mode = data.voice_mode
    if data.tts_voice_id is not None:
        va.tts_voice_id = data.tts_voice_id
    if data.stt_language is not None:
        va.stt_language = data.stt_language
    if data.max_concurrent_calls is not None:
        va.max_concurrent_calls = data.max_concurrent_calls
    await db.flush()
    return VoiceAgentOut.model_validate(va)


async def delete_voice_agent(
    voice_agent_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> None:
    va = await _load_va(voice_agent_id, workspace_id, db)
    await db.delete(va)


async def _load_va(
    voice_agent_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> VoiceAgent:
    r = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == voice_agent_id,
            VoiceAgent.workspace_id == workspace_id,
        )
    )
    va = r.scalar_one_or_none()
    if not va:
        raise HTTPException(status_code=404, detail="Voice agent not found.")
    return va


# ---------------------------------------------------------------------------
# Call lifecycle
# ---------------------------------------------------------------------------

async def initiate_outbound_call(
    voice_agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    request: PlaceCallRequest,
    db: AsyncSession,
) -> CallLogOut:
    va = await _load_va(voice_agent_id, workspace_id, db)

    # Concurrency cap check
    active = await db.execute(
        select(func.count()).where(
            CallLog.voice_agent_id == voice_agent_id,
            CallLog.status == CallStatus.IN_PROGRESS,
        )
    )
    if (active.scalar() or 0) >= va.max_concurrent_calls:
        raise HTTPException(
            status_code=429,
            detail=f"Max concurrent calls ({va.max_concurrent_calls}) reached for this agent.",
        )

    ws_active = await db.execute(
        select(func.count()).where(
            CallLog.workspace_id == workspace_id,
            CallLog.status == CallStatus.IN_PROGRESS,
        )
    )
    if (ws_active.scalar() or 0) >= settings.MAX_CONCURRENT_CALLS_PER_WORKSPACE:
        raise HTTPException(
            status_code=429,
            detail=f"Workspace concurrent call cap ({settings.MAX_CONCURRENT_CALLS_PER_WORKSPACE}) reached.",
        )

    from_number = va.phone_number or settings.TWILIO_PHONE_NUMBER
    if not from_number:
        raise HTTPException(status_code=422, detail="No phone number configured for this voice agent.")

    # Create pending call log
    call_log = CallLog(
        voice_agent_id=va.id,
        workspace_id=workspace_id,
        call_sid="pending",
        from_number=from_number,
        to_number=request.to,
        direction="outbound",
        status=CallStatus.RINGING,
    )
    db.add(call_log)
    await db.flush()

    # Create linked AgentRun
    run = AgentRun(
        agent_id=va.agent_id,
        workspace_id=workspace_id,
        trigger_source="voice_outbound",
        status=RunStatus.RUNNING,
        started_at=_now(),
    )
    db.add(run)
    await db.flush()
    call_log.run_id = run.id

    # Webhook URL for Twilio to POST when call is answered
    webhook_url = (
        f"{settings.TWILIO_WEBHOOK_BASE_URL}/api/v1/voice/answer/{call_log.id}"
    )

    # Place the call via Twilio
    from app.voice.factory import get_telephony_provider
    provider = get_telephony_provider()
    call_record = await provider.place_outbound_call(
        to=request.to,
        from_=from_number,
        webhook_url=webhook_url,
    )
    call_log.call_sid = call_record.call_sid

    await db.commit()
    return _to_call_log_out(call_log)


async def handle_inbound_call(
    voice_agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    call_sid: str,
    from_number: str,
    to_number: str,
    db: AsyncSession,
) -> tuple[CallLog, str]:
    """
    Called when Twilio POSTs to /answer for an inbound call.
    Creates CallLog, returns (call_log, twiml_response).
    """
    va = await _load_va(voice_agent_id, workspace_id, db)

    # Create run + call log
    run = AgentRun(
        agent_id=va.agent_id,
        workspace_id=workspace_id,
        trigger_source="voice_inbound",
        status=RunStatus.RUNNING,
        started_at=_now(),
    )
    db.add(run)
    await db.flush()

    call_log = CallLog(
        voice_agent_id=va.id,
        workspace_id=workspace_id,
        run_id=run.id,
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        direction="inbound",
        status=CallStatus.RINGING,
    )
    db.add(call_log)
    await db.flush()

    # Build TwiML to answer and open media stream
    ws_url = f"wss://{settings.TWILIO_WEBHOOK_BASE_URL.replace('https://', '')}/api/v1/voice/stream/{call_log.id}"
    from app.voice.factory import get_telephony_provider
    twiml = get_telephony_provider().generate_answer_twiml(ws_url)

    await db.commit()
    return call_log, twiml


# ---------------------------------------------------------------------------
# Call log queries
# ---------------------------------------------------------------------------

async def list_call_logs(
    workspace_id: uuid.UUID,
    db: AsyncSession,
    voice_agent_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[CallLogOut]:
    q = select(CallLog).where(CallLog.workspace_id == workspace_id)
    if voice_agent_id:
        q = q.where(CallLog.voice_agent_id == voice_agent_id)
    q = q.order_by(CallLog.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return [_to_call_log_out(c) for c in result.scalars().all()]


async def get_call_log(
    call_log_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> CallLogOut:
    r = await db.execute(
        select(CallLog).where(
            CallLog.id == call_log_id,
            CallLog.workspace_id == workspace_id,
        )
    )
    cl = r.scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Call log not found.")
    return _to_call_log_out(cl)


def _to_call_log_out(cl: CallLog) -> CallLogOut:
    transcript: list[TranscriptEntry] = []
    if cl.transcript_json:
        try:
            raw = json.loads(cl.transcript_json)
            transcript = [TranscriptEntry(**e) for e in raw]
        except Exception:
            pass
    return CallLogOut(
        id=cl.id,
        voice_agent_id=cl.voice_agent_id,
        workspace_id=cl.workspace_id,
        run_id=cl.run_id,
        call_sid=cl.call_sid,
        from_number=cl.from_number,
        to_number=cl.to_number,
        direction=cl.direction,
        status=cl.status,
        duration_seconds=cl.duration_seconds,
        transcript=transcript,
        consent_verified=cl.consent_verified,
        dnc_checked=cl.dnc_checked,
        ai_disclosed=cl.ai_disclosed,
        started_at=cl.started_at,
        ended_at=cl.ended_at,
        created_at=cl.created_at,
    )
