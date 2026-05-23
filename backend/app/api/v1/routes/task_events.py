"""Task SSE events endpoint."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.services.task_manager import TaskManager, sse_event_stream

router = APIRouter()


@router.get("/{task_id}/events")
async def task_events(
    task_id: UUID,
    session: DbSession,
):
    """SSE endpoint for real-time task progress updates."""
    task_manager = TaskManager(session)
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        sse_event_stream(task_manager, str(task_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
