"""add_resumes_and_resume_experiences

Revision ID: add_resumes_and_resume_experiences
Revises: 165f8f67bc70
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a1b2c3d4e5f6"
down_revision = "165f8f67bc70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("file_id", UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("parse_status", sa.String(50), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("structured_summary", JSONB, nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(100), nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "resume_experiences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("resume_id", UUID(as_uuid=True), sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("experience_type", sa.String(50), nullable=False),
        sa.Column("company_or_project", sa.String(255), nullable=True),
        sa.Column("role_title", sa.String(255), nullable=True),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tech_stack", JSONB, nullable=True),
        sa.Column("extracted_keywords", JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("resume_experiences")
    op.drop_table("resumes")
