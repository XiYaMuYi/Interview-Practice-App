"""Generic async repository base."""

from typing import Any, Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

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
