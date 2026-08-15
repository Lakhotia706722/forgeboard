"""
Pydantic schemas for workspace member management — Phase 9b.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import WorkspaceMemberStatus, WorkspaceRole


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------

class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: WorkspaceRole
    status: WorkspaceMemberStatus
    joined_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberInvite(BaseModel):
    email: EmailStr
    role: WorkspaceRole = Field(
        default=WorkspaceRole.VIEWER,
        description="Role to assign: admin | builder | viewer | agency",
    )


class MemberRoleUpdate(BaseModel):
    role: WorkspaceRole


# ---------------------------------------------------------------------------
# Workspace settings
# ---------------------------------------------------------------------------

class WorkspaceDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    is_active: bool
    spend_cap_usd_cents: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    spend_cap_usd_cents: int | None = Field(default=None, ge=0)
