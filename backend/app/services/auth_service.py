"""
Auth + workspace creation business logic.
"""
import re
import uuid

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, Workspace
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, TokenPair, UserOut, WorkspaceOut


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Simple slug: lowercase, replace spaces with hyphens, strip non-alphanumeric."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:60]  # cap length


async def _unique_slug(base: str, db: AsyncSession) -> str:
    """Append a short UUID suffix if the base slug is already taken."""
    slug = base
    result = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if result.scalar_one_or_none() is None:
        return slug
    return f"{base}-{str(uuid.uuid4())[:8]}"


def _build_auth_response(user: User, workspace: Workspace) -> AuthResponse:
    tokens = TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
    workspace_out = WorkspaceOut.model_validate(workspace)
    user_out = UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        workspace=workspace_out,
    )
    return AuthResponse(user=user_out, tokens=tokens)


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def signup(data: SignupRequest, db: AsyncSession) -> AuthResponse:
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    # Create user
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()  # get user.id without committing

    # Create default workspace (1:1 for MVP)
    slug = await _unique_slug(_slugify(data.full_name + "-workspace"), db)
    workspace = Workspace(
        name=f"{data.full_name}'s Workspace",
        slug=slug,
        owner_id=user.id,
    )
    db.add(workspace)
    await db.flush()

    return _build_auth_response(user, workspace)


async def login(data: LoginRequest, db: AsyncSession) -> AuthResponse:
    result = await db.execute(
        select(User)
        .where(User.email == data.email)
        .options(selectinload(User.workspaces))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    # Use the first (only, for MVP) workspace
    workspace = user.workspaces[0] if user.workspaces else None
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace not found for this user. Contact support.",
        )

    return _build_auth_response(user, workspace)


async def refresh_tokens(refresh_token: str, db: AsyncSession) -> TokenPair:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise credentials_exc

    if payload.get("type") != "refresh":
        raise credentials_exc

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc

    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def get_current_user(token: str, db: AsyncSession) -> User:
    """
    Validate access token and return the User. Used as a FastAPI dependency.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exc

    if payload.get("type") != "access":
        raise credentials_exc

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exc

    result = await db.execute(
        select(User)
        .where(User.id == uuid.UUID(user_id))
        .options(selectinload(User.workspaces))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc

    return user
