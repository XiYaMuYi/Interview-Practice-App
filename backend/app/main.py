"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for middleware initialization."""
    # ── Startup ──────────────────────────────────────────────────────
    setup_logging(debug=settings.DEBUG)
    logger.info("Starting Interview Practice App...")

    # Initialize Redis cache (only if enabled)
    if settings.REDIS_ENABLED:
        from app.infra.cache.redis_client import redis_client
        await redis_client.connect()
        logger.info("Redis cache connected")
    else:
        logger.info("Redis cache disabled (skipping)")

    # Initialize RabbitMQ (only if enabled)
    if settings.RABBITMQ_ENABLED:
        from app.infra.messaging.rabbit_client import rabbit_client
        await rabbit_client.connect()

        from app.infra.messaging.queue_service import declare_queues
        await declare_queues()

        from app.services.queue_worker_service import start_queue_workers
        import asyncio
        app.state.queue_worker_task = asyncio.create_task(start_queue_workers())
        logger.info("RabbitMQ connected, queues declared, workers started")
    else:
        logger.info("RabbitMQ disabled (skipping)")

    # Initialize event publisher (in-memory fallback when Kafka disabled)
    from app.infra.events.event_publisher import event_publisher
    await event_publisher.connect()
    if settings.EVENT_BACKEND == "inmemory":
        logger.info("Event publisher initialized (in-memory backend)")
    else:
        logger.info(f"Event publisher initialized ({settings.EVENT_BACKEND} backend)")

    logger.info("All middleware connections initialized")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down middleware connections...")

    if settings.REDIS_ENABLED:
        from app.infra.cache.redis_client import redis_client
        await redis_client.disconnect()

    if settings.RABBITMQ_ENABLED:
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

    # ── CORS ────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health endpoints at root path (no version prefix)
    from app.api.v1.routes import health_routes
    app.include_router(health_routes.router)

    # v1 API routes
    from app.api.v1 import register_routes  # noqa: F401
    register_routes(app)

    return app


app = create_app()
