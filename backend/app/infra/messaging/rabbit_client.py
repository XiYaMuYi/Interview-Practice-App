"""RabbitMQ connection manager with graceful fallback."""

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(f"interview_practice.{__name__}")

# Lazy import to avoid blocking startup when RabbitMQ is not installed.
_connection = None
_connected = False


async def _get_connection():
    global _connection, _connected
    if _connection is not None:
        return _connection

    import aio_pika

    try:
        _connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
        )
        _connected = True
        logger.info(f"RabbitMQ connected: {settings.RABBITMQ_URL}")
        return _connection
    except Exception:
        _connected = False
        _connection = None
        logger.warning("RabbitMQ connection failed — running in no-queue mode")
        return None


class RabbitMQClient:
    """RabbitMQ connection manager.

    Graceful fallback: if RabbitMQ is unavailable, all operations become no-ops.
    """

    def __init__(self) -> None:
        self._connected = False

    async def connect(self) -> None:
        if not settings.RABBITMQ_ENABLED:
            logger.info("RabbitMQ is disabled (RABBITMQ_ENABLED=False)")
            return
        conn = await _get_connection()
        if conn is not None:
            self._connected = True
        else:
            self._connected = False

    async def disconnect(self) -> None:
        global _connection, _connected
        if _connection:
            try:
                await _connection.close()
            except Exception:
                pass
            _connection = None
            _connected = False
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def get_connection(self):
        """Get the underlying aio_pika connection (or None)."""
        return await _get_connection()


# Singleton
rabbit_client = RabbitMQClient()
