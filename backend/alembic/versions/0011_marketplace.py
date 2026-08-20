"""create marketplace_listings table

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-28

Marketplace listings are GLOBAL (not workspace-scoped).
A listing's config_payload is credential-free and workspace-agnostic.

listing_status:
  draft     — author is editing, not yet submitted
  pending   — submitted for review, not yet approved
  approved  — visible in public catalog
  rejected  — rejected by reviewer with note

listing_type:
  agent     — instantiates an Agent in the user's workspace
  connector — instantiates a Connector config (no credentials) in the user's workspace
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE listingstatus AS ENUM ('draft', 'pending', 'approved', 'rejected')"
    )
    op.execute(
        "CREATE TYPE listingtype AS ENUM ('agent', 'connector')"
    )

    op.create_table(
        "marketplace_listings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        # author — NULL means ForgeBoard first-party
        sa.Column(
            "author_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("author_name", sa.String(255), nullable=False, server_default="ForgeBoard"),
        sa.Column(
            "listing_type",
            sa.Enum("agent", "connector", name="listingtype", create_type=False),
            nullable=False,
            server_default="agent",
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "pending", "approved", "rejected", name="listingstatus", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        # Versioned config payload — credential-free, workspace-agnostic JSON
        sa.Column("config_payload", JSONB, nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        # Screenshot / preview image URL
        sa.Column("preview_image_url", sa.Text(), nullable=True),
        # Counters
        sa.Column("install_count", sa.Integer(), nullable=False, server_default="0"),
        # Review fields
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_marketplace_listings_status", "marketplace_listings", ["status"]
    )
    op.create_index(
        "ix_marketplace_listings_category", "marketplace_listings", ["category"]
    )
    op.create_index(
        "ix_marketplace_listings_author_user_id",
        "marketplace_listings",
        ["author_user_id"],
    )
    op.create_index(
        "ix_marketplace_listings_install_count",
        "marketplace_listings",
        ["install_count"],
    )


def downgrade() -> None:
    op.drop_table("marketplace_listings")
    op.execute("DROP TYPE listingstatus")
    op.execute("DROP TYPE listingtype")
