"""Study routes — study records, review scheduling, statistics."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.domain.schemas import (
    ReviewListItem,
    ReviewListResponse,
    ReviewRequest,
    StudyRecordResponse,
    StudySessionCreate,
    StudyStatsResponse,
)
from app.services.study_service import StudyService

router = APIRouter()


@router.post("/records", response_model=StudyRecordResponse)
async def create_study_record(session: DbSession, data: StudySessionCreate):
    """Record a study session."""
    service = StudyService(session)
    record_data = data.model_dump()
    record = await service.create_study_record(record_data)
    return record


@router.get("/records")
async def list_study_records(
    session: DbSession,
    question_id: UUID | None = Query(None),
    study_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List study records with optional filters."""
    service = StudyService(session)
    records = await service.get_study_records(
        question_id=question_id,
        study_type=study_type,
        offset=offset,
        limit=limit,
    )
    return {"total": len(records), "items": records}


@router.get("/records/{question_id}")
async def get_question_records(session: DbSession, question_id: UUID):
    """Get all study records for a specific question."""
    service = StudyService(session)
    records = await service.get_records_for_question(question_id)
    return {"question_id": str(question_id), "total": len(records), "items": records}


@router.post("/review", response_model=StudyRecordResponse)
async def record_review(session: DbSession, data: ReviewRequest):
    """Record a review and calculate next review date (SM-2 simplified)."""
    service = StudyService(session)
    record = await service.record_review(
        question_id=data.question_id,
        quality=data.quality,
        user_answer=data.user_answer,
        duration=data.duration_seconds,
    )
    return record


@router.get("/review-list", response_model=ReviewListResponse)
async def get_review_list(session: DbSession, limit: int = Query(50, ge=1, le=200)):
    """Get questions due for review."""
    service = StudyService(session)
    items = await service.get_review_list(limit=limit)
    review_items = [ReviewListItem(**item) for item in items]
    return ReviewListResponse(items=review_items, total=len(review_items))


@router.get("/stats", response_model=StudyStatsResponse)
async def get_study_stats(session: DbSession):
    """Get aggregated study statistics."""
    service = StudyService(session)
    stats = await service.get_stats()
    return StudyStatsResponse(**stats)
