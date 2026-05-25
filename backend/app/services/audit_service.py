"""Audit service — writes security audit log entries."""

import uuid
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.models.audit import AuditLog


class AuditService:
    """Service for writing and querying audit logs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        action: str,
        actor_id: uuid.UUID | None = None,
        actor_username: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Write a single audit log entry."""
        entry = AuditLog(
            actor_id=actor_id,
            actor_username=actor_username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_logs(
        self,
        action: str | None = None,
        actor_id: uuid.UUID | None = None,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs with optional filters. Returns (items, total)."""
        query = select(AuditLog)
        count_query = select(AuditLog)

        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if actor_id:
            query = query.where(AuditLog.actor_id == actor_id)
            count_query = count_query.where(AuditLog.actor_id == actor_id)
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
            count_query = count_query.where(AuditLog.target_type == target_type)

        # Get total count
        count_result = await self.session.exec(count_query)
        total = len(count_result.all())

        # Get paginated results (newest first)
        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.exec(query)
        return list(result.all()), total
