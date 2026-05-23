"""Background queue workers for RabbitMQ-driven tasks."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.infra.db.session import async_session
from app.infra.messaging.queue_service import (
    QUEUE_IMPORT_EXTRACT,
    QUEUE_RESUME_PARSE,
    consume,
)
from app.services.import_service import ImportService
from app.services.resume_service import ResumeService


async def _handle_resume_parse(message: dict[str, Any], incoming_message: Any) -> None:
    resume_id = message.get("resume_id")
    task_id = message.get("task_id")
    if not resume_id or not task_id:
        return
    async with async_session() as session:
        service = ResumeService(session)
        await service.parse_resume_background(UUID(str(resume_id)))
        await session.commit()


async def _handle_import_extract(message: dict[str, Any], incoming_message: Any) -> None:
    text = message.get("text")
    source_type = message.get("source_type", "paste")
    if not text:
        return
    async with async_session() as session:
        service = ImportService(session)
        await service.import_text(text, source_type=source_type)
        await session.commit()


async def start_queue_workers() -> None:
    """Start RabbitMQ consumers for queue-backed workflows."""
    await asyncio.gather(
        consume(QUEUE_RESUME_PARSE, _handle_resume_parse, prefetch_count=1),
        consume(QUEUE_IMPORT_EXTRACT, _handle_import_extract, prefetch_count=1),
    )
