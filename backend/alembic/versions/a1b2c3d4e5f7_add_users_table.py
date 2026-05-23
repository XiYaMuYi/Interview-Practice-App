"""add users table

Revision ID: a1b2c3d4e5f7
Revises: 8675172568af
Create Date: 2026-05-23
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f7"
down_revision = "8675172568af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column("username", sa.String(length=100), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(length=255), unique=True, nullable=True, index=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
    )


def downgrade() -> None:
    op.drop_table("users")
