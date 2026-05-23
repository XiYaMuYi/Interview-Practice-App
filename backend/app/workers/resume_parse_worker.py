"""Resume parse worker — consumes from resume_parse queue."""

from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.infra.db.session import async_session
from app.services.resume_service import ResumeService
from app.workers.base_worker import BaseWorker

logger = get_logger(__name__)


class ResumeParseWorker(BaseWorker):
    """Worker that processes resume parsing tasks from RabbitMQ."""

    def __init__(self) -> None:
        super().__init__(name="ResumeParseWorker", max_retries=3)

    async def handle(self, message: dict[str, Any]) -> None:
        task_id = message.get("task_id")
        resume_id = message.get("resume_id")

        if not resume_id:
            logger.error(f"No resume_id in message: {message}")
            return

        async with async_session() as session:
            service = ResumeService(session)
            try:
                result = await service.parse_resume(UUID(resume_id))
                logger.info(
                    f"Resume {resume_id} parsed: "
                    f"{result.get('experiences_count', 0)} experiences"
                )
            except Exception:
                logger.exception(f"Failed to parse resume {resume_id}")
                raise
