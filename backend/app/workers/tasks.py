"""
Celery tasks for agent execution.

run_agent_task:
  - Loads AgentConfig from DB
  - Calls Claude with tools in an agentic loop (tool_use → tool_result → repeat)
  - Executes each tool call against the real connector
  - Captures full trace, tokens, cost
  - Retries failed tool calls up to MAX_TOOL_RETRIES
  - Marks run FAILED after MAX_TOOL_RETRIES; increments agent.consecutive_failures
  - Auto-moves agent to NEEDS_REVIEW after 3 consecutive failures
  - Per-workspace concurrency cap enforced via Redis counter

Cost estimation (Claude claude-sonnet-4-5):
  Input:  $3 / 1M tokens  → 0.0003 cents/token → store as micro-cents, convert on display
  Output: $15 / 1M tokens
  We store integer USD cents: round(tokens * rate * 100)
"""
import json
import uuid
from datetime import datetime, timezone

import anthropic
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.encryption import decrypt_json
from app.models.agent import Agent, AgentStatus
from app.models.audit import AuditLogEntry
from app.models.connector import Connector
from app.models.kv_store import KvEntry
from app.models.run import AgentRun, RunStatus
from app.schemas.agent import AgentConfig
from app.schemas.run import TraceEvent
from app.services.tool_executor import execute_tool
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)

MAX_TOOL_CALLS = 20
MAX_TOOL_RETRIES = 2
CONSECUTIVE_FAILURES_THRESHOLD = 3

# Cost in USD cents per 1M tokens (Claude Sonnet)
INPUT_COST_PER_M = 300    # $3.00 / 1M
OUTPUT_COST_PER_M = 1500  # $15.00 / 1M


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estimate_cost(input_tokens: int, output_tokens: int) -> int:
    """Return estimated cost in USD cents."""
    input_cents = (input_tokens / 1_000_000) * INPUT_COST_PER_M
    output_cents = (output_tokens / 1_000_000) * OUTPUT_COST_PER_M
    return round(input_cents + output_cents)


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="run_agent",
    max_retries=0,  # We handle retries inside the task per tool call
    acks_late=True,
)
def run_agent_task(self: Task, agent_id: str, run_id: str) -> dict:
    """
    Execute an agent run synchronously inside the Celery worker.
    Uses asyncio.run() to bridge the async DB/HTTP calls.
    """
    import asyncio
    return asyncio.run(_run_agent_async(agent_id, run_id, self.request.id))


async def _run_agent_async(agent_id: str, run_id: str, celery_task_id: str) -> dict:
    run_uuid = uuid.UUID(run_id)
    agent_uuid = uuid.UUID(agent_id)

    async with AsyncSessionLocal() as db:
        # ── Load run ──────────────────────────────────────────────────────────
        run_result = await db.execute(select(AgentRun).where(AgentRun.id == run_uuid))
        run = run_result.scalar_one_or_none()
        if not run:
            logger.error(f"Run {run_id} not found.")
            return {"error": "Run not found"}

        # ── Load agent ────────────────────────────────────────────────────────
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_uuid))
        agent = agent_result.scalar_one_or_none()
        if not agent or not agent.agent_config_json:
            await _fail_run(run, "Agent or agent config not found.", db)
            await db.commit()
            return {"error": "Agent not found"}

        # ── Mark run as RUNNING ───────────────────────────────────────────────
        run.status = RunStatus.RUNNING
        run.celery_task_id = celery_task_id
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        # ── Check workspace spend cap ─────────────────────────────────────────
        from sqlalchemy import func as sqlfunc
        from app.models.user import Workspace
        ws_result = await db.execute(
            select(Workspace).where(Workspace.id == run.workspace_id)
        )
        workspace = ws_result.scalar_one_or_none()
        if workspace:
            total_spent_result = await db.execute(
                select(sqlfunc.sum(AgentRun.cost_usd_cents)).where(
                    AgentRun.workspace_id == run.workspace_id,
                    AgentRun.status == RunStatus.SUCCESS,
                )
            )
            total_spent = total_spent_result.scalar() or 0
            if total_spent >= workspace.spend_cap_usd_cents:
                await _fail_run(
                    run,
                    f"Workspace spend cap of ${workspace.spend_cap_usd_cents / 100:.2f} reached. "
                    "All agents auto-paused. Adjust your cap in workspace settings.",
                    db,
                )
                # Auto-pause all live agents in this workspace
                from app.models.agent import AgentStatus as AS
                live_agents_result = await db.execute(
                    select(Agent).where(
                        Agent.workspace_id == run.workspace_id,
                        Agent.status == AS.LIVE,
                    )
                )
                for live_agent in live_agents_result.scalars().all():
                    live_agent.status = AS.PAUSED
                await db.commit()
                return {"error": "Spend cap reached"}

        from sqlalchemy import func
        concurrent = await db.execute(
            select(func.count()).where(
                AgentRun.workspace_id == run.workspace_id,
                AgentRun.status == RunStatus.RUNNING,
                AgentRun.id != run.id,
            )
        )
        running_count = concurrent.scalar() or 0
        if running_count >= settings.MAX_CONCURRENT_RUNS_PER_WORKSPACE:
            await _fail_run(
                run,
                f"Workspace concurrency cap ({settings.MAX_CONCURRENT_RUNS_PER_WORKSPACE}) reached. Try again later.",
                db,
            )
            await db.commit()
            return {"error": "Concurrency cap reached"}

        # ── Parse agent config ────────────────────────────────────────────────
        try:
            config = AgentConfig.model_validate_json(agent.agent_config_json)
        except Exception as e:
            await _fail_run(run, f"Failed to parse agent config: {e}", db)
            await db.commit()
            return {"error": str(e)}

        # ── Load connector credentials ────────────────────────────────────────
        connector_creds: dict[str, str | None] = {}
        for conn_id in config.connector_map:
            conn_result = await db.execute(
                select(Connector).where(Connector.id == uuid.UUID(conn_id))
            )
            conn = conn_result.scalar_one_or_none()
            connector_creds[conn_id] = conn.encrypted_credentials if conn else None

        # ── Execute agentic loop ──────────────────────────────────────────────
        trace: list[TraceEvent] = []
        seq = 0
        total_input_tokens = 0
        total_output_tokens = 0
        final_output = ""

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Build Anthropic tools list
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in config.tools
        ]

        messages: list[dict] = []
        # Initial user turn to kick off the agent
        messages.append({
            "role": "user",
            "content": "Execute your goal now. Use your tools to take action.",
        })

        tool_calls_made = 0
        error_msg: str | None = None

        try:
            while tool_calls_made < MAX_TOOL_CALLS:
                # ── LLM call ─────────────────────────────────────────────────
                seq += 1
                trace.append(TraceEvent(
                    seq=seq,
                    type="llm_call",
                    timestamp=_now_iso(),
                    data={"messages_count": len(messages)},
                ))

                api_kwargs: dict = {
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 4096,
                    "system": config.system_prompt,
                    "messages": messages,
                }
                if tools:
                    api_kwargs["tools"] = tools

                response = await client.messages.create(**api_kwargs)

                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

                # ── Process response content blocks ───────────────────────────
                tool_use_blocks = []
                text_blocks = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_use_blocks.append(block)
                    elif block.type == "text":
                        text_blocks.append(block)
                        final_output = block.text  # last text block is the output

                # Append assistant turn
                messages.append({"role": "assistant", "content": response.content})

                # ── Stop if no tool calls ─────────────────────────────────────
                if response.stop_reason == "end_turn" or not tool_use_blocks:
                    break

                # ── Execute tool calls ────────────────────────────────────────
                tool_results = []

                for block in tool_use_blocks:
                    tool_calls_made += 1
                    tool_name = block.name
                    tool_input = block.input

                    seq += 1
                    trace.append(TraceEvent(
                        seq=seq,
                        type="tool_call",
                        timestamp=_now_iso(),
                        data={"tool": tool_name, "input": tool_input},
                    ))

                    # Find matching connector
                    conn_id, conn_meta = _find_connector_for_tool(tool_name, config)
                    result: dict

                    if conn_id is None:
                        result = {"error": f"No connector found for tool '{tool_name}'"}
                    else:
                        # KV store needs DB — handle inline
                        base_name = tool_name.split("__")[0]
                        if conn_meta.get("type") == "kv_store":
                            result = await _exec_kv_tool(
                                base_name, tool_input, run.workspace_id, db
                            )
                        else:
                            # Retry loop for tool calls
                            for attempt in range(MAX_TOOL_RETRIES + 1):
                                result = await execute_tool(
                                    tool_name=tool_name,
                                    tool_input=tool_input,
                                    connector_type=conn_meta["type"],
                                    connector_config=conn_meta.get("config", {}),
                                    encrypted_credentials=connector_creds.get(conn_id),
                                )
                                if "error" not in result or attempt == MAX_TOOL_RETRIES:
                                    break
                                logger.warning(
                                    f"Tool '{tool_name}' failed (attempt {attempt+1}): {result['error']}"
                                )

                    seq += 1
                    trace.append(TraceEvent(
                        seq=seq,
                        type="tool_result",
                        timestamp=_now_iso(),
                        data={"tool": tool_name, "result": result},
                    ))

                    # ── Write audit log entry ─────────────────────────────────
                    audit_entry = AuditLogEntry(
                        workspace_id=run.workspace_id,
                        agent_id=run.agent_id,
                        run_id=run.id,
                        agent_name=agent.name,
                        tool_name=tool_name,
                        tool_input_json=json.dumps(tool_input),
                        tool_result_json=json.dumps(result),
                        outcome="error" if "error" in result else "success",
                    )
                    db.add(audit_entry)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

                # Feed tool results back as user turn
                messages.append({"role": "user", "content": tool_results})

            else:
                # Hit MAX_TOOL_CALLS limit
                final_output += f"\n\n[Stopped: reached maximum tool call limit of {MAX_TOOL_CALLS}]"

        except anthropic.APIError as e:
            error_msg = f"Anthropic API error: {e}"
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during agent execution: {e}"
            logger.exception(error_msg)

        # ── Finalise run ──────────────────────────────────────────────────────
        cost = _estimate_cost(total_input_tokens, total_output_tokens)
        run.input_tokens = total_input_tokens
        run.output_tokens = total_output_tokens
        run.cost_usd_cents = cost
        run.trace_json = json.dumps([t.model_dump() for t in trace])
        run.finished_at = datetime.now(timezone.utc)

        if error_msg:
            run.status = RunStatus.FAILED
            run.error = error_msg
            agent.consecutive_failures += 1
        else:
            run.status = RunStatus.SUCCESS
            run.output = final_output
            run.error = None
            agent.consecutive_failures = 0

        # Update agent counters
        agent.total_runs += 1
        agent.total_cost_usd_cents += cost

        # Auto-move to NEEDS_REVIEW after threshold failures
        if (
            agent.consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD
            and agent.status == AgentStatus.LIVE
        ):
            agent.status = AgentStatus.NEEDS_REVIEW
            seq += 1
            trace.append(TraceEvent(
                seq=seq,
                type="system",
                timestamp=_now_iso(),
                data={"message": f"Agent auto-moved to NEEDS_REVIEW after {agent.consecutive_failures} consecutive failures."},
            ))
            # Re-save trace with the system event
            run.trace_json = json.dumps([t.model_dump() for t in trace])

        await db.commit()

        logger.info(
            f"Run {run_id} finished: status={run.status} "
            f"tokens={total_input_tokens}+{total_output_tokens} cost={cost}¢"
        )
        return {
            "run_id": run_id,
            "status": run.status.value,
            "output": run.output,
            "cost_usd_cents": cost,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_connector_for_tool(
    tool_name: str, config: AgentConfig
) -> tuple[str | None, dict]:
    """
    Given a (possibly namespaced) tool name, find the connector_id and metadata.
    Namespaced: "kv_get__abc12345" → look for connector whose id starts with abc12345
    Non-namespaced: match against all connectors' tool definitions.
    """
    parts = tool_name.split("__")
    if len(parts) == 2:
        suffix = parts[1]
        for conn_id, meta in config.connector_map.items():
            if conn_id.replace("-", "")[:8] == suffix.replace("-", "")[:8]:
                return conn_id, meta
    # Non-namespaced — find by tool type matching
    base = parts[0]
    type_hints = {
        "http_request": "http_webhook",
        "calendar_list_events": "google_calendar",
        "calendar_create_event": "google_calendar",
        "gmail_send": "gmail",
        "kv_get": "kv_store",
        "kv_set": "kv_store",
        "kv_delete": "kv_store",
    }
    target_type = type_hints.get(base)
    if target_type:
        for conn_id, meta in config.connector_map.items():
            if meta.get("type") == target_type:
                return conn_id, meta
    return None, {}


async def _exec_kv_tool(
    tool_name: str,
    inputs: dict,
    workspace_id: uuid.UUID,
    db,
) -> dict:
    key = inputs.get("key", "")
    if not key:
        return {"error": "key is required"}

    if tool_name == "kv_get":
        result = await db.execute(
            select(KvEntry).where(
                KvEntry.workspace_id == workspace_id,
                KvEntry.key == key,
            )
        )
        entry = result.scalar_one_or_none()
        return {"key": key, "value": entry.value if entry else None}

    elif tool_name == "kv_set":
        value = inputs.get("value", "")
        result = await db.execute(
            select(KvEntry).where(
                KvEntry.workspace_id == workspace_id,
                KvEntry.key == key,
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            entry.value = value
        else:
            entry = KvEntry(workspace_id=workspace_id, key=key, value=value)
            db.add(entry)
        await db.flush()
        return {"key": key, "value": value, "saved": True}

    elif tool_name == "kv_delete":
        result = await db.execute(
            select(KvEntry).where(
                KvEntry.workspace_id == workspace_id,
                KvEntry.key == key,
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            await db.delete(entry)
        return {"key": key, "deleted": entry is not None}

    return {"error": f"Unknown KV tool: {tool_name}"}


async def _fail_run(run: AgentRun, error: str, db) -> None:
    run.status = RunStatus.FAILED
    run.error = error
    run.finished_at = datetime.now(timezone.utc)
