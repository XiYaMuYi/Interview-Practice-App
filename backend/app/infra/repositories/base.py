"""Generic async repository base."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

if TYPE_CHECKING:
    from app.domain.models import (
        ChatHistory,
        File,
        KnowledgeNode,
        LearningProfile,
        PromptVersion,
        Question,
        QuestionEmbedding,
        StudyRecord,
        Tag,
    )

ModelT = TypeVar("ModelT", bound=SQLModel)


class BaseRepository(Generic[ModelT]):
    """Minimal async CRUD over SQLModel entities."""

    def __init__(self, model: type[ModelT], session: SQLModelAsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: UUID) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> Sequence[ModelT]:
        stmt = select(self.model).offset(offset).limit(limit)
        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.exec(stmt)
        rows = result.all()
        # SQLModel returns either model instances directly or BaseRow wrappers
        out: list[ModelT] = []
        for row in rows:
            if isinstance(row, self.model):
                out.append(row)
            elif hasattr(row, "_mapping"):
                mapping = dict(row._mapping)
                # Single-column row: the value might already be the model
                if len(mapping) == 1:
                    val = next(iter(mapping.values()))
                    if isinstance(val, self.model):
                        out.append(val)
                        continue
                out.append(self.model.model_validate(mapping))
            else:
                out.append(row)
        return out

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.exec(stmt)
        return result.one()

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        # UUIDs are client-side generated (default_factory=uuid4),
        # so obj.id is already set after flush — no need to re-fetch.
        return obj

    async def update(self, id: UUID, updates: dict[str, Any]) -> ModelT | None:
        obj = await self.get_by_id(id)
        if obj is None:
            return None
        for key, value in updates.items():
            setattr(obj, key, value)
        await self.session.flush()
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def soft_delete(self, id: UUID) -> bool:
        """Soft-delete by setting deleted_at timestamp.

        Only works for models that have a deleted_at column.
        Returns False if the model doesn't support soft-delete or object not found.
        """
        from datetime import datetime

        obj = await self.get_by_id(id)
        if obj is None:
            return False
        if not hasattr(obj, "deleted_at"):
            return False
        obj.deleted_at = datetime.utcnow()
        await self.session.flush()
        return True


# ── Domain-specific repositories ────────────────────────────────────


class QuestionRepository(BaseRepository["Question"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import Question as QuestionModel
        super().__init__(QuestionModel, session)

    async def search(
        self,
        *,
        query: str | None = None,
        domain_type: str | None = None,
        question_type: str | None = None,
        difficulty_level: int | None = None,
        source_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Question]:
        from sqlalchemy import or_

        stmt = select(self.model).where(self.model.deleted_at.is_(None))
        if query:
            stmt = stmt.where(
                or_(
                    self.model.title.ilike(f"%{query}%"),
                    self.model.content.ilike(f"%{query}%"),
                )
            )
        if domain_type:
            stmt = stmt.where(self.model.domain_type == domain_type)
        if question_type:
            stmt = stmt.where(self.model.question_type == question_type)
        if difficulty_level is not None:
            stmt = stmt.where(self.model.difficulty_level == difficulty_level)
        if source_type:
            stmt = stmt.where(self.model.source_type == source_type)
        stmt = stmt.offset(offset).limit(limit).order_by(self.model.created_at.desc())
        result = await self.session.exec(stmt)
        rows = result.all()
        out: list[Question] = []
        for row in rows:
            if isinstance(row, self.model):
                out.append(row)
            elif hasattr(row, "_mapping"):
                mapping = dict(row._mapping)
                if len(mapping) == 1:
                    val = next(iter(mapping.values()))
                    if isinstance(val, self.model):
                        out.append(val)
                        continue
                out.append(self.model.model_validate(mapping))
            else:
                out.append(row)
        return out

    async def search_with_count(
        self,
        *,
        user_id: str | None = None,
        query: str | None = None,
        domain_type: str | None = None,
        question_type: str | None = None,
        difficulty_level: int | None = None,
        source_type: str | None = None,
        source_ref: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Question], int]:
        """Return (items, total_count) with a separate COUNT query."""
        from sqlalchemy import or_, func

        # Build the base filter conditions
        conditions = [self.model.deleted_at.is_(None)]
        if user_id is not None:
            conditions.append(self.model.user_id == user_id)
        if query:
            conditions.append(
                or_(
                    self.model.title.ilike(f"%{query}%"),
                    self.model.content.ilike(f"%{query}%"),
                )
            )
        if domain_type:
            conditions.append(self.model.domain_type == domain_type)
        if question_type:
            conditions.append(self.model.question_type == question_type)
        if difficulty_level is not None:
            conditions.append(self.model.difficulty_level == difficulty_level)
        if source_type:
            conditions.append(self.model.source_type == source_type)
        if source_ref:
            conditions.append(self.model.source_ref == source_ref)

        # Count query
        count_stmt = select(func.count()).select_from(self.model).where(*conditions)
        total = (await self.session.exec(count_stmt)).scalar_one()

        # Data query
        data_stmt = select(self.model).where(*conditions)
        data_stmt = data_stmt.offset(offset).limit(limit).order_by(self.model.created_at.desc())
        result = await self.session.exec(data_stmt)
        rows = result.all()
        out: list[Question] = []
        for row in rows:
            if isinstance(row, self.model):
                out.append(row)
            elif hasattr(row, "_mapping"):
                mapping = dict(row._mapping)
                if len(mapping) == 1:
                    val = next(iter(mapping.values()))
                    if isinstance(val, self.model):
                        out.append(val)
                        continue
                out.append(self.model.model_validate(mapping))
            else:
                out.append(row)
        return out, total


class TagRepository(BaseRepository["Tag"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import Tag as TagModel
        super().__init__(TagModel, session)

    async def get_by_name(self, name: str) -> Tag | None:
        stmt = select(self.model).where(self.model.name == name)
        result = await self.session.exec(stmt)
        return result.first()


class KnowledgeNodeRepository(BaseRepository["KnowledgeNode"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import KnowledgeNode as KnowledgeNodeModel
        super().__init__(KnowledgeNodeModel, session)


class StudyRecordRepository(BaseRepository["StudyRecord"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import StudyRecord as StudyRecordModel
        super().__init__(StudyRecordModel, session)

    async def list_with_count(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> tuple[Sequence["StudyRecord"], int]:
        """Return (items, total_count) with a separate COUNT query."""
        from sqlalchemy import func

        count_stmt = select(func.count()).select_from(self.model)
        data_stmt = select(self.model)

        if filters:
            for key, value in filters.items():
                count_stmt = count_stmt.where(getattr(self.model, key) == value)
                data_stmt = data_stmt.where(getattr(self.model, key) == value)

        total = (await self.session.exec(count_stmt)).scalar_one()
        data_stmt = data_stmt.offset(offset).limit(limit).order_by(self.model.created_at.desc())
        result = await self.session.exec(data_stmt)
        return list(result.scalars().all()), total


class ChatHistoryRepository(BaseRepository["ChatHistory"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import ChatHistory as ChatHistoryModel
        super().__init__(ChatHistoryModel, session)

    async def get_by_session(self, session_id: str) -> Sequence[ChatHistory]:
        stmt = (
            select(self.model)
            .where(self.model.session_id == session_id)
            .order_by(self.model.created_at.asc())
        )
        result = await self.session.exec(stmt)
        return result.all()


class FileRepository(BaseRepository["File"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import File as FileModel
        super().__init__(FileModel, session)

    async def get_by_hash(self, file_hash: str) -> File | None:
        stmt = select(self.model).where(self.model.file_hash == file_hash)
        result = await self.session.exec(stmt)
        return result.scalars().first()


class QuestionEmbeddingRepository(BaseRepository["QuestionEmbedding"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import QuestionEmbedding as QuestionEmbeddingModel
        super().__init__(QuestionEmbeddingModel, session)


class LearningProfileRepository(BaseRepository["LearningProfile"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import LearningProfile as LearningProfileModel
        super().__init__(LearningProfileModel, session)


class PromptVersionRepository(BaseRepository["PromptVersion"]):
    def __init__(self, session: SQLModelAsyncSession):
        from app.domain.models import PromptVersion as PromptVersionModel
        super().__init__(PromptVersionModel, session)
