"""
Auth + workspace creation business logic.
"""
import re
import uuid
from datetime import datetime, timezone

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
from app.models.user import (
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    TokenPair,
    UserOut,
    WorkspaceCreate,
    WorkspaceOut,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Simple slug: lowercase, replace spaces with hyphens, strip non-alphanumeric."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:60]


async def _unique_slug(base: str, db: AsyncSession) -> str:
    """Append a short UUID suffix if the base slug is already taken."""
    slug = base
    result = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if result.scalar_one_or_none() is None:
        return slug
    return f"{base}-{str(uuid.uuid4())[:8]}"


def _workspace_out(workspace: Workspace, role: WorkspaceRole, member_status: WorkspaceMemberStatus) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        created_at=workspace.created_at,
        role=role,
        member_status=member_status,
    )


def _build_user_out(user: User, memberships: list[WorkspaceMember]) -> UserOut:
    """Build UserOut with all workspaces the user is a member of."""
    workspace_outs: list[WorkspaceOut] = []
    for m in memberships:
        if m.workspace:
            workspace_outs.append(
                _workspace_out(m.workspace, m.role, m.status)
            )

    # Legacy: first active owned workspace (backwards compat for Phase 0–8 clients)
    first_active = next(
        (w for w in workspace_outs if w.member_status == WorkspaceMemberStatus.ACTIVE),
        workspace_outs[0] if workspace_outs else None,
    )

    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        workspaces=workspace_outs,
        workspace=first_active,
    )


def _build_auth_response(user: User, memberships: list[WorkspaceMember]) -> AuthResponse:
    tokens = TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
    return AuthResponse(
        user=_build_user_out(user, memberships),
        tokens=tokens,
    )


def _memberships_query():
    """SQLAlchemy query options to load memberships with their workspaces."""
    return selectinload(User.memberships).selectinload(WorkspaceMember.workspace)


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
    await db.flush()

    # Create default workspace
    slug = await _unique_slug(_slugify(data.full_name + "-workspace"), db)
    workspace = Workspace(
        name=f"{data.full_name}'s Workspace",
        slug=slug,
        owner_id=user.id,
    )
    db.add(workspace)
    await db.flush()

    # Create the owner membership
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
        joined_at=_now(),
    )
    db.add(member)
    await db.flush()

    # Attach workspace to member for the response (avoid extra query)
    member.workspace = workspace

    return _build_auth_response(user, [member])


async def login(data: LoginRequest, db: AsyncSession) -> AuthResponse:
    result = await db.execute(
        select(User)
        .where(User.email == data.email)
        .options(_memberships_query())
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

    # Return all active memberships
    active_memberships = [
        m for m in user.memberships
        if m.status == WorkspaceMemberStatus.ACTIVE
    ]
    all_memberships = user.memberships  # include pending for invite banner

    if not active_memberships:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active workspace found for this user. Contact support.",
        )

    return _build_auth_response(user, all_memberships)


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
    Validate access token and return the User with memberships loaded.
    Used as a FastAPI dependency.
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
        .options(_memberships_query())
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc

    return user


# ---------------------------------------------------------------------------
# Workspace CRUD (used by workspace management endpoints)
# ---------------------------------------------------------------------------

async def create_workspace(
    user: User,
    data: WorkspaceCreate,
    db: AsyncSession,
) -> WorkspaceOut:
    """Create a new workspace owned by the given user."""
    slug = await _unique_slug(_slugify(data.name), db)
    workspace = Workspace(
        name=data.name,
        slug=slug,
        owner_id=user.id,
        description=data.description,
    )
    db.add(workspace)
    await db.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
        joined_at=_now(),
    )
    db.add(member)
    await db.flush()

    return _workspace_out(workspace, WorkspaceRole.OWNER, WorkspaceMemberStatus.ACTIVE)


async def list_user_workspaces(user: User, db: AsyncSession) -> list[WorkspaceOut]:
    """Return all workspaces the user is a member of (active + pending)."""
    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .options(selectinload(WorkspaceMember.workspace))
        .order_by(WorkspaceMember.created_at)
    )
    memberships = result.scalars().all()
    return [
        _workspace_out(m.workspace, m.role, m.status)
        for m in memberships
        if m.workspace
    ]


async def accept_invite(
    user: User,
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> WorkspaceOut:
    """Accept a pending workspace invite."""
    result = await db.execute(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == WorkspaceMemberStatus.PENDING,
        )
        .options(selectinload(WorkspaceMember.workspace))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Pending invite not found.")

    member.status = WorkspaceMemberStatus.ACTIVE
    member.joined_at = _now()
    await db.flush()

    return _workspace_out(member.workspace, member.role, member.status)
