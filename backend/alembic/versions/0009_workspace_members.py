"""add workspace_members table and workspace metadata fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-28

Changes:
  - Creates workspace_members table (workspace_id, user_id composite PK)
    with role enum (owner|admin|builder|viewer|agency) and status enum
    (pending|active). This table is the single source of truth for who
    belongs to which workspace and in what capacity.
  - Back-fills workspace_members for all existing (workspace, owner) pairs
    so the database is consistent immediately after migration.
  - Adds workspace.display_name (nullable) for white-label use (Phase 9d).
  - No existing rows are moved or deleted — fully additive migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # New ENUMs
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE workspacerole AS ENUM "
        "('owner', 'admin', 'builder', 'viewer', 'agency')"
    )
    op.execute(
        "CREATE TYPE workspacememberstatus AS ENUM ('pending', 'active')"
    )

    # ------------------------------------------------------------------
    # workspace_members
    # ------------------------------------------------------------------
    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum(
                "owner", "admin", "builder", "viewer", "agency",
                name="workspacerole",
                create_type=False,
            ),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "active",
                name="workspacememberstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        # Who sent the invite (NULL for the founding owner)
        sa.Column(
            "invited_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
    )
    op.create_index(
        "ix_workspace_members_user_id", "workspace_members", ["user_id"]
    )
    op.create_index(
        "ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"]
    )

    # ------------------------------------------------------------------
    # Back-fill existing owners as active 'owner' members
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO workspace_members (workspace_id, user_id, role, status, joined_at, created_at)
        SELECT id, owner_id, 'owner', 'active', created_at, now()
        FROM workspaces
        ON CONFLICT DO NOTHING
        """
    )

    # ------------------------------------------------------------------
    # Add display_name to workspaces (used by Phase 9d white-label)
    # ------------------------------------------------------------------
    op.add_column(
        "workspaces",
        sa.Column("display_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "display_name")
    op.drop_table("workspace_members")
    op.execute("DROP TYPE workspacememberstatus")
    op.execute("DROP TYPE workspacerole")
