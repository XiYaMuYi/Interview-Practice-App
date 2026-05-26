# Batch 1: 模型补 user_id + Alembic 迁移

## 背景
Phase 1 认证已完成。Phase 2 要做数据隔离。第一批只改模型和迁移。

## 必读
1. `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
2. `backend/app/domain/models/__init__.py` — 所有现有 SQLModel 实体

## 任务

### 1. File 模型加 user_id

打开 `backend/app/domain/models/__init__.py`，找到 `class File(SQLModel, table=True)` 类，添加字段：

```python
user_id: str | None = Field(default=None, max_length=255)
```

放在 `id` 之后、`file_name` 之前。

### 2. ExamAnswer 模型加 user_id

在同一文件中找到 `class ExamAnswer(SQLModel, table=True)`，添加：

```python
user_id: str | None = Field(default=None, max_length=255)
```

放在 `id` 之后。

### 3. Alembic 迁移

新建文件：`backend/alembic/versions/g1h2i3j4k5l6_add_user_id_to_files_exam_answers.py`

```python
"""add user_id to files and exam_answers

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等：检查列是否存在
    conn = op.get_bind()

    # files.user_id
    has_files_user_id = conn.execute(sa.text("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_name='files' AND column_name='user_id'
        )
    """)).scalar()
    if not has_files_user_id:
        op.add_column('files', sa.Column('user_id', sa.String(length=255), nullable=True))

    # exam_answers.user_id
    has_exam_answers_user_id = conn.execute(sa.text("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_name='exam_answers' AND column_name='user_id'
        )
    """)).scalar()
    if not has_exam_answers_user_id:
        op.add_column('exam_answers', sa.Column('user_id', sa.String(length=255), nullable=True))

    # 幂等索引
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_files_user_id ON files (user_id)
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_exam_answers_user_id ON exam_answers (user_id)
    """))


def downgrade() -> None:
    op.drop_index('ix_exam_answers_user_id', table_name='exam_answers')
    op.drop_index('ix_files_user_id', table_name='files')
    op.drop_column('exam_answers', 'user_id')
    op.drop_column('files', 'user_id')
```

## 完成标准
- `File` 和 `ExamAnswer` 有 `user_id` 字段
- 迁移文件创建完成
- 不需要改 service/route，不需要 docker 重建
