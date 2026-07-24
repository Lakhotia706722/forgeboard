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


MAX_TURNS = 30           # hard cap on conversation turns
SILENCE_TIMEOUT = 3.0    # seconds of silence before Claude responds


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

    messages: list[dict] = []
    # Seed the conversation with the AI-disclosure + opening (Phase 8b will enforce this)
    opening = (
        f"Hello! I'm an AI assistant. {agent.goal[:120]}. How can I help you today?"
    )
    # TTS the opening and send immediately
    try:
        audio = await tts.synthesize(opening, voice_id=voice_agent.tts_voice_id)
        await _send_audio(websocket, audio.audio_bytes)
        transcript.append(TranscriptSegment(speaker="agent", text=opening, is_final=True))
    except Exception as e:
        await _send_audio(websocket, b"")  # send empty to keep stream alive

    messages.append({"role": "user", "content": "The call has started. Begin the conversation."})

    # Build Anthropic tools list from agent config
    tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in config.tools
    ] if config.tools else []

    # ── Main conversation loop ────────────────────────────────────────────────
    pending_human_text: list[str] = []
    turn_count = 0

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
                # If we have accumulated human speech, process it
                if pending_human_text:
                    human_turn = " ".join(pending_human_text)
                    pending_human_text.clear()
                    turn_count += 1

                    if turn_count > MAX_TURNS:
                        await _say_and_send(websocket, tts, "I need to end our call now. Goodbye!", voice_agent)
                        break

                    seq += 1
                    trace.append(TraceEvent(
                        seq=seq, type="human_speech",
                        timestamp=_now_iso(),
                        data={"text": human_turn},
                    ))

                    # Feed to Claude
                    messages.append({"role": "user", "content": human_turn})

                    seq += 1
                    trace.append(TraceEvent(
                        seq=seq, type="llm_call",
                        timestamp=_now_iso(),
                        data={"turn": turn_count},
                    ))

                    api_kwargs: dict = {
                        "model": "claude-sonnet-4-5",
                        "max_tokens": 512,   # short responses for phone UX
                        "system": config.system_prompt + "\n\nIMPORTANT: You are on a phone call. Keep responses under 2 sentences. Be natural and conversational.",
                        "messages": messages,
                    }
                    if tools:
                        api_kwargs["tools"] = tools

                    response = await anthropic_client.messages.create(**api_kwargs)
                    total_input_tokens += response.usage.input_tokens
                    total_output_tokens += response.usage.output_tokens

                    agent_text = ""
                    tool_calls = []
                    for block in response.content:
                        if block.type == "text":
                            agent_text = block.text
                        elif block.type == "tool_use":
                            tool_calls.append(block)

                    # Handle tool calls inline (same connector executor as Phase 4)
                    if tool_calls:
                        tool_results = await _execute_tool_calls(tool_calls, config, call_log.workspace_id, db, trace, seq)
                        seq += len(tool_calls) * 2
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({"role": "user", "content": tool_results})

                        # Get final text response after tools
                        follow_up = await anthropic_client.messages.create(
                            model="claude-sonnet-4-5",
                            max_tokens=256,
                            system=api_kwargs["system"],
                            messages=messages,
                        )
                        total_input_tokens += follow_up.usage.input_tokens
                        total_output_tokens += follow_up.usage.output_tokens
                        for block in follow_up.content:
                            if block.type == "text":
                                agent_text = block.text
                        messages.append({"role": "assistant", "content": follow_up.content})
                    else:
                        messages.append({"role": "assistant", "content": response.content})

                    if agent_text:
                        transcript.append(TranscriptSegment(speaker="agent", text=agent_text, is_final=True))
                        seq += 1
                        trace.append(TraceEvent(
                            seq=seq, type="agent_speech",
                            timestamp=_now_iso(),
                            data={"text": agent_text},
                        ))
                        await _say_and_send(websocket, tts, agent_text, voice_agent)

                    if response.stop_reason == "end_turn" and not tool_calls:
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
    call_log.status = CallStatus.COMPLETED
    call_log.ended_at = _now()
    if call_log.started_at:
        call_log.duration_seconds = int(
            (_now() - call_log.started_at).total_seconds()
        )
    call_log.transcript_json = json.dumps([
        {"speaker": s.speaker, "text": s.text, "timestamp_ms": s.timestamp_ms}
        for s in transcript
    ])
    call_log.ai_disclosed = True  # opening message always includes disclosure

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
# Helpers
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


async def _execute_tool_calls(tool_calls, config: AgentConfig, workspace_id: uuid.UUID, db, trace: list, seq: int) -> list:
    """Run tool calls inline during a voice conversation."""
    from app.workers.tasks import _find_connector_for_tool, _exec_kv_tool
    from app.services.tool_executor import execute_tool
    from sqlalchemy import select as sa_select
    from app.models.connector import Connector

    # Load credentials
    connector_creds: dict[str, str | None] = {}
    for conn_id in config.connector_map:
        r = await db.execute(sa_select(Connector).where(Connector.id == uuid.UUID(conn_id)))
        conn = r.scalar_one_or_none()
        connector_creds[conn_id] = conn.encrypted_credentials if conn else None

    results = []
    for block in tool_calls:
        conn_id, conn_meta = _find_connector_for_tool(block.name, config)
        if conn_id is None:
            result = {"error": f"No connector for tool {block.name}"}
        elif conn_meta.get("type") == "kv_store":
            result = await _exec_kv_tool(block.name.split("__")[0], block.input, workspace_id, db)
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
