"""Study routes — study records, review scheduling, statistics."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.common.pagination import build_paginated_response
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List study records with optional filters."""
    service = StudyService(session)
    records, total = await service.get_study_records_with_count(
        question_id=question_id,
        study_type=study_type,
        page=page,
        page_size=page_size,
    )
    return build_paginated_response(
        items=records,
        total=total,
        page=page,
        page_size=page_size,
    )


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


@router.get("/review-list")
async def get_review_list(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get questions due for review."""
    service = StudyService(session)
    items, total = await service.get_review_list_with_count(
        page=page,
        page_size=page_size,
    )
    review_items = [ReviewListItem(**item) for item in items]
    return build_paginated_response(
        items=[item.model_dump() for item in review_items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=StudyStatsResponse)
async def get_study_stats(session: DbSession):
    """Get aggregated study statistics."""
    service = StudyService(session)
    stats = await service.get_stats()
    return StudyStatsResponse(**stats)
