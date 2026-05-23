"""Study routes — study records, review scheduling, statistics."""

from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.common.pagination import build_paginated_response
from app.domain.schemas import (
    LearningPathRequest,
    ReviewListItem,
    ReviewListResponse,
    ReviewReportRequest,
    ReviewRequest,
    StudyRecordResponse,
    StudySessionCreate,
    StudyStatsResponse,
)
from app.services.study_service import StudyService

router = APIRouter()


def _study_record_response(record: dict) -> StudyRecordResponse:
    """Normalize service output before FastAPI response validation."""
    record_data = dict(record)
    if record_data.get("created_at") is None:
        record_data["created_at"] = record_data.get("reviewed_at")
    if record_data.get("reviewed_at") is None:
        record_data["reviewed_at"] = record_data.get("created_at")
    return StudyRecordResponse.model_validate(record_data)


@router.post("/records", response_model=StudyRecordResponse)
async def create_study_record(session: DbSession, data: StudySessionCreate):
    """Record a study session."""
    service = StudyService(session)
    record_data = data.model_dump()
    record = await service.create_study_record(record_data)
    return _study_record_response(record)


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
    return _study_record_response(record)


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


@router.get("/stats/by-source")
async def get_stats_by_source(session: DbSession):
    """Get study statistics breakdown by question source type."""
    from app.domain.models import Question, StudyRecord

    stmt = (
        select(Question.source_type, func.count(func.distinct(StudyRecord.question_id)))
        .join(StudyRecord, StudyRecord.question_id == Question.id)
        .where(Question.deleted_at.is_(None))
        .group_by(Question.source_type)
    )
    result = await session.exec(stmt)
    breakdown = {row[0] or "unknown": row[1] for row in result.all()}
    return breakdown


@router.post("/review-report/generate-stream")
async def generate_review_report_stream(session: DbSession, data: ReviewReportRequest):
    """Generate a review report via SSE stream."""
    service = StudyService(session)
    task_id, event_gen = await service.generate_review_report_stream(
        session_id=data.session_id,
        days=data.days,
        include_feedback=data.include_feedback,
    )
    return StreamingResponse(
        event_gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/learning-path/generate-stream")
async def generate_learning_path_stream(session: DbSession, data: LearningPathRequest):
    """Generate a learning path via SSE stream."""
    service = StudyService(session)
    task_id, event_gen = await service.generate_learning_path_stream(
        focus_areas=data.focus_areas,
        max_items=data.max_items,
        strategy=data.strategy,
    )
    return StreamingResponse(
        event_gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
