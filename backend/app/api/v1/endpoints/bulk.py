"""
Bulk action endpoints — Phase 9e.

  POST /bulk/agents/status  — bulk pause/resume/move  [builder, admin, owner]
  POST /bulk/agents/delete  — bulk delete             [builder, admin, owner]
  POST /bulk/agents/clone   — bulk clone across workspaces [agency|admin|owner in both]

All bulk actions that touch live agents require the caller to explicitly
acknowledge the live-agent impact by passing confirm_live=true in the body.
The endpoint returns 422 if live agents are in the selection and confirm_live
is absent or false.
"""
from typing import Annotated

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, CurrentWorkspace, DB, require_role
from app.models.agent import Agent, AgentStatus
from app.schemas.bulk import BulkActionResult, BulkCloneRequest, BulkDelete, BulkStatusUpdate
from sqlalchemy import select
from pydantic import BaseModel

router = APIRouter()

_BUILDER_UP = require_role("owner", "admin", "builder")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class BulkStatusBody(BulkStatusUpdate):
    confirm_live: bool = False  # must be True when any selected agent is live


class BulkDeleteBody(BulkDelete):
    confirm_live: bool = False


class BulkCloneBody(BulkCloneRequest):
    pass  # no confirm needed — clone doesn't touch live agents


# ---------------------------------------------------------------------------
# Bulk status update (pause / resume / move lane)
# ---------------------------------------------------------------------------

@router.post("/agents/status", response_model=BulkActionResult)
async def bulk_update_status(
    body: BulkStatusBody,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    """
    Move multiple agents to the same target status in one request.

    If any selected agent is currently Live and confirm_live=false,
    returns 422 — forcing the caller to explicitly confirm the impact.
    """
    from app.services.agent_service import _validate_status_transition

    # Load all requested agents scoped to this workspace
    result = await db.execute(
        select(Agent).where(
            Agent.id.in_(body.agent_ids),
            Agent.workspace_id == workspace.id,
        )
    )
    agents = result.scalars().all()

    # Check for live agents requiring confirmation
    live_agents = [a for a in agents if a.status == AgentStatus.LIVE]
    if live_agents and not body.confirm_live:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{len(live_agents)} of the selected agents are currently Live. "
                "Set confirm_live=true to proceed."
            ),
        )

    target = AgentStatus(body.status)
    succeeded: list = []
    failed: list = []

    for agent in agents:
        try:
            _validate_status_transition(agent.status, target)
            agent.status = target
            succeeded.append(agent.id)
        except HTTPException as e:
            failed.append({"agent_id": str(agent.id), "reason": e.detail})

    # Report agents not found in this workspace
    found_ids = {a.id for a in agents}
    for requested_id in body.agent_ids:
        if requested_id not in found_ids:
            failed.append({"agent_id": str(requested_id), "reason": "Not found in workspace."})

    await db.commit()

    return BulkActionResult(
        succeeded=succeeded,
        failed=failed,
        total=len(body.agent_ids),
        success_count=len(succeeded),
        failure_count=len(failed),
    )


# ---------------------------------------------------------------------------
# Bulk delete
# ---------------------------------------------------------------------------

@router.post("/agents/delete", response_model=BulkActionResult)
async def bulk_delete(
    body: BulkDeleteBody,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    """
    Delete multiple agents at once.

    Live agents require confirm_live=true.
    Agents not found in the workspace are reported as failures (not a 404).
    """
    result = await db.execute(
        select(Agent).where(
            Agent.id.in_(body.agent_ids),
            Agent.workspace_id == workspace.id,
        )
    )
    agents = result.scalars().all()

    live_agents = [a for a in agents if a.status == AgentStatus.LIVE]
    if live_agents and not body.confirm_live:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{len(live_agents)} of the selected agents are currently Live. "
                "Set confirm_live=true to confirm deletion."
            ),
        )

    succeeded: list = []
    failed: list = []

    for agent in agents:
        await db.delete(agent)
        succeeded.append(agent.id)

    found_ids = {a.id for a in agents}
    for requested_id in body.agent_ids:
        if requested_id not in found_ids:
            failed.append({"agent_id": str(requested_id), "reason": "Not found in workspace."})

    await db.commit()

    return BulkActionResult(
        succeeded=succeeded,
        failed=failed,
        total=len(body.agent_ids),
        success_count=len(succeeded),
        failure_count=len(failed),
    )


# ---------------------------------------------------------------------------
# Bulk clone (agency view — cross-workspace)
# ---------------------------------------------------------------------------

@router.post("/agents/clone", response_model=BulkActionResult)
async def bulk_clone(
    body: BulkCloneBody,
    user: CurrentUser,
    db: DB,
):
    """
    Clone multiple agents from a source workspace into a destination workspace.

    The calling user must have agency|admin|owner role in BOTH workspaces.
    No X-Workspace-ID header needed — the source/dest are in the body.
    Each agent clone starts in DRAFT status in the destination workspace.
    """
    from app.services.agency_service import _assert_agency_access, clone_agent
    from app.schemas.agency import CloneAgentRequest

    # Verify access to both workspaces up front
    await _assert_agency_access(user.id, body.source_workspace_id, db)
    await _assert_agency_access(user.id, body.dest_workspace_id, db)

    succeeded: list = []
    failed: list = []

    for agent_id in body.agent_ids:
        try:
            req = CloneAgentRequest(
                source_workspace_id=body.source_workspace_id,
                source_agent_id=agent_id,
                dest_workspace_id=body.dest_workspace_id,
            )
            result = await clone_agent(req, user.id, db)
            succeeded.append(agent_id)
        except HTTPException as e:
            failed.append({"agent_id": str(agent_id), "reason": e.detail})
        except Exception as e:
            failed.append({"agent_id": str(agent_id), "reason": str(e)})

    await db.commit()

    return BulkActionResult(
        succeeded=succeeded,
        failed=failed,
        total=len(body.agent_ids),
        success_count=len(succeeded),
        failure_count=len(failed),
    )
