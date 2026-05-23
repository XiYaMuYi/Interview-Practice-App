"""Event schema definitions — Pydantic models for all event payloads."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base event with common fields."""
    event_type: str
    task_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "interview_practice"


class TaskEvent(BaseEvent):
    """Task lifecycle event."""
    task_type: str
    status: str
    source_id: str | None = None
    progress: float = 0.0
    error_message: str | None = None
    extra_data: dict[str, Any] | None = None


class ChunkProcessedEvent(BaseEvent):
    """Chunk processing completed."""
    chunk_index: int
    chunk_type: str
    total_chunks: int
    task_id: str


class QuestionGeneratedEvent(BaseEvent):
    """Question generated and saved."""
    question_id: str
    content_preview: str
    total_generated: int
    task_id: str


class FollowupGeneratedEvent(BaseEvent):
    """Follow-up question generated."""
    original_question_id: str | None = None
    followup_text: str
    task_id: str


class LLMCallEvent(BaseEvent):
    """LLM call result."""
    prompt_key: str
    prompt_version: str
    model_name: str
    duration_ms: int
    status: str  # success | failed
    error_message: str | None = None


class CacheEvent(BaseEvent):
    """Cache hit/miss event."""
    cache_key: str
    ttl: int | None = None
