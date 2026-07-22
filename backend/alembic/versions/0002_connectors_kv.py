"""create connectors and kv_entries tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "connector_type",
            sa.Enum(
                "http_webhook", "google_calendar", "gmail", "kv_store",
                name="connectortype"
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "connected", "disconnected", "error", "pending_auth",
                name="connectorstatus"
            ),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
    op.create_index("ix_connectors_workspace_id", "connectors", ["workspace_id"])

    op.create_table(
        "kv_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("workspace_id", "key", name="uq_kv_workspace_key"),
    )
    op.create_index("ix_kv_entries_workspace_id", "kv_entries", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("kv_entries")
    op.drop_table("connectors")
    op.execute("DROP TYPE connectorstatus")
    op.execute("DROP TYPE connectortype")
