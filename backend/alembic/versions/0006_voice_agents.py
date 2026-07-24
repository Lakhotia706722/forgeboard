"""create voice_agents and call_logs tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE voicemode AS ENUM ('inbound', 'outbound')")
    op.execute(
        "CREATE TYPE callstatus AS ENUM "
        "('idle', 'ringing', 'in_progress', 'completed', 'failed', 'transferred')"
    )

    op.create_table(
        "voice_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id", UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False, unique=True,
        ),
        sa.Column(
            "workspace_id", UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column(
            "voice_mode",
            sa.Enum("inbound", "outbound", name="voicemode", create_type=False),
            nullable=False, server_default="inbound",
        ),
        sa.Column("phone_number_sid", sa.String(50), nullable=True),
        sa.Column("tts_voice_id", sa.String(100), nullable=True),
        sa.Column("stt_language", sa.String(10), nullable=False, server_default="en-US"),
        sa.Column("max_concurrent_calls", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_call_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_escalations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_voice_agents_agent_id", "voice_agents", ["agent_id"])
    op.create_index("ix_voice_agents_workspace_id", "voice_agents", ["workspace_id"])

    op.create_table(
        "call_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "voice_agent_id", UUID(as_uuid=True),
            sa.ForeignKey("voice_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id", UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id", UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("call_sid", sa.String(100), nullable=False),
        sa.Column("from_number", sa.String(30), nullable=False),
        sa.Column("to_number", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column(
            "status",
            sa.Enum("idle", "ringing", "in_progress", "completed", "failed", "transferred",
                    name="callstatus", create_type=False),
            nullable=False, server_default="idle",
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transcript_json", sa.Text(), nullable=True),
        sa.Column("consent_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dnc_checked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ai_disclosed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_call_logs_voice_agent_id", "call_logs", ["voice_agent_id"])
    op.create_index("ix_call_logs_workspace_id", "call_logs", ["workspace_id"])
    op.create_index("ix_call_logs_call_sid", "call_logs", ["call_sid"])
    op.create_index("ix_call_logs_run_id", "call_logs", ["run_id"])


def downgrade() -> None:
    op.drop_table("call_logs")
    op.drop_table("voice_agents")
    op.execute("DROP TYPE callstatus")
    op.execute("DROP TYPE voicemode")
