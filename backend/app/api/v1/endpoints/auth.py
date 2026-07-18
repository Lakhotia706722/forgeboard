"""
Auth endpoints: signup, login, token refresh, logout, /me.
"""
from fastapi import APIRouter

from app.api.deps import CurrentUser, DB
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
    WorkspaceOut,
)
from app.services import auth_service

router = APIRouter()


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(body: SignupRequest, db: DB):
    """
    Create a new user account and a default workspace.
    Returns the user object and a JWT token pair.
    """
    return await auth_service.signup(body, db)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: DB):
    """
    Authenticate with email + password.
    Returns the user object and a JWT token pair.
    """
    return await auth_service.login(body, db)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: DB):
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    return await auth_service.refresh_tokens(body.refresh_token, db)


@router.post("/logout", status_code=204)
async def logout():
    """
    Stateless logout — client should discard tokens.
    (Token blocklist / Redis-based revocation can be added pre-production.)
    """
    return None


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    """
    Return the currently authenticated user with their workspace.
    """
    workspace = user.workspaces[0] if user.workspaces else None
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        workspace=WorkspaceOut.model_validate(workspace) if workspace else None,
    )
