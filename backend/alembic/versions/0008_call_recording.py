"""add recording columns to call_logs

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "call_logs",
        sa.Column("recording_sid", sa.String(100), nullable=True),
    )
    op.add_column(
        "call_logs",
        sa.Column("recording_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("call_logs", "recording_url")
    op.drop_column("call_logs", "recording_sid")
