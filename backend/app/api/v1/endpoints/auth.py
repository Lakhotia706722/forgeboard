"""
Auth endpoints: signup, login, token refresh, logout, /me, workspace management.

Phase 9a additions:
  GET  /auth/workspaces           — list all workspaces the user belongs to
  POST /auth/workspaces           — create a new workspace
  POST /auth/workspaces/{id}/accept — accept a pending invite
"""
import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DB
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
    WorkspaceCreate,
    WorkspaceOut,
)
from app.services import auth_service

router = APIRouter()


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(body: SignupRequest, db: DB):
    """
    Create a new user account and a default workspace.
    Returns the user object (with workspaces list) and a JWT token pair.
    """
    result = await auth_service.signup(body, db)
    await db.commit()
    return result


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: DB):
    """
    Authenticate with email + password.
    Returns the user object (with all workspaces) and a JWT token pair.
    """
    return await auth_service.login(body, db)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: DB):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    return await auth_service.refresh_tokens(body.refresh_token, db)


@router.post("/logout", status_code=204)
async def logout():
    """Stateless logout — client discards tokens."""
    return None


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, db: DB):
    """
    Return the currently authenticated user with all their workspaces.
    """
    workspaces = await auth_service.list_user_workspaces(user, db)
    first_active = next((w for w in workspaces if w.member_status and w.member_status.value == "active"), None)
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        workspaces=workspaces,
        workspace=first_active,
    )


# ---------------------------------------------------------------------------
# Workspace management
# ---------------------------------------------------------------------------

@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(user: CurrentUser, db: DB):
    """List all workspaces the authenticated user belongs to (active + pending)."""
    return await auth_service.list_user_workspaces(user, db)


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(body: WorkspaceCreate, user: CurrentUser, db: DB):
    """Create a new workspace. The calling user becomes the owner."""
    result = await auth_service.create_workspace(user, body, db)
    await db.commit()
    return result


@router.post("/workspaces/{workspace_id}/accept", response_model=WorkspaceOut)
async def accept_invite(workspace_id: uuid.UUID, user: CurrentUser, db: DB):
    """Accept a pending workspace invite."""
    result = await auth_service.accept_invite(user, workspace_id, db)
    await db.commit()
    return result
