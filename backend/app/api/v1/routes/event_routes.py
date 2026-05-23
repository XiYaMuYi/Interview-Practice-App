"""Event analytics routes."""

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.infra.repositories.base import BaseRepository
from app.domain.models import EventAuditLog

router = APIRouter()


@router.get("/audit")
async def list_event_audit(
    session: DbSession,
    event_type: str | None = Query(default=None),
    backend: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    repo = BaseRepository(EventAuditLog, session)
    filters = {}
    if event_type:
        filters["event_type"] = event_type
    if backend:
        filters["backend"] = backend
    if status:
        filters["status"] = status
    rows = await repo.list(limit=limit, filters=filters or None)
    return {
        "items": [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "backend": row.backend,
                "task_id": str(row.task_id) if row.task_id else None,
                "session_id": row.session_id,
                "source": row.source,
                "status": row.status,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "total": len(rows),
    }
