"""
User, Workspace, and WorkspaceMember ORM models.

Multi-workspace design (Phase 9a):
  - A User can belong to many Workspaces via workspace_members (M:M)
  - workspace_members.role: owner | admin | builder | viewer | agency
  - workspace_members.status: pending | active
  - Owners are auto-inserted as active members at workspace creation
  - The workspace_id FK on all resource tables (agents, connectors, runs, etc.)
    is unchanged — all existing data stays scoped correctly
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkspaceRole(str, PyEnum):
    OWNER   = "owner"
    ADMIN   = "admin"
    BUILDER = "builder"
    VIEWER  = "viewer"
    AGENCY  = "agency"


class WorkspaceMemberStatus(str, PyEnum):
    PENDING = "pending"
    ACTIVE  = "active"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Workspaces this user OWNS (kept for backwards compat + cascade delete)
    workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace", back_populates="owner", cascade="all, delete-orphan",
        foreign_keys="Workspace.owner_id",
    )

    # All workspace memberships (owned + invited)
    memberships: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="user",
        foreign_keys="WorkspaceMember.user_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional display name for white-label overrides (Phase 9d)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    spend_cap_usd_cents: Mapped[int] = mapped_column(default=5000, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="workspaces", foreign_keys=[owner_id]
    )
    members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan",
        foreign_keys="WorkspaceMember.workspace_id",
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} slug={self.slug}>"


class WorkspaceMember(Base):
    """
    Junction table: which users belong to which workspaces and in what role.

    Composite PK: (workspace_id, user_id) — a user can hold exactly one role
    per workspace.  Pending invites have status='pending'; accepted = 'active'.
    """
    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(WorkspaceRole, name="workspacerole"),
        nullable=False,
        default=WorkspaceRole.VIEWER,
    )
    status: Mapped[WorkspaceMemberStatus] = mapped_column(
        SAEnum(WorkspaceMemberStatus, name="workspacememberstatus"),
        nullable=False,
        default=WorkspaceMemberStatus.ACTIVE,
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace", back_populates="members",
        foreign_keys=[workspace_id],
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="memberships",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return (
            f"<WorkspaceMember workspace={self.workspace_id} "
            f"user={self.user_id} role={self.role} status={self.status}>"
        )
