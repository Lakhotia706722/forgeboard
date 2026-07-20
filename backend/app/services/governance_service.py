"""
Governance service — audit log queries, spend cap management,
approval gate helpers.
"""
import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLogEntry
from app.models.run import AgentRun, RunStatus
from app.models.user import Workspace
from app.models.agent import Agent, AgentStatus


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

async def list_audit_log(
    workspace_id: uuid.UUID,
    db: AsyncSession,
    agent_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[AuditLogEntry]:
    q = select(AuditLogEntry).where(AuditLogEntry.workspace_id == workspace_id)
    if agent_id:
        q = q.where(AuditLogEntry.agent_id == agent_id)
    if run_id:
        q = q.where(AuditLogEntry.run_id == run_id)
    q = q.order_by(AuditLogEntry.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


def export_audit_json(entries: list[AuditLogEntry]) -> str:
    rows = []
    for e in entries:
        rows.append({
            "id": str(e.id),
            "workspace_id": str(e.workspace_id),
            "agent_id": str(e.agent_id),
            "run_id": str(e.run_id),
            "agent_name": e.agent_name,
            "tool_name": e.tool_name,
            "tool_input": _safe_json(e.tool_input_json),
            "tool_result": _safe_json(e.tool_result_json),
            "outcome": e.outcome,
            "created_at": e.created_at.isoformat(),
        })
    return json.dumps(rows, indent=2)


def export_audit_csv(entries: list[AuditLogEntry]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "agent_name", "tool_name", "outcome",
            "created_at", "run_id", "agent_id",
        ],
    )
    writer.writeheader()
    for e in entries:
        writer.writerow({
            "id": str(e.id),
            "agent_name": e.agent_name,
            "tool_name": e.tool_name,
            "outcome": e.outcome,
            "created_at": e.created_at.isoformat(),
            "run_id": str(e.run_id),
            "agent_id": str(e.agent_id),
        })
    return output.getvalue()


def _safe_json(raw: str | None) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


# ---------------------------------------------------------------------------
# Spend cap
# ---------------------------------------------------------------------------

async def get_workspace_spend(
    workspace_id: uuid.UUID, db: AsyncSession
) -> dict:
    from sqlalchemy import func
    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    ws = ws_result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    total_result = await db.execute(
        select(func.sum(AgentRun.cost_usd_cents)).where(
            AgentRun.workspace_id == workspace_id,
        )
    )
    total_spent = total_result.scalar() or 0

    return {
        "spend_cap_usd_cents": ws.spend_cap_usd_cents,
        "total_spent_usd_cents": total_spent,
        "remaining_usd_cents": max(0, ws.spend_cap_usd_cents - total_spent),
        "cap_reached": total_spent >= ws.spend_cap_usd_cents,
    }


async def update_spend_cap(
    workspace_id: uuid.UUID,
    new_cap_usd_cents: int,
    db: AsyncSession,
) -> dict:
    if new_cap_usd_cents < 0:
        raise HTTPException(status_code=422, detail="Spend cap must be >= 0.")

    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    ws = ws_result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    ws.spend_cap_usd_cents = new_cap_usd_cents
    await db.flush()
    return {"spend_cap_usd_cents": ws.spend_cap_usd_cents}


# ---------------------------------------------------------------------------
# Approval gate
# ---------------------------------------------------------------------------

async def list_pending_approvals(
    workspace_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """
    Return agents with requires_approval=True that have a RUNNING run —
    these are paused waiting for manual approval.

    Phase 6 MVP: the approval gate pauses the agent status to PAUSED when a run
    starts if requires_approval is True. The user manually resumes via the board.
    Full mid-run approval (pausing inside a tool call loop) would require a more
    complex async signalling mechanism — noted as a pre-production upgrade.
    """
    result = await db.execute(
        select(Agent, AgentRun)
        .join(AgentRun, AgentRun.agent_id == Agent.id)
        .where(
            Agent.workspace_id == workspace_id,
            Agent.requires_approval == True,  # noqa: E712
            AgentRun.status == RunStatus.RUNNING,
        )
        .order_by(AgentRun.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "run_id": str(run.id),
            "started_at": run.started_at.isoformat() if run.started_at else None,
        }
        for agent, run in rows
    ]
