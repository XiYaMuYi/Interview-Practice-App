"""Import extract worker — consumes from import_extract queue."""

from typing import Any

from app.core.logging import get_logger
from app.infra.db.session import async_session
from app.services.import_service import ImportService
from app.workers.base_worker import BaseWorker

logger = get_logger(__name__)


class ImportExtractWorker(BaseWorker):
    """Worker that processes text import/extraction tasks from RabbitMQ."""

    def __init__(self) -> None:
        super().__init__(name="ImportExtractWorker", max_retries=3)

    async def handle(self, message: dict[str, Any]) -> None:
        task_id = message.get("task_id")
        source_type = message.get("source_type", "paste")

        # In a full implementation, the text body would be stored in a
        # persistent store (S3, DB) and retrieved by task_id. For MVP,
        # the text is passed directly in the message.
        text = message.get("text", "")
        if not text:
            logger.warning(f"No text in import message: {message}")
            return

        async with async_session() as session:
            service = ImportService(session)
            try:
                result = await service.import_text(text, source_type=source_type)
                logger.info(
                    f"Import extracted: {result.get('questions_extracted', 0)} questions"
                )
            except Exception:
                logger.exception(f"Import extract failed for task {task_id}")
                raise
