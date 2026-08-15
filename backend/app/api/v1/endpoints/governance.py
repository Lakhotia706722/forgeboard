"""
Governance endpoints:
  GET  /governance/audit              — list audit log entries        [all roles]
  GET  /governance/audit/export       — export as JSON or CSV         [admin, owner]
  GET  /governance/spend              — current spend vs cap          [all roles]
  PATCH /governance/spend-cap         — update workspace spend cap    [admin, owner]
  GET  /governance/pending-approvals  — agents awaiting approval      [all roles]
"""
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, Response

from app.api.deps import CurrentWorkspace, DB, require_role
from app.services import governance_service

router = APIRouter()

_ADMIN_UP = require_role("owner", "admin")


@router.get("/audit")
async def list_audit_log(
    workspace: CurrentWorkspace,
    db: DB,
    agent_id: Optional[uuid.UUID] = Query(default=None),
    run_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=200, le=1000),
):
    entries = await governance_service.list_audit_log(
        workspace.id, db, agent_id=agent_id, run_id=run_id, limit=limit
    )
    return [
        {
            "id": str(e.id),
            "agent_id": str(e.agent_id),
            "run_id": str(e.run_id),
            "agent_name": e.agent_name,
            "tool_name": e.tool_name,
            "tool_input": governance_service._safe_json(e.tool_input_json),
            "tool_result": governance_service._safe_json(e.tool_result_json),
            "outcome": e.outcome,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.get("/audit/export")
async def export_audit_log(
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    agent_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=1000, le=5000),
):
    """Export audit log as JSON or CSV download. Requires admin or owner."""
    entries = await governance_service.list_audit_log(
        workspace.id, db, agent_id=agent_id, limit=limit
    )

    if format == "csv":
        content = governance_service.export_audit_csv(entries)
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    content = governance_service.export_audit_json(entries)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_log.json"},
    )


@router.get("/spend")
async def get_spend(workspace: CurrentWorkspace, db: DB):
    """Return current spend vs cap for the workspace."""
    return await governance_service.get_workspace_spend(workspace.id, db)


@router.patch("/spend-cap")
async def update_spend_cap(
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
    cap_usd_cents: int = Query(
        ...,
        ge=0,
        description="New spend cap in USD cents (e.g. 5000 = $50.00)",
    ),
):
    """Update the hard spend cap. Requires admin or owner."""
    return await governance_service.update_spend_cap(workspace.id, cap_usd_cents, db)


@router.get("/pending-approvals")
async def list_pending_approvals(workspace: CurrentWorkspace, db: DB):
    """Return agents with requires_approval=True that have active runs."""
    return await governance_service.list_pending_approvals(workspace.id, db)
