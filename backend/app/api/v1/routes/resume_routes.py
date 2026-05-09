"""Resume routes — upload, parse, and manage resumes."""

from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import DbSession
from app.core.exceptions import ParseError
from app.domain.schemas.resume_schemas import (
    ResumeParseResponse,
    ResumeRead,
    ResumeUpdate,
)
from app.services.resume_service import ResumeService

router = APIRouter()


@router.post("/upload", response_model=ResumeRead)
async def upload_resume(
    session: DbSession,
    file: UploadFile = File(...),
):
    """Upload a resume file (PDF, DOCX, TXT, MD)."""
    content = await file.read()
    if not content:
        raise ParseError("Uploaded file is empty")

    service = ResumeService(session)
    resume = await service.upload_resume(file_name=file.filename or "unknown", content=content)
    return resume


@router.post("/upload-text", response_model=ResumeRead)
async def upload_resume_text(
    session: DbSession,
    text: str = Form(...),
    file_name: str = Form(default="pasted_resume.txt"),
):
    """Upload resume content as plain text."""
    if not text.strip():
        raise ParseError("Empty text provided")

    service = ResumeService(session)
    resume = await service.upload_resume(file_name=file_name, content=text.encode("utf-8"))
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


@router.get("", response_model=list[ResumeRead])
async def list_resumes(
    session: DbSession,
    offset: int = 0,
    limit: int = 50,
):
    """List all uploaded resumes."""
    service = ResumeService(session)
    resumes = await service.list_resumes(offset=offset, limit=limit)
    return resumes


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
