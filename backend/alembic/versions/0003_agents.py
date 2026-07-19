"""create agents and agent_connectors tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE agentstatus AS ENUM "
        "('draft', 'testing', 'live', 'paused', 'needs_review')"
    )
    op.execute(
        "CREATE TYPE triggertype AS ENUM "
        "('manual', 'scheduled', 'webhook')"
    )

    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "testing", "live", "paused", "needs_review",
                name="agentstatus", create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "manual", "scheduled", "webhook",
                name="triggertype", create_type=False,
            ),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("cron_schedule", sa.String(100), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("agent_config_json", sa.Text(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("total_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    op.create_index("ix_agents_status", "agents", ["status"])

    op.create_table(
        "agent_connectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connector_id",
            UUID(as_uuid=True),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_connectors_agent_id", "agent_connectors", ["agent_id"])


def downgrade() -> None:
    op.drop_table("agent_connectors")
    op.drop_table("agents")
    op.execute("DROP TYPE triggertype")
    op.execute("DROP TYPE agentstatus")
