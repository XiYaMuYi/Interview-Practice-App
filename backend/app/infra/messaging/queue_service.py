"""Queue service — RabbitMQ queue operations with pre-defined queues."""

import json
import logging
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.infra.messaging.rabbit_client import rabbit_client

logger = logging.getLogger(f"interview_practice.{__name__}")

# ── Pre-defined Queues ────────────────────────────────────────────────

QUEUE_RESUME_PARSE = "resume_parse"
QUEUE_IMPORT_EXTRACT = "import_extract"
QUEUE_QUESTION_BATCH_GENERATE = "question_batch_generate"
QUEUE_REVIEW_GENERATE = "review_generate"

PREDEFINED_QUEUES = [
    QUEUE_RESUME_PARSE,
    QUEUE_IMPORT_EXTRACT,
    QUEUE_QUESTION_BATCH_GENERATE,
    QUEUE_REVIEW_GENERATE,
]


async def declare_queues() -> None:
    """Declare all pre-defined queues."""
    if not rabbit_client.connected:
        return

    import aio_pika

    conn = await rabbit_client.get_connection()
    if conn is None:
        return

    channel = await conn.channel()
    for queue_name in PREDEFINED_QUEUES:
        await channel.declare_queue(
            queue_name,
            durable=True,
            arguments={"x-message-ttl": 3600000},  # 1h default TTL
        )
        logger.info(f"Declared queue: {queue_name}")


async def publish_to_queue(
    queue_name: str,
    message: dict[str, Any],
    priority: int = 0,
    routing_key: str | None = None,
) -> bool:
    """Publish a message to a RabbitMQ queue.

    Returns False if RabbitMQ is unavailable (graceful fallback).
    """
    if not rabbit_client.connected:
        logger.debug(f"RabbitMQ not connected, skipping publish to {queue_name}")
        return False

    import aio_pika

    conn = await rabbit_client.get_connection()
    if conn is None:
        return False

    try:
        channel = await conn.channel()
        body = json.dumps(message, ensure_ascii=False).encode()
        rk = routing_key or queue_name

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=priority,
            ),
            routing_key=rk,
        )
        logger.info(f"Published to queue {queue_name}: {message.get('task_id', 'n/a')}")
        return True
    except Exception:
        logger.warning(f"Failed to publish to queue {queue_name}")
        return False


async def consume(
    queue_name: str,
    handler_fn: Callable,
    prefetch_count: int = 1,
) -> None:
    """Start consuming from a queue with the given handler.

    handler_fn receives the parsed message dict and should call ack/nack.
    """
    if not rabbit_client.connected:
        logger.warning(f"RabbitMQ not connected, cannot consume from {queue_name}")
        return

    import aio_pika

    conn = await rabbit_client.get_connection()
    if conn is None:
        return

    channel = await conn.channel()
    await channel.set_qos(prefetch_count=prefetch_count)

    queue = await channel.declare_queue(queue_name, durable=True)

    async def _on_message(message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                body = json.loads(message.body.decode())
                await handler_fn(body, message)
            except Exception:
                logger.exception(f"Handler failed for queue {queue_name}")
                await message.nack(requeue=True)

    await queue.consume(_on_message)
    logger.info(f"Consuming from queue: {queue_name}")
