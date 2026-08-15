"""add white-label branding fields to workspaces

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-28

Adds per-workspace branding:
  managed_by_agency_id  — FK to users.id (the agency user who manages this workspace)
  brand_logo_url        — URL to the agency's logo (hosted externally or via CDN)
  brand_primary_color   — CSS hex colour, e.g. "#6366f1"
  brand_app_name        — Override for "ForgeBoard" in the UI, e.g. "Acme Agents"

All nullable — if NULL the platform defaults apply.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "managed_by_agency_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_workspaces_managed_by_agency_id",
        "workspaces",
        ["managed_by_agency_id"],
    )
    op.add_column(
        "workspaces",
        sa.Column("brand_logo_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column("brand_primary_color", sa.String(7), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column("brand_app_name", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "brand_app_name")
    op.drop_column("workspaces", "brand_primary_color")
    op.drop_column("workspaces", "brand_logo_url")
    op.drop_index("ix_workspaces_managed_by_agency_id", table_name="workspaces")
    op.drop_column("workspaces", "managed_by_agency_id")
