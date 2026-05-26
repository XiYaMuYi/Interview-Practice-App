"""Task Manager - manages async task lifecycle and SSE event distribution."""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.models import Task
from app.infra.cache.cache_service import TTL_TASK_STATUS, get_cache, set_cache
from app.infra.events.event_publisher import event_publisher
from app.infra.events.event_types import TASK_CREATED, TASK_DONE, TASK_FAILED, TASK_STARTED

logger = get_logger(__name__)


def _task_status_key(task_id: str) -> str:
    return f"app:task:status:{task_id}"


class TaskManager:
    """Manage background tasks and SSE event streaming."""

    # Class-level shared state — all instances share the same subscriber queues
    # so events published by one instance reach subscribers of any instance.
    _subscribers: dict[str, list[asyncio.Queue]] = {}
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, task_type: str, source_id: str | None = None) -> Task:
        """Create a new task record."""
        task = Task(
            id=uuid4(),
            task_type=task_type,
            source_id=source_id,
            status="pending",
            progress=0.0,
            retry_count=0,
        )
        self.session.add(task)
        await self.session.flush()
        logger.info(f"Task created: {task.id} type={task_type} source={source_id}")

        payload = {
            "task_id": str(task.id),
            "task_type": task_type,
            "source_id": source_id,
        }

        # Cache a compact task snapshot so local Redis does not store oversized objects.
        try:
            await set_cache(
                _task_status_key(str(task.id)),
                {
                    "task_id": str(task.id),
                    "task_type": task.task_type,
                    "status": task.status,
                    "progress": task.progress,
                    "current_phase": task.current_phase,
                    "total_chunks": task.total_chunks,
                    "processed_chunks": task.processed_chunks,
                    "error_message": task.error_message,
                    "extra_data": task.extra_data,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                },
                ttl=TTL_TASK_STATUS,
            )
        except Exception:
            pass

        # Publish event
        try:
            await event_publisher.publish(TASK_CREATED, payload)
        except Exception:
            pass  # Graceful fallback

        return task

    async def update_task(
        self,
        task_id: UUID,
        *,
        status: str | None = None,
        progress: float | None = None,
        current_phase: str | None = None,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        error_message: str | None = None,
        extra_data: dict | None = None,
    ) -> Task | None:
        """Update task fields and notify subscribers."""
        stmt = select(Task).where(Task.id == task_id)
        result = await self.session.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            return None

        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if current_phase is not None:
            task.current_phase = current_phase
        if total_chunks is not None:
            task.total_chunks = total_chunks
        if processed_chunks is not None:
            task.processed_chunks = processed_chunks
        if error_message is not None:
            task.error_message = error_message
        if extra_data is not None:
            task.extra_data = extra_data
        task.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.commit()

        # Write a compact task snapshot to Redis (TTL 10min).
        # Keep the payload small so local Redis memory stays within safe bounds.
        try:
            await set_cache(
                _task_status_key(str(task_id)),
                {
                    "id": str(task_id),
                    "task_id": str(task_id),
                    "task_type": task.task_type,
                    "status": task.status,
                    "progress": task.progress,
                    "current_phase": task.current_phase,
                    "total_chunks": task.total_chunks,
                    "processed_chunks": task.processed_chunks,
                    "error_message": task.error_message,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                },
                ttl=TTL_TASK_STATUS,
            )
        except Exception:
            pass  # Graceful fallback

        # Publish task lifecycle events
        try:
            if status == "processing" or status == "running":
                await event_publisher.publish(TASK_STARTED, {
                    "task_id": str(task_id),
                    "status": task.status,
                    "progress": task.progress,
                })
            elif status == "done":
                await event_publisher.publish(TASK_DONE, {
                    "task_id": str(task_id),
                    "status": "done",
                    "progress": task.progress,
                })
            elif status == "failed":
                await event_publisher.publish(TASK_FAILED, {
                    "task_id": str(task_id),
                    "status": "failed",
                    "error_message": task.error_message,
                })
        except Exception:
            pass  # Graceful fallback

        # Notify SSE subscribers
        await self._notify_subscribers(str(task_id), {
            "task_id": str(task_id),
            "status": task.status,
            "progress": task.progress,
            "current_phase": task.current_phase,
            "total_chunks": task.total_chunks,
            "processed_chunks": task.processed_chunks,
        })

        return task

    async def get_task(self, task_id: UUID) -> Task | None:
        """Get a task by ID. Check Redis cache first."""
        # Try Redis cache first
        cached = await get_cache(_task_status_key(str(task_id)))
        if cached is not None:
            return Task(**cached)

        # Fall back to database
        stmt = select(Task).where(Task.id == task_id)
        result = await self.session.execute(stmt)
        task = result.scalar_one_or_none()
        if task:
            # Populate Redis for next time with a compact snapshot only.
            try:
                await set_cache(
                    _task_status_key(str(task_id)),
                    {
                        "id": str(task.id),
                        "task_type": task.task_type,
                        "source_id": task.source_id,
                        "status": task.status,
                        "progress": task.progress,
                        "current_phase": task.current_phase,
                        "total_chunks": task.total_chunks,
                        "processed_chunks": task.processed_chunks,
                        "error_message": task.error_message,
                        "retry_count": task.retry_count,
                        "extra_data": task.extra_data,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    },
                    ttl=TTL_TASK_STATUS,
                )
            except Exception:
                pass
        return task

    async def subscribe(self, task_id: str) -> asyncio.Queue:
        """Subscribe to SSE events for a task."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(queue)
        return queue

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        """Unsubscribe from SSE events."""
        async with self._lock:
            if task_id in self._subscribers:
                self._subscribers[task_id] = [
                    q for q in self._subscribers[task_id] if q is not queue
                ]
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

    async def publish_task_event(self, task_id: str, event: dict):
        """Publish a task event to all SSE subscribers.

        Unlike ``update_task()`` (which only publishes task status snapshots),
        this method pushes *arbitrary* SSE events — such as ``token``,
        ``content``, ``chunk_saved``, etc. — to every subscriber queue so
        that both the direct StreamingResponse consumer and the GET
        ``/tasks/{task_id}/events`` endpoint receive the same event stream.
        """
        if "event_type" not in event:
            if "token" in event:
                event["event_type"] = "token"
            elif "content" in event:
                event["event_type"] = "content"
            elif "error" in event:
                event["event_type"] = "error"
            elif event.get("status") == "done":
                event["event_type"] = "done"
            elif "evaluation" in event or {"score", "feedback"}.issubset(event):
                event["event_type"] = "evaluation"
            elif "summary" in event:
                event["event_type"] = "summary"
            elif "followup_question" in event:
                event["event_type"] = "followup"
            elif "recommendations" in event:
                event["event_type"] = "recommendations"
            else:
                event["event_type"] = "progress"

        async with self._lock:
            subscribers = list(self._subscribers.get(task_id, []))
        for queue in subscribers:
            await queue.put(event)

    async def _notify_subscribers(self, task_id: str, event: dict):
        """Push event to all subscribers of a task."""
        async with self._lock:
            subscribers = self._subscribers.get(task_id, [])
        for queue in subscribers:
            await queue.put(event)


async def sse_event_stream(task_manager: TaskManager, task_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a task."""
    queue = await task_manager.subscribe(task_id)

    async def emit_db_snapshot():
        task = await task_manager.get_task(UUID(task_id))
        if not task:
            return

        snapshot = {
            "event_type": "progress",
            "task_id": task_id,
            "status": task.status,
            "progress": task.progress,
            "current_phase": task.current_phase,
            "total_chunks": task.total_chunks,
            "processed_chunks": task.processed_chunks,
            "error_message": task.error_message,
        }
        if task.extra_data:
            snapshot.update(task.extra_data)
        yield f"event: progress\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"

        if task.status == "done":
            if task.extra_data and task.extra_data.get("content"):
                content_event = {
                    "event_type": "content",
                    "task_id": task_id,
                    "content": task.extra_data["content"],
                    **({"depth": task.extra_data["depth"]} if task.extra_data.get("depth") else {}),
                }
                yield f"event: content\ndata: {json.dumps(content_event, ensure_ascii=False)}\n\n"
            done_event = {"event_type": "done", "task_id": task_id, "status": "done", "progress": 1.0}
            if task.extra_data:
                done_event.update(task.extra_data)
            yield f"event: done\ndata: {json.dumps(done_event, ensure_ascii=False)}\n\n"
            return

        if task.status == "failed":
            error_event = {
                "event_type": "error",
                "task_id": task_id,
                "status": "failed",
                "error": task.error_message or "Task failed",
                "recoverable": False,
            }
            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            return

    try:
        try:
            async for snapshot_event in emit_db_snapshot():
                yield snapshot_event
                if snapshot_event.startswith("event: done") or snapshot_event.startswith("event: error"):
                    return
        except Exception:
            logger.exception("Failed to emit initial SSE task snapshot")

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2)
            except asyncio.TimeoutError:
                try:
                    async for snapshot_event in emit_db_snapshot():
                        yield snapshot_event
                        if snapshot_event.startswith("event: done") or snapshot_event.startswith("event: error"):
                            return
                except Exception:
                    logger.exception("Failed to emit polling SSE task snapshot")
                heartbeat = {"event_type": "heartbeat", "task_id": task_id}
                yield f"event: heartbeat\ndata: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"
                continue
            event_type = event.get("event_type", "progress")
            data = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        await task_manager.unsubscribe(task_id, queue)
