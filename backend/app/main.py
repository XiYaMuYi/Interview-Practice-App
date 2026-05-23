"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for middleware initialization."""
    # ── Startup ──────────────────────────────────────────────────────
    setup_logging(debug=settings.DEBUG)
    logger.info("Starting Interview Practice App...")

    # Initialize Redis cache
    from app.infra.cache.redis_client import redis_client
    await redis_client.connect()

    # Initialize RabbitMQ
    from app.infra.messaging.rabbit_client import rabbit_client
    await rabbit_client.connect()

    # Declare RabbitMQ queues
    from app.infra.messaging.queue_service import declare_queues
    await declare_queues()

    # Initialize event publisher
    from app.infra.events.event_publisher import event_publisher
    await event_publisher.connect()

    # Start RabbitMQ queue workers when enabled
    if settings.RABBITMQ_ENABLED:
        from app.services.queue_worker_service import start_queue_workers
        import asyncio
        app.state.queue_worker_task = asyncio.create_task(start_queue_workers())
        logger.info("RabbitMQ queue workers started")

    logger.info("All middleware connections initialized")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down middleware connections...")

    from app.infra.cache.redis_client import redis_client
    await redis_client.disconnect()

    from app.infra.messaging.rabbit_client import rabbit_client
    await rabbit_client.disconnect()

    from app.infra.events.event_publisher import event_publisher
    await event_publisher.disconnect()

    queue_worker_task = getattr(app.state, "queue_worker_task", None)
    if queue_worker_task:
        queue_worker_task.cancel()
        try:
            await queue_worker_task
        except Exception:
            pass

    logger.info("Middleware connections closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        redirect_slashes=False,
        lifespan=lifespan,
    )

    # Health endpoints at root path (no version prefix)
    from app.api.v1.routes import health_routes
    app.include_router(health_routes.router)

    # v1 API routes
    from app.api.v1 import register_routes  # noqa: F401
    register_routes(app)

    return app


app = create_app()
