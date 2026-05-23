"""add user_id to resumes and questions

Revision ID: add_user_id_to_resumes_questions
Revises: 7c158c13231f
Create Date: 2026-05-11 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'add_user_id_to_resumes_questions'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('resumes', sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('questions', sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    # Optional: add index for faster user-scoped queries
    op.create_index('ix_resumes_user_id', 'resumes', ['user_id'])
    op.create_index('ix_questions_user_id', 'questions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_questions_user_id', table_name='questions')
    op.drop_index('ix_resumes_user_id', table_name='resumes')
    op.drop_column('questions', 'user_id')
    op.drop_column('resumes', 'user_id')
