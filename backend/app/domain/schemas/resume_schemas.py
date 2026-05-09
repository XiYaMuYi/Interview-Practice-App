"""Pydantic schemas for resume upload, parsing, and CRUD."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Resume Experience ────────────────────────────────────────────────


class ResumeExperienceCreate(BaseModel):
    experience_type: str = Field(max_length=50)
    company_or_project: str | None = Field(default=None, max_length=255)
    role_title: str | None = Field(default=None, max_length=255)
    start_date: str | None = Field(default=None, max_length=20)
    end_date: str | None = Field(default=None, max_length=20)
    description: str | None = None
    tech_stack: dict | None = None
    extracted_keywords: dict | None = None
    confidence: float | None = None
    extra_data: dict | None = None


class ResumeExperienceRead(BaseModel):
    id: UUID
    resume_id: UUID
    experience_type: str
    company_or_project: str | None = None
    role_title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    tech_stack: dict | None = None
    extracted_keywords: dict | None = None
    confidence: float | None = None
    extra_data: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Resume ───────────────────────────────────────────────────────────


class ResumeCreate(BaseModel):
    file_name: str = Field(max_length=255)
    file_path: str = Field(max_length=500)
    source_type: str = Field(default="upload", max_length=50)
    file_id: UUID | None = None
    raw_text: str | None = None


class ResumeRead(BaseModel):
    id: UUID
    file_id: UUID | None = None
    file_name: str
    file_path: str
    source_type: str
    parse_status: str
    raw_text: str | None = None
    structured_summary: dict | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    extra_data: dict | None = None
    created_at: datetime
    updated_at: datetime
    # Note: experiences omitted here to avoid lazy-load MissingGreenlet errors.
    # Use GET /{resume_id}/experiences to fetch them separately.

    model_config = {"from_attributes": True}


class ResumeUpdate(BaseModel):
    file_name: str | None = Field(default=None, max_length=255)
    parse_status: str | None = None
    raw_text: str | None = None
    structured_summary: dict | None = None
    extra_data: dict | None = None


class ResumeParseResponse(BaseModel):
    resume_id: UUID
    parse_status: str
    structured_summary: dict | None = None
    experiences_count: int = 0
    model_version: str | None = None
    prompt_version: str | None = None
