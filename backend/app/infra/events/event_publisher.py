"""Event publisher — abstract interface, Kafka implementation, and in-memory fallback."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.db.session import async_session
from app.infra.events.event_store import persist_event_audit
from app.infra.events.event_types import (
    CACHE_HIT,
    CACHE_MISS,
    CHUNK_PROCESSED,
    FOLLOWUP_GENERATED,
    LLM_CALL_FAILED,
    LLM_CALL_SUCCESS,
    QUESTION_GENERATED,
    TASK_CREATED,
    TASK_DONE,
    TASK_FAILED,
    TASK_STARTED,
)

logger = get_logger(__name__)


class EventPublisher(ABC):
    """Abstract event publisher interface."""

    @abstractmethod
    async def publish(self, event_type: str, payload: dict[str, Any]) -> bool:
        """Publish an event. Returns False if publishing failed."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...


class InMemoryEventPublisher(EventPublisher):
    """In-memory event publisher for MVP.

    Events are written to an in-memory log that can be inspected during development.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._log: list[dict] = []
        self._max_entries = max_entries

    async def connect(self) -> None:
        logger.info("InMemoryEventPublisher connected (MVP mode)")

    async def disconnect(self) -> None:
        self._log.clear()
        logger.info("InMemoryEventPublisher disconnected")

    async def publish(self, event_type: str, payload: dict[str, Any]) -> bool:
        import time

        entry = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": time.time(),
        }
        self._log.append(entry)
        if len(self._log) > self._max_entries:
            self._log = self._log[-self._max_entries:]

        logger.debug(f"[Event] {event_type}: {json.dumps(payload, ensure_ascii=False)[:200]}")

        try:
            async with async_session() as session:
                await persist_event_audit(
                    session,
                    event_type=event_type,
                    backend="inmemory",
                    payload=payload,
                    task_id=payload.get("task_id"),
                    session_id=payload.get("session_id"),
                    source=payload.get("source"),
                    status="ok",
                )
                await session.commit()
        except Exception:
            logger.debug("Failed to persist in-memory event audit")

        return True

    def get_recent(self, n: int = 50) -> list[dict]:
        """Get the most recent N events (for debugging)."""
        return self._log[-n:]


class KafkaEventPublisher(EventPublisher):
    """Kafka event publisher using aiokafka.

    Graceful fallback: if Kafka is unavailable, publishing becomes a no-op.
    """

    def __init__(self) -> None:
        self._producer = None
        self._connected = False

    async def connect(self) -> None:
        if not settings.KAFKA_ENABLED:
            logger.info("Kafka is disabled (KAFKA_ENABLED=False)")
            return

        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            )
            await self._producer.start()
            self._connected = True
            logger.info(f"Kafka connected: {settings.KAFKA_BOOTSTRAP_SERVERS}")
        except Exception:
            self._connected = False
            self._producer = None
            logger.warning("Kafka connection failed — events will be dropped")

    async def disconnect(self) -> None:
        if self._producer:
            try:
                await self._producer.stop()
            except Exception:
                pass
            self._producer = None
            self._connected = False

    async def publish(self, event_type: str, payload: dict[str, Any]) -> bool:
        if not self._connected or self._producer is None:
            return False

        try:
            topic = "interview_practice_events"
            message = {"event_type": event_type, **payload}
            await self._producer.send_and_wait(topic, value=message)

            try:
                async with async_session() as session:
                    await persist_event_audit(
                        session,
                        event_type=event_type,
                        backend="kafka",
                        payload=payload,
                        task_id=payload.get("task_id"),
                        session_id=payload.get("session_id"),
                        source=payload.get("source"),
                        status="ok",
                    )
                    await session.commit()
            except Exception:
                logger.debug("Failed to persist Kafka event audit")

            return True
        except Exception:
            logger.warning(f"Failed to publish Kafka event: {event_type}")
            try:
                async with async_session() as session:
                    await persist_event_audit(
                        session,
                        event_type=event_type,
                        backend="kafka",
                        payload=payload,
                        task_id=payload.get("task_id"),
                        session_id=payload.get("session_id"),
                        source=payload.get("source"),
                        status="failed",
                    )
                    await session.commit()
            except Exception:
                pass
            return False


# ── Singleton + Factory ──────────────────────────────────────────────

def create_event_publisher() -> EventPublisher:
    """Factory: return the configured event publisher implementation."""
    if settings.EVENT_BACKEND == "kafka":
        return KafkaEventPublisher()
    # Default to in-memory for MVP
    return InMemoryEventPublisher()


# Default publisher instance
event_publisher: EventPublisher = create_event_publisher()
