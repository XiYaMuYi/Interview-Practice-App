"""Metrics service — lightweight JSON metrics via SQL aggregation."""

import asyncio

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.db.session import engine

logger = get_logger(__name__)


async def get_task_metrics() -> dict:
    """Aggregate task counts by status."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT status, COUNT(*) AS cnt
                FROM tasks
                GROUP BY status
            """))
            rows = result.fetchall()
            counts = {row[0]: row[1] for row in rows}

        return {
            "total": sum(counts.values()),
            "pending": counts.get("pending", 0),
            "processing": counts.get("processing", 0),
            "failed": counts.get("failed", 0),
            "done": counts.get("done", 0),
        }
    except Exception as e:
        logger.error(f"Failed to get task metrics: {e}")
        return {"total": 0, "pending": 0, "processing": 0, "failed": 0, "done": 0}


async def get_question_metrics() -> dict:
    """Count total questions and those with embeddings."""
    try:
        async with engine.connect() as conn:
            total_result = await conn.execute(text(
                "SELECT COUNT(*) FROM questions WHERE deleted_at IS NULL"
            ))
            total = total_result.scalar() or 0

            embedding_result = await conn.execute(text(
                "SELECT COUNT(DISTINCT question_id) FROM question_embeddings"
            ))
            with_embeddings = embedding_result.scalar() or 0

        return {
            "total": total,
            "with_embeddings": with_embeddings,
        }
    except Exception as e:
        logger.error(f"Failed to get question metrics: {e}")
        return {"total": 0, "with_embeddings": 0}


async def get_study_metrics() -> dict:
    """Count total study sessions (distinct session_ids)."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT COUNT(DISTINCT session_id) FROM study_records WHERE session_id IS NOT NULL"
            ))
            total = result.scalar() or 0

        return {"total": total}
    except Exception as e:
        logger.error(f"Failed to get study metrics: {e}")
        return {"total": 0}


async def get_all_metrics() -> dict:
    """Return all metrics in a single call."""
    tasks, questions, study = await asyncio.gather(
        get_task_metrics(),
        get_question_metrics(),
        get_study_metrics(),
    )
    return {
        "tasks": tasks,
        "questions": questions,
        "study_sessions": study,
    }
