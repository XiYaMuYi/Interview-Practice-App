"""Event audit storage for event backend fallback and analytics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import EventAuditLog
from app.infra.repositories.base import BaseRepository


class EventAuditRepository(BaseRepository[EventAuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(EventAuditLog, session)


async def persist_event_audit(
    session: AsyncSession,
    *,
    event_type: str,
    backend: str,
    payload: dict[str, Any],
    task_id: str | UUID | None = None,
    session_id: str | None = None,
    source: str | None = None,
    status: str = "ok",
) -> EventAuditLog:
    repo = EventAuditRepository(session)
    audit = EventAuditLog(
        event_type=event_type,
        backend=backend,
        task_id=UUID(str(task_id)) if task_id else None,
        session_id=session_id,
        source=source,
        status=status,
        payload=payload,
    )
    return await repo.create(audit)
