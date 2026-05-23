"""Pydantic schemas for task management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    task_type: str = Field(max_length=50)
    source_id: str | None = None


class TaskUpdate(BaseModel):
    status: str | None = None
    progress: float | None = None
    current_phase: str | None = None
    total_chunks: int | None = None
    processed_chunks: int | None = None
    error_message: str | None = None
    retry_count: int | None = None
    extra_data: dict | None = None


class TaskRead(BaseModel):
    id: UUID
    task_type: str
    source_id: str | None
    status: str
    progress: float
    current_phase: str | None
    total_chunks: int | None
    processed_chunks: int | None
    error_message: str | None
    retry_count: int
    extra_data: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
