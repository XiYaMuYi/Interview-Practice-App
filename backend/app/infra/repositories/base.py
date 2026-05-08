"""Generic async repository base."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

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

    def __init__(self, model: type[ModelT], session: AsyncSession):
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
        return result.all()

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
        await self.session.refresh(obj)
        return obj

    async def update(self, id: UUID, updates: dict[str, Any]) -> ModelT | None:
        obj = await self.get_by_id(id)
        if obj is None:
            return None
        for key, value in updates.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True


# ── Domain-specific repositories ────────────────────────────────────


class QuestionRepository(BaseRepository["Question"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import Question as QuestionModel
        super().__init__(QuestionModel, session)

    async def search(
        self,
        *,
        query: str | None = None,
        domain_type: str | None = None,
        question_type: str | None = None,
        difficulty_level: int | None = None,
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
        stmt = stmt.offset(offset).limit(limit).order_by(self.model.created_at.desc())
        result = await self.session.exec(stmt)
        return result.all()


class TagRepository(BaseRepository["Tag"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import Tag as TagModel
        super().__init__(TagModel, session)

    async def get_by_name(self, name: str) -> Tag | None:
        stmt = select(self.model).where(self.model.name == name)
        result = await self.session.exec(stmt)
        return result.first()


class KnowledgeNodeRepository(BaseRepository["KnowledgeNode"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import KnowledgeNode as KnowledgeNodeModel
        super().__init__(KnowledgeNodeModel, session)


class StudyRecordRepository(BaseRepository["StudyRecord"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import StudyRecord as StudyRecordModel
        super().__init__(StudyRecordModel, session)


class ChatHistoryRepository(BaseRepository["ChatHistory"]):
    def __init__(self, session: AsyncSession):
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
    def __init__(self, session: AsyncSession):
        from app.domain.models import File as FileModel
        super().__init__(FileModel, session)

    async def get_by_hash(self, file_hash: str) -> File | None:
        stmt = select(self.model).where(self.model.file_hash == file_hash)
        result = await self.session.exec(stmt)
        return result.first()


class QuestionEmbeddingRepository(BaseRepository["QuestionEmbedding"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import QuestionEmbedding as QuestionEmbeddingModel
        super().__init__(QuestionEmbeddingModel, session)


class LearningProfileRepository(BaseRepository["LearningProfile"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import LearningProfile as LearningProfileModel
        super().__init__(LearningProfileModel, session)


class PromptVersionRepository(BaseRepository["PromptVersion"]):
    def __init__(self, session: AsyncSession):
        from app.domain.models import PromptVersion as PromptVersionModel
        super().__init__(PromptVersionModel, session)
