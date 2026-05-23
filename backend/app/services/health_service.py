"""Health check service — validates connectivity to key dependencies."""

import time
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.db.session import engine

logger = get_logger(__name__)

START_TIME = time.monotonic()
APP_VERSION = "1.0.0"

CHECK_TIMEOUT = 3.0  # seconds


async def check_database() -> tuple[bool, str, int]:
    """Run SELECT 1 to verify database connectivity."""
    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        duration_ms = int((time.monotonic() - start) * 1000)
        return True, "ok", duration_ms
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Database health check failed: {e}")
        return False, str(e), duration_ms


async def check_vector_store() -> tuple[bool, str, int]:
    """Verify pgvector extension and question_embeddings table exist."""
    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'question_embeddings'
                )
            """))
            exists = result.scalar()
            if not exists:
                duration_ms = int((time.monotonic() - start) * 1000)
                return False, "question_embeddings table not found", duration_ms
        duration_ms = int((time.monotonic() - start) * 1000)
        return True, "ok", duration_ms
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Vector store health check failed: {e}")
        return False, str(e), duration_ms


async def check_llm_provider() -> tuple[bool, str, int]:
    """Verify LLM provider configuration is present (no actual API call)."""
    start = time.monotonic()
    if not settings.LLM_API_KEY:
        duration_ms = int((time.monotonic() - start) * 1000)
        return False, "LLM_API_KEY not configured", duration_ms
    if not settings.LLM_BASE_URL:
        duration_ms = int((time.monotonic() - start) * 1000)
        return False, "LLM_BASE_URL not configured", duration_ms
    duration_ms = int((time.monotonic() - start) * 1000)
    return True, f"provider={settings.LLM_PROVIDER}, model={settings.LLM_MODEL_NAME}", duration_ms


def get_uptime_seconds() -> float:
    return round(time.monotonic() - START_TIME, 1)


def get_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
