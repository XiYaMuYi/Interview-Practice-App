"""Metrics routes — lightweight system metrics."""

from fastapi import APIRouter

from app.core.logging import get_logger
from app.services import metrics_service as svc

logger = get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_metrics() -> dict:
    return await svc.get_all_metrics()
