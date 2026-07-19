"""
Run service — create, list, get run records and trigger execution.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentStatus
from app.models.run import AgentRun, RunStatus
from app.schemas.run import RunDetail, RunOut, TraceEvent


# ---------------------------------------------------------------------------
# Record creation (used by API endpoint + scheduler)
# ---------------------------------------------------------------------------

async def create_run_record(
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    trigger_source: str,
    db: AsyncSession,
) -> AgentRun:
    run = AgentRun(
        agent_id=agent_id,
        workspace_id=workspace_id,
        trigger_source=trigger_source,
        status=RunStatus.PENDING,
    )
    db.add(run)
    await db.flush()
    return run


# ---------------------------------------------------------------------------
# Trigger a manual run
# ---------------------------------------------------------------------------

async def trigger_manual_run(
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> RunOut:
    # Verify agent exists and belongs to workspace
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    if not agent.agent_config_json:
        raise HTTPException(
            status_code=422,
            detail="Agent config not built. Save the agent first.",
        )

    if agent.status == AgentStatus.PAUSED:
        raise HTTPException(status_code=422, detail="Agent is paused. Resume it before running.")

    # Create run record
    run = await create_run_record(agent_id, workspace_id, "manual", db)
    await db.commit()

    # Enqueue Celery task
    from app.workers.celery_app import celery_app
    celery_app.send_task("run_agent", args=[str(agent_id), str(run.id)])

    return RunOut.model_validate(run)


# ---------------------------------------------------------------------------
# Query runs
# ---------------------------------------------------------------------------

async def list_runs(
    workspace_id: uuid.UUID,
    db: AsyncSession,
    agent_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[RunOut]:
    query = select(AgentRun).where(AgentRun.workspace_id == workspace_id)
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    query = query.order_by(AgentRun.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [RunOut.model_validate(r) for r in result.scalars().all()]


async def get_run(
    run_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> RunDetail:
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    trace: list[TraceEvent] = []
    if run.trace_json:
        try:
            raw = json.loads(run.trace_json)
            trace = [TraceEvent.model_validate(e) for e in raw]
        except Exception:
            pass

    return RunDetail(
        id=run.id,
        agent_id=run.agent_id,
        workspace_id=run.workspace_id,
        status=run.status,
        trigger_source=run.trigger_source,
        celery_task_id=run.celery_task_id,
        output=run.output,
        error=run.error,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_usd_cents=run.cost_usd_cents,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        trace=trace,
    )
