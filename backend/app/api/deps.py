"""
FastAPI dependency factories for use across all endpoint modules.

Multi-workspace (Phase 9a):
  current_workspace now reads the X-Workspace-ID request header and validates
  that the authenticated user is an active member of that workspace.
  Returns 400 if the header is missing, 403 if the user is not a member.

  All existing endpoints that inject CurrentWorkspace continue to work
  unchanged — the only difference is the workspace is now resolved from the
  header rather than hardcoded to user.workspaces[0].
"""
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, Workspace, WorkspaceMember, WorkspaceMemberStatus
from app.services.auth_service import get_current_user

bearer_scheme = HTTPBearer()


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated User from the Bearer token."""
    return await get_current_user(credentials.credentials, db)


async def current_workspace(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header()] = None,
) -> Workspace:
    """
    Resolve the active workspace for the current request.

    Clients MUST send the X-Workspace-ID header on every authenticated request.
    The server validates that the authenticated user is an active member of
    that workspace before returning it.

    Backwards compatibility:
      If X-Workspace-ID is absent and the user has exactly one active workspace,
      we fall back to that workspace silently.  This preserves compatibility
      with Phase 0–8 clients and test suites that don't send the header yet.
      Once all clients are updated this fallback can be removed.
    """
    # --- Resolve workspace_id from header ---
    if x_workspace_id:
        try:
            ws_uuid = uuid.UUID(x_workspace_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Workspace-ID header is not a valid UUID.",
            )
    else:
        # Fallback: use first active membership (Phase 0–8 compat)
        active = [
            m for m in user.memberships
            if m.status == WorkspaceMemberStatus.ACTIVE and m.workspace
        ]
        if not active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active workspace found. Send X-Workspace-ID header.",
            )
        if len(active) > 1:
            # Multiple workspaces and no header — ambiguous, require explicit selection
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This account belongs to multiple workspaces. "
                    "Send the X-Workspace-ID header to select one."
                ),
            )
        return active[0].workspace

    # --- Validate membership ---
    member_result = await db.execute(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == ws_uuid,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this workspace.",
        )

    # Load the workspace
    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == ws_uuid, Workspace.is_active.is_(True))
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    return workspace


# Convenient type aliases
CurrentUser = Annotated[User, Depends(current_user)]
CurrentWorkspace = Annotated[Workspace, Depends(current_workspace)]
DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# RBAC — role-based access control helpers
# ---------------------------------------------------------------------------

async def current_member(
    user: Annotated[User, Depends(current_user)],
    workspace: Annotated[Workspace, Depends(current_workspace)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> "WorkspaceMember":
    """
    Return the WorkspaceMember row for the current user+workspace.
    Used by require_role() to check permissions.
    """
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this workspace.",
        )
    return member


CurrentMember = Annotated["WorkspaceMember", Depends(current_member)]


def require_role(*allowed_roles: "WorkspaceRole"):
    """
    Dependency factory: raises 403 if the calling user's role is not in
    allowed_roles for the current workspace.

    Usage in endpoints:
        @router.delete("/{id}")
        async def delete_something(
            _: Annotated[None, Depends(require_role("owner", "admin"))],
            workspace: CurrentWorkspace,
            db: DB,
        ):
    """
    from app.models.user import WorkspaceRole as _Role

    async def _check(member: CurrentMember) -> None:
        if member.role not in allowed_roles:
            allowed_str = ", ".join(r if isinstance(r, str) else r.value for r in allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {allowed_str}.",
            )

    return Depends(_check)


# ---------------------------------------------------------------------------
# Twilio webhook signature validation
# ---------------------------------------------------------------------------

async def validate_twilio_signature(request: Request) -> None:
    """
    Verify the X-Twilio-Signature header on inbound Twilio webhook requests.
    Returns 403 if the signature is invalid.
    Skips validation when TWILIO_AUTH_TOKEN is not configured (dev/test).
    """
    if not settings.TWILIO_AUTH_TOKEN:
        return

    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        return

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")

    url = str(request.url)
    if settings.TWILIO_WEBHOOK_BASE_URL:
        from urllib.parse import urlparse, urlunparse
        parsed_request = urlparse(url)
        parsed_base = urlparse(settings.TWILIO_WEBHOOK_BASE_URL)
        url = urlunparse(parsed_request._replace(
            scheme=parsed_base.scheme,
            netloc=parsed_base.netloc,
        ))

    form_params: dict[str, str] = {}
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        form_params = dict(form_data)

    if not validator.validate(url, form_params, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature.",
        )


TwilioWebhook = Annotated[None, Depends(validate_twilio_signature)]
