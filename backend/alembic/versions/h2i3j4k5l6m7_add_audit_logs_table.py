"""add audit_logs table for security audit logging (Phase 6)

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-25

Idempotent: checks for existing table before creating.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Create audit_logs table ─────────────────────────────────────────
    table_exists = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='audit_logs'"
        )
    ).scalar()
    if not table_exists:
        op.create_table(
            "audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("actor_username", sa.String(100), nullable=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("target_type", sa.String(50), nullable=True),
            sa.Column("target_id", sa.String(100), nullable=True),
            sa.Column("detail", sa.String(1000), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    # ── Add indexes ─────────────────────────────────────────────────────
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_action "
            "ON audit_logs(action)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_id "
            "ON audit_logs(actor_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at "
            "ON audit_logs(created_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_target "
            "ON audit_logs(target_type, target_id)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
