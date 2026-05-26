"""Health check routes — lightweight liveness and readiness probes."""

from fastapi import APIRouter

from app.core.logging import get_logger
from app.services import health_service as svc

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Quick health check — no dependency probing."""
    return {
        "status": "ok",
        "timestamp": svc.get_timestamp(),
        "uptime_seconds": svc.get_uptime_seconds(),
        "version": svc.APP_VERSION,
    }


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe — process is running."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict:
    """Readiness probe — verify all critical dependencies."""
    db_ok, db_detail, db_ms = await svc.check_database()
    vs_ok, vs_detail, vs_ms = await svc.check_vector_store()
    llm_ok, llm_detail, llm_ms = await svc.check_llm_provider()

    all_ok = db_ok and vs_ok and llm_ok
    status = "ready" if all_ok else "not_ready"

    checks = {
        "database": {"status": "ok" if db_ok else "error", "detail": db_detail, "duration_ms": db_ms},
        "vector_store": {"status": "ok" if vs_ok else "error", "detail": vs_detail, "duration_ms": vs_ms},
        "llm_provider": {"status": "ok" if llm_ok else "error", "detail": llm_detail, "duration_ms": llm_ms},
    }

    return {
        "status": status,
        "checks": checks,
    }
