"""
Workspace member management — Phase 9b.

Handles:
  - Listing members of a workspace
  - Inviting a user by email (creates pending WorkspaceMember row)
  - Changing a member's role
  - Removing a member
  - Updating workspace settings (name, spend cap)

Permission rules are enforced at the endpoint layer via require_role().
This service trusts that the caller has already been authorised.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import (
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.schemas.workspaces import (
    MemberInvite,
    MemberOut,
    MemberRoleUpdate,
    WorkspaceSettingsUpdate,
    WorkspaceDetailOut,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _member_out(member: WorkspaceMember) -> MemberOut:
    return MemberOut(
        user_id=member.user_id,
        email=member.user.email if member.user else "",
        full_name=member.user.full_name if member.user else "",
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        created_at=member.created_at,
    )


# ---------------------------------------------------------------------------
# Member queries
# ---------------------------------------------------------------------------

async def list_members(
    workspace_id: uuid.UUID, db: AsyncSession
) -> list[MemberOut]:
    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .options(selectinload(WorkspaceMember.user))
        .order_by(WorkspaceMember.created_at)
    )
    return [_member_out(m) for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------

async def invite_member(
    workspace_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    data: MemberInvite,
    db: AsyncSession,
) -> MemberOut:
    """
    Create a pending WorkspaceMember for the invited email.

    If the email belongs to an existing user, the invite is immediately
    visible to them on next login.  If no account exists yet, the row
    sits pending until they sign up with that email (future: email invite link).
    """
    # Look up the user by email
    user_result = await db.execute(
        select(User).where(User.email == data.email)
    )
    invitee = user_result.scalar_one_or_none()

    if invitee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No ForgeBoard account found for {data.email}. "
                "They need to sign up first before being invited."
            ),
        )

    # Check they're not already a member
    existing_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == invitee.id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        if existing.status == WorkspaceMemberStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{data.email} is already an active member of this workspace.",
            )
        # Already pending — update role in case it changed
        existing.role = data.role
        await db.flush()
        existing.user = invitee
        return _member_out(existing)

    # Prevent downgrading — can't invite someone as owner via the invite flow
    if data.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot invite someone as owner. Transfer ownership explicitly.",
        )

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=invitee.id,
        role=data.role,
        status=WorkspaceMemberStatus.PENDING,
        invited_by=invited_by_user_id,
    )
    db.add(member)
    await db.flush()

    member.user = invitee
    return _member_out(member)


# ---------------------------------------------------------------------------
# Role update
# ---------------------------------------------------------------------------

async def update_member_role(
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    data: MemberRoleUpdate,
    db: AsyncSession,
) -> MemberOut:
    result = await db.execute(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
        )
        .options(selectinload(WorkspaceMember.user))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    # Can't change owner role via this endpoint
    if member.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=422,
            detail="Cannot change the workspace owner's role. Transfer ownership first.",
        )
    # Can't assign owner role via this endpoint
    if data.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=422,
            detail="Cannot assign owner role. Use ownership transfer.",
        )
    # Can't change your own role
    if target_user_id == requesting_user_id:
        raise HTTPException(status_code=422, detail="Cannot change your own role.")

    member.role = data.role
    await db.flush()
    return _member_out(member)


# ---------------------------------------------------------------------------
# Remove member
# ---------------------------------------------------------------------------

async def remove_member(
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    if member.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=422,
            detail="Cannot remove the workspace owner.",
        )
    if target_user_id == requesting_user_id:
        raise HTTPException(status_code=422, detail="Cannot remove yourself.")

    await db.delete(member)


# ---------------------------------------------------------------------------
# Workspace settings
# ---------------------------------------------------------------------------

async def get_workspace_detail(
    workspace_id: uuid.UUID, db: AsyncSession
) -> WorkspaceDetailOut:
    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    ws = ws_result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return WorkspaceDetailOut(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        is_active=ws.is_active,
        spend_cap_usd_cents=ws.spend_cap_usd_cents,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


async def update_workspace_settings(
    workspace_id: uuid.UUID,
    data: WorkspaceSettingsUpdate,
    db: AsyncSession,
) -> WorkspaceDetailOut:
    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    ws = ws_result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if data.name is not None:
        ws.name = data.name
    if data.description is not None:
        ws.description = data.description
    if data.spend_cap_usd_cents is not None:
        if data.spend_cap_usd_cents < 0:
            raise HTTPException(status_code=422, detail="Spend cap must be >= 0.")
        ws.spend_cap_usd_cents = data.spend_cap_usd_cents

    await db.flush()
    return await get_workspace_detail(workspace_id, db)
