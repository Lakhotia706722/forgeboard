"""
Platform audit service — Phase 11a.

Provides a single log() helper that any service can call to record a
platform-wide event into platform_audit_log.

Usage:
    from app.services.platform_audit_service import log_event

    await log_event(
        db=db,
        event_type="member.invited",
        workspace_id=workspace.id,
        actor_user_id=inviter.id,
        actor_email=inviter.email,
        actor_name=inviter.full_name,
        resource_type="workspace_member",
        resource_id=invitee.id,
        after_state={"email": data.email, "role": data.role.value},
        request=request,   # optional FastAPI Request for IP/UA
    )

All parameters except db and event_type are optional so callers only
pass what's meaningful for that event.
"""
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_audit import PlatformAuditLog


async def log_event(
    db: AsyncSession,
    event_type: str,
    workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    actor_name: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    request: Request | None = None,
) -> None:
    """
    Append a platform audit event.  Never raises — audit failures must not
    break the operation being audited.  Silently swallows errors.
    """
    try:
        ip_address: str | None = None
        user_agent: str | None = None

        if request:
            # Respect X-Forwarded-For for reverse-proxy deployments
            forwarded = request.headers.get("X-Forwarded-For")
            ip_address = (
                forwarded.split(",")[0].strip()
                if forwarded
                else (request.client.host if request.client else None)
            )
            user_agent = request.headers.get("User-Agent")

        entry = PlatformAuditLog(
            event_type=event_type,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            actor_name=actor_name,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        # Do NOT flush/commit here — the caller controls the transaction.
        # The entry will be committed with the surrounding operation.
    except Exception:
        pass  # Audit must never break the operation


async def purge_expired_entries(
    workspace_id: uuid.UUID,
    retention_days: int,
    db: AsyncSession,
) -> int:
    """
    Delete platform_audit_log entries older than retention_days for a workspace.
    Returns the number of rows deleted.
    Called by the Celery scheduler (daily).
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import delete as sa_delete
    from app.models.platform_audit import PlatformAuditLog

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(
        sa_delete(PlatformAuditLog).where(
            PlatformAuditLog.workspace_id == workspace_id,
            PlatformAuditLog.created_at < cutoff,
        )
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

import csv
import io
import json


def export_platform_audit_json(entries: list[PlatformAuditLog]) -> str:
    rows = []
    for e in entries:
        rows.append({
            "id": str(e.id),
            "event_type": e.event_type,
            "workspace_id": str(e.workspace_id) if e.workspace_id else None,
            "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
            "actor_email": e.actor_email,
            "actor_name": e.actor_name,
            "resource_type": e.resource_type,
            "resource_id": str(e.resource_id) if e.resource_id else None,
            "before_state": e.before_state,
            "after_state": e.after_state,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat(),
        })
    return json.dumps(rows, indent=2)


def export_platform_audit_csv(entries: list[PlatformAuditLog]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "event_type", "workspace_id", "actor_email",
            "actor_name", "resource_type", "resource_id",
            "before_state", "after_state", "ip_address", "created_at",
        ],
    )
    writer.writeheader()
    for e in entries:
        writer.writerow({
            "id": str(e.id),
            "event_type": e.event_type,
            "workspace_id": str(e.workspace_id) if e.workspace_id else "",
            "actor_email": e.actor_email or "",
            "actor_name": e.actor_name or "",
            "resource_type": e.resource_type or "",
            "resource_id": str(e.resource_id) if e.resource_id else "",
            "before_state": json.dumps(e.before_state) if e.before_state else "",
            "after_state": json.dumps(e.after_state) if e.after_state else "",
            "ip_address": e.ip_address or "",
            "created_at": e.created_at.isoformat(),
        })
    return output.getvalue()
