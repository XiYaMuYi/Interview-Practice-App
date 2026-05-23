"""Base Worker class — shared utilities for RabbitMQ consumers."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(f"interview_practice.{__name__}")


class BaseWorker(ABC):
    """Base class for RabbitMQ workers.

    Provides:
    - Retry logic with exponential backoff
    - Graceful shutdown handling
    - Task status tracking
    """

    def __init__(self, name: str, max_retries: int = 3) -> None:
        self.name = name
        self.max_retries = max_retries
        self._running = False

    @abstractmethod
    async def handle(self, message: dict[str, Any]) -> None:
        """Process a single message from the queue."""
        ...

    async def handle_with_retry(self, message: dict[str, Any]) -> None:
        """Process message with automatic retries."""
        task_id = message.get("task_id", "unknown")
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"[{self.name}] Processing task {task_id}, attempt {attempt}")
                await self.handle(message)
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[{self.name}] Task {task_id} attempt {attempt} failed: {e}"
                )
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.info(f"[{self.name}] Retrying in {wait}s...")
                    await asyncio.sleep(wait)

        logger.error(f"[{self.name}] Task {task_id} failed after {self.max_retries} attempts")
        raise last_error

    async def start(self) -> None:
        """Start the worker."""
        self._running = True
        logger.info(f"[{self.name}] Worker started")

    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        logger.info(f"[{self.name}] Worker stopped")
