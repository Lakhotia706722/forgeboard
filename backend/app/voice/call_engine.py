"""
Call engine — manages the lifecycle of a single voice call.

Flow:
  1. Twilio opens a WebSocket media stream to /api/v1/voice/stream/{call_log_id}
  2. call_engine.run_call_session() drives the loop:
     a. Stream μ-law audio from Twilio → Deepgram STT
     b. Accumulate transcript until a sentence boundary or pause
     c. Feed transcript turn to Claude (same reasoning loop as Phase 4)
     d. Claude responds with text (and optional tool calls via MCP connectors)
     e. Synthesize Claude's text with ElevenLabs TTS → send audio back to Twilio
     f. Repeat until Claude returns stop_reason="end_turn" or caller hangs up
  3. On session end: finalise CallLog, update AgentRun, flush transcript to DB

Phase 8d additions:
  - TRANSFER_TOOL injected into every voice call so Claude can self-escalate
  - _detect_escalation() keyword check after each human turn
  - Warm handoff via TwilioProvider.transfer_to_human() with transcript context
  - Email alert to workspace owner when escalation_number is unset
    (uses existing Gmail connector, falls back to trace log only if none exists)

This module is pure async — it runs directly in the FastAPI WebSocket handler,
not in Celery, because real-time audio latency requires an event loop.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent
from app.models.run import AgentRun, RunStatus
from app.models.voice_agent import CallLog, CallStatus, VoiceAgent
from app.schemas.agent import AgentConfig
from app.schemas.run import TraceEvent
from app.voice.factory import get_stt_provider, get_tts_provider
from app.voice.interfaces import TranscriptSegment
from app.voice.redaction import redact_transcript


MAX_TURNS = 30        # hard cap on conversation turns
SILENCE_TIMEOUT = 3.0  # seconds of silence before Claude responds

# AI disclosure prefix — platform constant.
# This prefix is non-removable.  The trailing text (agent goal) may vary,
# but every call must begin with this statement identifying the caller as AI.
# ⚠ Adjust wording only in consultation with legal counsel.
_DISCLOSURE_PREFIX = "Hello, I'm an AI assistant"

# ---------------------------------------------------------------------------
# Transfer tool — injected into every voice call regardless of agent config.
# Claude can use this to request a warm handoff to a human at any time.
# ---------------------------------------------------------------------------
TRANSFER_TOOL: dict = {
    "name": "transfer_to_human",
    "description": (
        "Transfer this call to a human agent. Use this when: the caller explicitly "
        "requests a human, you cannot resolve their issue, the caller is upset or "
        "distressed, or the situation requires human judgement. "
        "Always inform the caller you are transferring them before using this tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Brief reason for the transfer (shown to the human agent).",
            },
        },
        "required": ["reason"],
    },
}

# Keywords that trigger automatic escalation detection on the human transcript.
# Conservative set — only phrases that unambiguously signal distress or a
# human-agent request.
_ESCALATION_KEYWORDS: list[str] = [
    "speak to a human",
    "talk to a human",
    "real person",
    "speak to a person",
    "talk to a person",
    "speak to a representative",
    "talk to a representative",
    "speak to a manager",
    "talk to a manager",
    "speak to your manager",
    "get me your manager",
    "speak to a supervisor",
    "talk to a supervisor",
    "i want a human",
    "i need a human",
    "i want a real person",
    "this is unacceptable",
    "i am going to sue",
    "i'll sue",
    "i'm furious",
    "i am furious",
    "this is ridiculous",
]


def _build_opening(agent_goal: str, agent_name: str) -> str:
    """
    Build the mandatory opening statement for every voice call.

    The disclosure prefix is a platform constant and cannot be removed.
    The trailing text is derived from the agent's goal (truncated for UX).
    """
    goal_snippet = agent_goal[:100].rstrip() if agent_goal else ""
    if goal_snippet:
        return (
            f"{_DISCLOSURE_PREFIX} calling on behalf of {agent_name}. "
            f"{goal_snippet}. How can I help you today?"
        )
    return f"{_DISCLOSURE_PREFIX} calling on behalf of {agent_name}. How can I help you today?"


def _detect_escalation(text: str) -> bool:
    """Return True if the text contains any escalation keyword."""
    lower = text.lower()
    return any(kw in lower for kw in _ESCALATION_KEYWORDS)


def _build_transfer_context(
    call_log: CallLog,
    transcript: list[TranscriptSegment],
    reason: str,
) -> str:
    """
    Build a brief spoken context summary read to the human agent before
    the call is bridged (via Twilio TwiML <Say>).
    """
    # Last 3 human utterances for context
    human_turns = [s.text for s in transcript if s.speaker == "human"][-3:]
    context_snippet = " | ".join(human_turns) if human_turns else "no prior context"
    return (
        f"Transferring a call from {call_log.from_number}. "
        f"The caller said: {context_snippet[:200]}. "
        f"Reason for transfer: {reason[:200]}."
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


async def run_call_session(
    websocket,           # FastAPI WebSocket
    call_log_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Main call session loop. Called from the WebSocket endpoint.
    Handles the full inbound/outbound call conversation.
    """
    # ── Load call log + voice agent + agent config ────────────────────────────
    cl_result = await db.execute(
        select(CallLog).where(CallLog.id == call_log_id)
    )
    call_log = cl_result.scalar_one_or_none()
    if not call_log:
        await websocket.close(code=1008)
        return

    va_result = await db.execute(
        select(VoiceAgent).where(VoiceAgent.id == call_log.voice_agent_id)
    )
    voice_agent = va_result.scalar_one_or_none()
    if not voice_agent:
        await websocket.close(code=1008)
        return

    ag_result = await db.execute(
        select(Agent).where(Agent.id == voice_agent.agent_id)
    )
    agent = ag_result.scalar_one_or_none()
    if not agent or not agent.agent_config_json:
        await websocket.close(code=1008)
        return

    config = AgentConfig.model_validate_json(agent.agent_config_json)

    # ── Mark call as in-progress ──────────────────────────────────────────────
    call_log.status = CallStatus.IN_PROGRESS
    call_log.started_at = _now()
    await db.commit()

    # ── Initialise providers + state ──────────────────────────────────────────
    stt = get_stt_provider()
    tts = get_tts_provider()
    anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    transcript: list[TranscriptSegment] = []
    trace: list[TraceEvent] = []
    seq = 0
    total_input_tokens = 0
    total_output_tokens = 0

    # ── Opening — mandatory AI disclosure ────────────────────────────────────
    messages: list[dict] = []
    opening = _build_opening(agent.goal, agent.name)
    try:
        audio = await tts.synthesize(opening, voice_id=voice_agent.tts_voice_id)
        await _send_audio(websocket, audio.audio_bytes)
        transcript.append(TranscriptSegment(speaker="agent", text=opening, is_final=True))
        call_log.ai_disclosed = True
        await db.commit()
    except Exception:
        await _send_audio(websocket, b"")  # keep stream alive on TTS failure

    messages.append({"role": "user", "content": "The call has started. Begin the conversation."})

    # Build Anthropic tools list from agent config + inject the transfer tool
    tools: list[dict] = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in config.tools
    ] if config.tools else []
    tools.append(TRANSFER_TOOL)  # always available on voice calls

    # ── Main conversation loop ────────────────────────────────────────────────
    pending_human_text: list[str] = []
    turn_count = 0
    call_transferred = False

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event", "")

            # Twilio sends "media" events with base64 audio chunks
            if event == "media":
                import base64
                chunk = base64.b64decode(data["media"]["payload"])
                segments = await stt.transcribe_stream(chunk)
                for seg in segments:
                    if seg.text and seg.is_final:
                        pending_human_text.append(seg.text)
                        transcript.append(seg)

            # Twilio sends "mark" events to signal end of TTS playback
            elif event == "mark":
                if not pending_human_text:
                    continue

                human_turn = " ".join(pending_human_text)
                pending_human_text.clear()
                turn_count += 1

                if turn_count > MAX_TURNS:
                    await _say_and_send(
                        websocket, tts,
                        "I need to end our call now. Goodbye!",
                        voice_agent,
                    )
                    break

                seq += 1
                trace.append(TraceEvent(
                    seq=seq, type="human_speech",
                    timestamp=_now_iso(),
                    data={"text": human_turn},
                ))

                # ── Escalation detection ──────────────────────────────────────
                if _detect_escalation(human_turn):
                    seq += 1
                    trace.append(TraceEvent(
                        seq=seq, type="escalation_alert",
                        timestamp=_now_iso(),
                        data={"trigger": human_turn[:200], "source": "keyword_detection"},
                    ))
                    voice_agent.total_escalations += 1

                    if voice_agent.escalation_number:
                        # Auto-transfer immediately
                        await _execute_transfer(
                            call_log=call_log,
                            voice_agent=voice_agent,
                            transcript=transcript,
                            reason="Caller requested a human agent (keyword detection).",
                            trace=trace,
                            seq=seq,
                            db=db,
                        )
                        call_transferred = True
                        break
                    else:
                        # No escalation number — send email alert + inject system message
                        await _send_escalation_email(
                            voice_agent=voice_agent,
                            call_log=call_log,
                            trigger_text=human_turn,
                            db=db,
                        )
                        messages.append({
                            "role": "user",
                            "content": (
                                "[SYSTEM: Escalation signal detected in caller's message. "
                                "No human transfer number is configured. "
                                "Acknowledge the caller's concern empathetically and do your best "
                                "to resolve the issue. If you cannot resolve it, inform the caller "
                                "that a human will follow up with them.]"
                            ),
                        })

                # ── Feed to Claude ────────────────────────────────────────────
                messages.append({"role": "user", "content": human_turn})

                seq += 1
                trace.append(TraceEvent(
                    seq=seq, type="llm_call",
                    timestamp=_now_iso(),
                    data={"turn": turn_count},
                ))

                api_kwargs: dict = {
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 512,
                    "system": (
                        config.system_prompt
                        + "\n\nIMPORTANT: You are on a phone call. "
                        "Keep responses under 2 sentences. "
                        "Be natural and conversational. "
                        "If the caller needs a human, use the transfer_to_human tool."
                    ),
                    "messages": messages,
                    "tools": tools,
                }

                response = await anthropic_client.messages.create(**api_kwargs)
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

                agent_text = ""
                tool_calls_in_response = []
                for block in response.content:
                    if block.type == "text":
                        agent_text = block.text
                    elif block.type == "tool_use":
                        tool_calls_in_response.append(block)

                # ── Handle tool calls ─────────────────────────────────────────
                if tool_calls_in_response:
                    # Check if Claude called transfer_to_human
                    transfer_block = next(
                        (b for b in tool_calls_in_response if b.name == "transfer_to_human"),
                        None,
                    )

                    if transfer_block:
                        reason = transfer_block.input.get("reason", "Agent requested transfer.")
                        seq += 1
                        trace.append(TraceEvent(
                            seq=seq, type="escalation_alert",
                            timestamp=_now_iso(),
                            data={"trigger": reason, "source": "claude_tool_call"},
                        ))
                        voice_agent.total_escalations += 1

                        # TTS a handoff message to the caller before transferring
                        handoff_msg = (
                            "I'm transferring you to a human agent right now. "
                            "Please hold for just a moment."
                        )
                        await _say_and_send(websocket, tts, handoff_msg, voice_agent)
                        transcript.append(
                            TranscriptSegment(speaker="agent", text=handoff_msg, is_final=True)
                        )

                        if voice_agent.escalation_number:
                            await _execute_transfer(
                                call_log=call_log,
                                voice_agent=voice_agent,
                                transcript=transcript,
                                reason=reason,
                                trace=trace,
                                seq=seq,
                                db=db,
                            )
                            call_transferred = True
                        else:
                            # No number — alert the owner and keep call live
                            await _send_escalation_email(
                                voice_agent=voice_agent,
                                call_log=call_log,
                                trigger_text=reason,
                                db=db,
                            )
                            seq += 1
                            trace.append(TraceEvent(
                                seq=seq, type="system",
                                timestamp=_now_iso(),
                                data={"note": "Transfer requested but no escalation_number configured. Email alert sent."},
                            ))

                        # Feed a synthetic tool result back to Claude so the
                        # conversation record is coherent, then break
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": transfer_block.id,
                                "content": json.dumps({"transferred": call_transferred}),
                            }],
                        })
                        break

                    # Non-transfer tool calls — run through normal MCP executor
                    non_transfer = [b for b in tool_calls_in_response if b.name != "transfer_to_human"]
                    if non_transfer:
                        tool_results = await _execute_tool_calls(
                            non_transfer, config, call_log.workspace_id, db, trace, seq
                        )
                        seq += len(non_transfer) * 2
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({"role": "user", "content": tool_results})

                        # Follow-up call to get the spoken response after tools
                        follow_up = await anthropic_client.messages.create(
                            model="claude-sonnet-4-5",
                            max_tokens=256,
                            system=api_kwargs["system"],
                            messages=messages,
                            tools=tools,
                        )
                        total_input_tokens += follow_up.usage.input_tokens
                        total_output_tokens += follow_up.usage.output_tokens
                        for block in follow_up.content:
                            if block.type == "text":
                                agent_text = block.text
                        messages.append({"role": "assistant", "content": follow_up.content})
                else:
                    messages.append({"role": "assistant", "content": response.content})

                # ── TTS the agent's response ───────────────────────────────────
                if agent_text:
                    transcript.append(
                        TranscriptSegment(speaker="agent", text=agent_text, is_final=True)
                    )
                    seq += 1
                    trace.append(TraceEvent(
                        seq=seq, type="agent_speech",
                        timestamp=_now_iso(),
                        data={"text": agent_text},
                    ))
                    await _say_and_send(websocket, tts, agent_text, voice_agent)

                if response.stop_reason == "end_turn" and not tool_calls_in_response:
                    break

            elif event == "stop":
                break

    except Exception as e:
        trace.append(TraceEvent(
            seq=seq + 1, type="error",
            timestamp=_now_iso(),
            data={"error": str(e)},
        ))
    finally:
        await stt.close()

    # ── Finalise call log ─────────────────────────────────────────────────────
    if not call_transferred:
        call_log.status = CallStatus.COMPLETED
    # TRANSFERRED status is set inside _execute_transfer — don't overwrite it

    call_log.ended_at = _now()
    if call_log.started_at:
        call_log.duration_seconds = int(
            (_now() - call_log.started_at).total_seconds()
        )

    # Redact sensitive data before persisting
    transcript = redact_transcript(transcript)
    call_log.transcript_json = json.dumps([
        {"speaker": s.speaker, "text": s.text, "timestamp_ms": s.timestamp_ms}
        for s in transcript
    ])
    # ai_disclosed was already set True when the opening TTS was sent

    # Update voice agent counters
    voice_agent.total_calls += 1
    voice_agent.total_call_seconds += call_log.duration_seconds

    # Update linked AgentRun if exists
    if call_log.run_id:
        run_result = await db.execute(
            select(AgentRun).where(AgentRun.id == call_log.run_id)
        )
        run = run_result.scalar_one_or_none()
        if run:
            from app.workers.tasks import _estimate_cost
            cost = _estimate_cost(total_input_tokens, total_output_tokens)
            run.status = RunStatus.SUCCESS
            run.output = transcript[-1].text if transcript else ""
            run.trace_json = json.dumps([t.model_dump() for t in trace])
            run.input_tokens = total_input_tokens
            run.output_tokens = total_output_tokens
            run.cost_usd_cents = cost
            run.finished_at = _now()

    await db.commit()


# ---------------------------------------------------------------------------
# Transfer helpers
# ---------------------------------------------------------------------------

async def _execute_transfer(
    call_log: CallLog,
    voice_agent: VoiceAgent,
    transcript: list[TranscriptSegment],
    reason: str,
    trace: list[TraceEvent],
    seq: int,
    db: AsyncSession,
) -> None:
    """
    Perform a warm transfer to voice_agent.escalation_number.

    Passes a spoken context summary to the human agent via TwiML <Say>
    so they have full context without the caller repeating themselves.
    """
    from app.voice.factory import get_telephony_provider

    context = _build_transfer_context(call_log, transcript, reason)
    try:
        provider = get_telephony_provider()
        await provider.transfer_to_human(
            call_sid=call_log.call_sid,
            human_number=voice_agent.escalation_number,
            context_twiml=context,
        )
        call_log.status = CallStatus.TRANSFERRED
        trace.append(TraceEvent(
            seq=seq + 1, type="transfer",
            timestamp=_now_iso(),
            data={
                "to": voice_agent.escalation_number,
                "reason": reason,
                "context_summary": context[:300],
            },
        ))
    except Exception as e:
        trace.append(TraceEvent(
            seq=seq + 1, type="error",
            timestamp=_now_iso(),
            data={"error": f"Transfer failed: {e}"},
        ))


async def _send_escalation_email(
    voice_agent: VoiceAgent,
    call_log: CallLog,
    trigger_text: str,
    db: AsyncSession,
) -> None:
    """
    Send a real-time escalation alert email to the workspace owner via the
    workspace's Gmail connector (Phase 2).

    Falls back to trace-log-only if no connected Gmail connector exists.
    """
    from sqlalchemy import select as sa_select
    from app.models.connector import Connector, ConnectorStatus, ConnectorType
    from app.models.user import User, Workspace
    from app.services.tool_executor import execute_tool

    try:
        # Look up workspace owner email
        ws_result = await db.execute(
            sa_select(Workspace).where(Workspace.id == call_log.workspace_id)
        )
        workspace = ws_result.scalar_one_or_none()
        if not workspace:
            return

        owner_result = await db.execute(
            sa_select(User).where(User.id == workspace.owner_id)
        )
        owner = owner_result.scalar_one_or_none()
        if not owner:
            return

        # Find a connected Gmail connector for this workspace
        gmail_result = await db.execute(
            sa_select(Connector).where(
                Connector.workspace_id == call_log.workspace_id,
                Connector.connector_type == ConnectorType.GMAIL,
                Connector.status == ConnectorStatus.CONNECTED,
            )
        )
        gmail_connector = gmail_result.scalar_one_or_none()
        if not gmail_connector:
            # No Gmail connector — escalation recorded in trace log only
            return

        import json as _json
        config = _json.loads(gmail_connector.config_json) if gmail_connector.config_json else {}

        subject = f"[ForgeBoard] Escalation Alert — call from {call_log.from_number}"
        body = (
            f"An escalation was detected on an active voice call.\n\n"
            f"Voice Agent: {voice_agent.agent_id}\n"
            f"Call SID:    {call_log.call_sid}\n"
            f"Caller:      {call_log.from_number}\n"
            f"Direction:   {call_log.direction}\n\n"
            f"Trigger text:\n{trigger_text}\n\n"
            f"No escalation transfer number is configured for this agent.\n"
            f"Please follow up with the caller directly.\n\n"
            f"— ForgeBoard Voice Module"
        )

        await execute_tool(
            tool_name="gmail_send",
            tool_input={"to": owner.email, "subject": subject, "body": body},
            connector_type="gmail",
            connector_config=config,
            encrypted_credentials=gmail_connector.encrypted_credentials,
        )

    except Exception:
        # Email failure must never crash the call — trace log captures the event
        pass


# ---------------------------------------------------------------------------
# Audio / TTS helpers
# ---------------------------------------------------------------------------

async def _send_audio(websocket, audio_bytes: bytes) -> None:
    """Send TTS audio back to Twilio as a media event."""
    import base64
    payload = base64.b64encode(audio_bytes).decode()
    await websocket.send_text(json.dumps({
        "event": "media",
        "streamSid": "",  # Twilio fills this in via the stream SID
        "media": {"payload": payload},
    }))


async def _say_and_send(websocket, tts, text: str, voice_agent: VoiceAgent) -> None:
    """TTS synthesise and stream back to caller."""
    try:
        audio = await tts.synthesize(text, voice_id=voice_agent.tts_voice_id)
        await _send_audio(websocket, audio.audio_bytes)
    except Exception:
        pass  # Don't crash the call on TTS failure


# ---------------------------------------------------------------------------
# MCP tool executor (non-transfer tools)
# ---------------------------------------------------------------------------

async def _execute_tool_calls(
    tool_calls: list,
    config: AgentConfig,
    workspace_id: uuid.UUID,
    db: AsyncSession,
    trace: list,
    seq: int,
) -> list:
    """Run MCP connector tool calls inline during a voice conversation."""
    from app.workers.tasks import _find_connector_for_tool, _exec_kv_tool
    from app.services.tool_executor import execute_tool
    from sqlalchemy import select as sa_select
    from app.models.connector import Connector

    # Load credentials for all connectors referenced by the agent config
    connector_creds: dict[str, str | None] = {}
    for conn_id in config.connector_map:
        r = await db.execute(
            sa_select(Connector).where(Connector.id == uuid.UUID(conn_id))
        )
        conn = r.scalar_one_or_none()
        connector_creds[conn_id] = conn.encrypted_credentials if conn else None

    results = []
    for block in tool_calls:
        conn_id, conn_meta = _find_connector_for_tool(block.name, config)
        if conn_id is None:
            result = {"error": f"No connector for tool {block.name}"}
        elif conn_meta.get("type") == "kv_store":
            result = await _exec_kv_tool(
                block.name.split("__")[0], block.input, workspace_id, db
            )
        else:
            result = await execute_tool(
                tool_name=block.name,
                tool_input=block.input,
                connector_type=conn_meta["type"],
                connector_config=conn_meta.get("config", {}),
                encrypted_credentials=connector_creds.get(conn_id),
            )
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result),
        })
    return results
