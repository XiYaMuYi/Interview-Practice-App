"""Resume routes — upload, parse, and manage resumes."""

import hashlib
from uuid import UUID

from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.common.pagination import build_paginated_response
from app.core.exceptions import ParseError
from app.domain.schemas.resume_schemas import (
    ResumeExperienceRead,
    ResumeParseResponse,
    ResumeRead,
    ResumeUpdate,
)
from app.services.resume_service import ResumeService
from app.services.task_manager import TaskManager

router = APIRouter()


@router.post("/upload", response_model=ResumeRead)
async def upload_resume(
    session: DbSession,
    file: UploadFile = File(...),
    user_id: str | None = Query(default=None),
):
    """Upload a resume file (PDF, DOCX, TXT, MD)."""
    content = await file.read()
    if not content:
        raise ParseError("Uploaded file is empty")

    # Problem 4: compute SHA256 hash for duplicate detection
    file_hash = hashlib.sha256(content).hexdigest()

    if user_id:
        service = ResumeService(session)
        existing = await service.find_by_user_and_hash(user_id, file_hash)
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "duplicate",
                    "message": "Same file already uploaded by this user",
                    "existing_resume_id": str(existing.id),
                    "file_hash": file_hash,
                },
            )

    service = ResumeService(session)
    resume = await service.upload_resume(
        file_name=file.filename or "unknown",
        content=content,
        user_id=user_id,
    )
    # Store file_hash in extra_data for later duplicate detection
    resume.extra_data = {"file_hash": file_hash}
    await session.flush()
    return resume


@router.post("/upload-text", response_model=ResumeRead)
async def upload_resume_text(
    session: DbSession,
    text: str = Form(...),
    file_name: str = Form(default="pasted_resume.txt"),
    user_id: str | None = Form(default=None),
):
    """Upload resume content as plain text."""
    if not text.strip():
        raise ParseError("Empty text provided")

    service = ResumeService(session)
    resume = await service.upload_resume(file_name=file_name, content=text.encode("utf-8"), user_id=user_id)
    return resume


@router.post("/{resume_id}/parse", response_model=ResumeParseResponse)
async def parse_resume(
    resume_id: UUID,
    session: DbSession,
):
    """Parse an uploaded resume using LLM to extract structured data."""
    service = ResumeService(session)
    result = await service.parse_resume(resume_id)
    return result


@router.get("")
async def list_resumes(
    session: DbSession,
    user_id: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all uploaded resumes with pagination."""
    service = ResumeService(session)
    resumes, total = await service.list_resumes_with_count(
        page=page,
        page_size=page_size,
        user_id=user_id,
    )
    return build_paginated_response(
        items=[
            {
                "id": str(r.id),
                "file_name": r.file_name,
                "file_path": r.file_path,
                "source_type": r.source_type,
                "parse_status": r.parse_status,
                "structured_summary": r.structured_summary,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in resumes
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{resume_id}", response_model=ResumeRead)
async def get_resume(
    resume_id: UUID,
    session: DbSession,
):
    """Get a single resume by ID."""
    service = ResumeService(session)
    resume = await service.get_resume(resume_id)
    return resume


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: UUID,
    updates: ResumeUpdate,
    session: DbSession,
):
    """Update a resume record."""
    service = ResumeService(session)
    resume = await service.get_resume(resume_id)
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(resume, key, value)
    await session.flush()
    return resume


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: UUID,
    session: DbSession,
):
    """Soft-delete a resume."""
    service = ResumeService(session)
    deleted = await service.delete_resume(resume_id)
    return {"status": "success", "deleted": deleted}


@router.get("/{resume_id}/experiences", response_model=list[ResumeExperienceRead])
async def list_resume_experiences(
    resume_id: UUID,
    session: DbSession,
):
    """List all parsed experiences for a resume."""
    from app.services.resume_service import ResumeService
    service = ResumeService(session)
    return await service.list_experiences(resume_id)


@router.post("/{resume_id}/parse-stream")
async def parse_resume_stream(
    resume_id: UUID,
    generate_questions: bool = Query(
        default=False,
        description="If true, continue into question generation after parsing completes",
    ),
    max_questions: int = Query(default=20, ge=1, le=50),
):
    """Create a streaming resume parsing task. Returns SSE event stream.

    When generate_questions=True, the pipeline continues into question
    generation after parsing completes (parse + generate in one stream).

    We manage the DB session manually here because FastAPI's dependency
    lifecycle commits/closes the session *before* the StreamingResponse
    generator starts iterating, which breaks update_task() flushes.
    """
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = ResumeService(session)
            task_id, event_gen = await service.parse_resume_stream(
                resume_id,
                generate_questions=generate_questions,
                max_questions=max_questions,
            )
            try:
                async for event in event_gen:
                    yield event
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{resume_id}/parse-stream-async")
async def parse_resume_stream_async(
    resume_id: UUID,
    session: DbSession,
):
    """Submit resume parsing to RabbitMQ queue for async processing.

    Returns a task_id that can be used to track progress.
    Falls back to synchronous stream if RabbitMQ is unavailable.
    """
    service = ResumeService(session)
    result = await service.parse_resume_stream_async(resume_id)
    return {"status": "success", **result}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: UUID, session: DbSession):
    """Get current task status."""
    task_manager = TaskManager(session)
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{resume_id}/regenerate-questions")
async def regenerate_questions(
    resume_id: UUID,
    count: int = Query(default=10, ge=1, le=50, description="Number of questions to generate"),
):
    """Regenerate interview questions from resume experiences via SSE stream.

    Reads existing resume_experiences, calls question_generation prompt,
    and streams back newly generated questions as SSE events.
    """
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as db_session:
            service = ResumeService(db_session)
            task_id, event_gen = await service.regenerate_questions_stream(resume_id, count=count)
            try:
                async for event in event_gen:
                    yield event
                await db_session.commit()
            except Exception:
                await db_session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{resume_id}/generate-questions-stream")
async def generate_questions_from_resume(
    resume_id: UUID,
    max_questions: int = Query(default=20, ge=1, le=50, description="Max questions to generate"),
):
    """Generate interview questions from a parsed resume via SSE stream.

    Content Production Pipeline entry point: reads parsed resume experiences,
    calls question_generation LLM prompt, streams newly saved questions.

    Requires resume to be already parsed (parse_status='parsed').
    Use /{resume_id}/parse-stream first if not yet parsed.
    """
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as db_session:
            service = ResumeService(db_session)
            task_id, event_gen = await service.generate_questions_from_resume_stream(
                resume_id, max_questions=max_questions,
            )
            try:
                async for event in event_gen:
                    yield event
                await db_session.commit()
            except Exception:
                await db_session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
