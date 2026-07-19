"""
Run endpoints:
  POST /agents/{agent_id}/runs          — trigger a manual run
  GET  /agents/{agent_id}/runs          — list runs for an agent
  GET  /runs                            — list all runs in workspace
  GET  /runs/{run_id}                   — get run detail with full trace
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Query

from app.api.deps import CurrentWorkspace, DB
from app.schemas.run import RunDetail, RunOut
from app.services import run_service

router = APIRouter()


@router.post("/agents/{agent_id}/runs", response_model=RunOut, status_code=202)
async def trigger_run(agent_id: uuid.UUID, workspace: CurrentWorkspace, db: DB):
    """
    Manually trigger an agent run. Returns immediately with a PENDING run record.
    The actual execution happens asynchronously in a Celery worker.
    Poll GET /runs/{run_id} to check status.
    """
    return await run_service.trigger_manual_run(agent_id, workspace.id, db)


@router.get("/agents/{agent_id}/runs", response_model=list[RunOut])
async def list_agent_runs(
    agent_id: uuid.UUID,
    workspace: CurrentWorkspace,
    db: DB,
    limit: int = Query(default=50, le=200),
):
    return await run_service.list_runs(workspace.id, db, agent_id=agent_id, limit=limit)


@router.get("/runs", response_model=list[RunOut])
async def list_all_runs(
    workspace: CurrentWorkspace,
    db: DB,
    limit: int = Query(default=50, le=200),
    agent_id: Optional[uuid.UUID] = Query(default=None),
):
    return await run_service.list_runs(workspace.id, db, agent_id=agent_id, limit=limit)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: uuid.UUID, workspace: CurrentWorkspace, db: DB):
    """
    Return a run with its full execution trace (tool calls, results, LLM turns).
    """
    return await run_service.get_run(run_id, workspace.id, db)
