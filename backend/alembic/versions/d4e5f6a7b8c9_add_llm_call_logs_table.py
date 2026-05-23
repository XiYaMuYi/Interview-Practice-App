"""add llm_call_logs table

Revision ID: d4e5f6a7b8c9
Revises: 7c158c13231f
Create Date: 2026-05-10 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "7c158c13231f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("prompt_key", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("prompt_version", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("model_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("request_preview", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False, server_default=""),
        sa.Column("response_preview", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("error_code", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("llm_call_logs")
