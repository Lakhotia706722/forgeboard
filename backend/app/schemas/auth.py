"""
Pydantic schemas for auth endpoints.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import WorkspaceMemberStatus, WorkspaceRole


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Workspace creation
# ---------------------------------------------------------------------------

class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------

class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    # The calling user's role + status in this workspace
    # Populated by the auth / workspace service, not from the ORM directly
    role: WorkspaceRole | None = None
    member_status: WorkspaceMemberStatus | None = None

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    # Multi-workspace: list of all workspaces the user belongs to (active + pending)
    workspaces: list[WorkspaceOut] = []
    # Legacy field kept for backwards compatibility — set to first active workspace
    # Deprecated: clients should use workspaces[] and X-Workspace-ID header
    workspace: WorkspaceOut | None = None

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair
