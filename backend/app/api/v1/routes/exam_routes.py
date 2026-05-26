"""Exam routes - mock exam session management."""

import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import DbSession, get_user_context, UserContext
from app.services.exam_service import ExamService

router = APIRouter()


# ── Schemas ──

class CreateExamRequest(BaseModel):
    title: str | None = None
    duration_minutes: int = Field(default=60, ge=10, le=180)
    question_count: int = Field(default=10, ge=1, le=50)
    difficulty_filter: str | None = None  # easy, medium, hard
    source_filter: str | None = None


class SubmitAnswerRequest(BaseModel):
    question_id: str
    user_answer: str


# ── Routes ──

@router.post("/sessions", summary="创建模拟考试")
async def create_exam(session: DbSession, data: CreateExamRequest, user_ctx: UserContext = Depends(get_user_context)):
    """Create a new exam session with selected questions."""
    service = ExamService(session)
    try:
        result = await service.create_exam_session(
            user_ctx=user_ctx,
            title=data.title,
            duration_minutes=data.duration_minutes,
            question_count=data.question_count,
            difficulty_filter=data.difficulty_filter,
            source_filter=data.source_filter,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{exam_id}", summary="获取考试详情")
async def get_exam(session: DbSession, exam_id: str, user_ctx: UserContext = Depends(get_user_context)):
    """Get exam session details including questions and answers."""
    try:
        exam_uuid = uuid.UUID(exam_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exam ID")

    service = ExamService(session)
    result = await service.get_exam_session(exam_uuid, user_ctx=user_ctx)
    if not result:
        raise HTTPException(status_code=404, detail="Exam not found")
    return result


@router.post("/sessions/{exam_id}/start", summary="开始考试")
async def start_exam(session: DbSession, exam_id: str, user_ctx: UserContext = Depends(get_user_context)):
    """Mark exam as started."""
    try:
        exam_uuid = uuid.UUID(exam_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exam ID")

    service = ExamService(session)
    try:
        return await service.start_exam(exam_uuid, user_ctx=user_ctx)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{exam_id}/answers", summary="提交答案")
async def submit_answer(session: DbSession, exam_id: str, data: SubmitAnswerRequest, user_ctx: UserContext = Depends(get_user_context)):
    """Save or update an answer during exam."""
    try:
        exam_uuid = uuid.UUID(exam_id)
        question_uuid = uuid.UUID(data.question_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    service = ExamService(session)
    try:
        return await service.submit_answer(exam_uuid, question_uuid, data.user_answer, user_ctx=user_ctx)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{exam_id}/submit", summary="提交试卷")
async def submit_exam(session: DbSession, exam_id: str, user_ctx: UserContext = Depends(get_user_context)):
    """Submit the exam for grading."""
    try:
        exam_uuid = uuid.UUID(exam_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exam ID")

    service = ExamService(session)
    try:
        return await service.submit_exam(exam_uuid, user_ctx=user_ctx)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{exam_id}/grade", summary="批改试卷（SSE流式）", response_class=StreamingResponse)
async def grade_exam(session: DbSession, exam_id: str, user_ctx: UserContext = Depends(get_user_context)):
    """Grade exam answers and return progress via SSE."""
    try:
        exam_uuid = uuid.UUID(exam_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exam ID")

    service = ExamService(session)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in service.grade_exam(exam_uuid, user_ctx=user_ctx):
                import json
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            import json
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions", summary="获取历史考试列表")
async def list_exams(
    session: DbSession,
    user_ctx: UserContext = Depends(get_user_context),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List exam sessions with pagination."""
    from sqlalchemy import func, select
    from app.domain.models import ExamSession

    offset = (page - 1) * page_size
    count_stmt = select(func.count()).select_from(ExamSession)
    if user_ctx.user_id is not None and not user_ctx.is_admin:
        count_stmt = count_stmt.where(ExamSession.user_id == user_ctx.user_id)
    total = (await session.exec(count_stmt)).scalar_one()

    stmt = select(ExamSession).order_by(ExamSession.created_at.desc()).offset(offset).limit(page_size)
    if user_ctx.user_id is not None and not user_ctx.is_admin:
        stmt = stmt.where(ExamSession.user_id == user_ctx.user_id)
    result = await session.scalars(stmt)
    exams = result.all()

    return {
        "items": [
            {
                "id": str(e.id),
                "title": e.title,
                "duration_minutes": e.duration_minutes,
                "total_questions": e.total_questions,
                "status": e.status,
                "total_score": e.total_score,
                "created_at": e.created_at.isoformat(),
            }
            for e in exams
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
