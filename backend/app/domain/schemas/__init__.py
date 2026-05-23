"""Pydantic request/response DTOs for all API endpoints.

Organized by domain: Questions, Import, Chat, Study, AI, Auth.
All schemas follow the database schema defined in 03_Database_Schema.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────
# Question DTOs
# ─────────────────────────────────────────────────────────────────────


class QuestionCreate(BaseModel):
    """Request body for creating a question manually."""

    title: str = Field(max_length=500)
    content: str
    source_type: str = Field(default="manual", max_length=50)
    source_id: str | None = None
    source_ref: str | None = None
    source_excerpt: str | None = None
    question_type: str | None = None
    domain_type: str | None = None
    difficulty_level: int | None = Field(default=None, ge=1, le=5)
    difficulty_score: float | None = None


class QuestionUpdate(BaseModel):
    """Request body for updating a question's fields."""

    title: str | None = Field(default=None, max_length=500)
    content: str | None = None
    question_type: str | None = None
    domain_type: str | None = None
    difficulty_level: int | None = Field(default=None, ge=1, le=5)
    difficulty_score: float | None = None
    answer_summary: str | None = None
    answer_detail: str | None = None
    explanation: str | None = None
    common_pitfalls: str | None = None
    mastery_level: int | None = Field(default=None, ge=1, le=5)
    review_status: str | None = None
    metadata: dict | None = None


class TagInfo(BaseModel):
    """Nested tag info in question response."""

    tag_name: str | None = None
    tag_type: str | None = None
    source_type: str | None = None
    confidence: float | None = None


class KnowledgeNodeInfo(BaseModel):
    """Nested knowledge node info in question response."""

    node_name: str | None = None
    node_type: str | None = None
    relation_type: str | None = None
    confidence: float | None = None


class QuestionResponse(BaseModel):
    """Full question response for detail view."""

    id: UUID
    title: str
    content: str
    source_type: str
    source_ref: str | None = None
    source_excerpt: str | None = None
    question_type: str | None = None
    domain_type: str | None = None
    difficulty_level: int | None = None
    difficulty_score: float | None = None
    answer_summary: str | None = None
    answer_detail: str | None = None
    explanation: str | None = None
    common_pitfalls: str | None = None
    mastery_level: int | None = None
    review_status: str | None = None
    tags: list[TagInfo] = []
    knowledge_nodes: list[KnowledgeNodeInfo] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionListItem(BaseModel):
    """Compact question for list view."""

    id: UUID
    title: str
    question_type: str | None = None
    domain_type: str | None = None
    difficulty_level: int | None = None
    mastery_level: int | None = None


class QuestionListResponse(BaseModel):
    """Paginated list of questions."""

    total: int
    offset: int
    limit: int
    items: list[QuestionListItem]


# ─────────────────────────────────────────────────────────────────────
# Import DTOs
# ─────────────────────────────────────────────────────────────────────


class ImportTextRequest(BaseModel):
    """Request body for pasting text to import."""

    text: str
    source_type: str = Field(default="paste", max_length=50)


class ImportFileItem(BaseModel):
    """Single file import result."""

    file_id: UUID | None = None
    file_name: str
    parse_status: str
    questions_extracted: int
    knowledge_nodes: int
    question_ids: list[str] = []


class ImportResult(BaseModel):
    """Result of an import operation."""

    status: str
    questions_extracted: int = 0
    knowledge_nodes: int = 0
    question_ids: list[str] = []
    file_id: str | None = None
    file_name: str | None = None
    message: str | None = None


# ─────────────────────────────────────────────────────────────────────
# Chat DTOs
# ─────────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """Single chat message."""

    role: str = Field(max_length=20)
    message: str
    message_type: str | None = None
    related_question_id: UUID | None = None
    evaluation_score: int | None = None
    evaluation_summary: str | None = None


class ChatMessageRequest(BaseModel):
    """Request to send a message in a chat session."""

    session_id: str | None = None
    message: str
    related_question_id: UUID | None = None
    mode: str = Field(default="chat", description="chat, interview, or explain")


class ChatSession(BaseModel):
    """Chat session metadata."""

    session_id: str
    created_at: datetime
    message_count: int


class ChatResponse(BaseModel):
    """Response for a chat message."""

    session_id: str
    assistant_message: str
    related_question_id: UUID | None = None
    message_type: str | None = None


class ChatHistoryResponse(BaseModel):
    """Full chat history for a session."""

    session_id: str
    messages: list[ChatMessage]
    total: int


class ChatSessionListResponse(BaseModel):
    """List of chat sessions."""

    sessions: list[ChatSession]
    total: int


# ─────────────────────────────────────────────────────────────────────
# Study DTOs
# ─────────────────────────────────────────────────────────────────────


class StudySessionCreate(BaseModel):
    """Start a study session for a question."""

    question_id: UUID
    study_type: str = Field(max_length=50, description="review, practice, mock, interview")
    user_answer: str | None = None
    duration_seconds: int | None = None


class ReviewRequest(BaseModel):
    """Request to review a specific question (SM-2)."""

    question_id: UUID
    quality: int = Field(ge=0, le=5, description="0=completely wrong, 5=perfect recall")
    user_answer: str | None = None
    duration_seconds: int | None = None


class StudyRecordResponse(BaseModel):
    """Single study record response."""

    id: UUID
    question_id: UUID | None = None
    study_type: str
    user_answer: str | None = None
    ai_score: int | None = None
    ai_feedback: str | None = None
    mastery_level: int | None = None
    duration_seconds: int | None = None
    review_result: str | None = None
    reviewed_at: datetime
    next_review_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewListItem(BaseModel):
    """Item in the review list."""

    question_id: UUID
    question_title: str
    difficulty_level: int | None = None
    mastery_level: int | None = None
    next_review_at: datetime | None = None
    review_status: str | None = None


class ReviewListResponse(BaseModel):
    """List of questions due for review."""

    items: list[ReviewListItem]
    total: int


class StudyStatsResponse(BaseModel):
    """Aggregated study statistics."""

    total_sessions: int
    total_reviews: int
    total_practice: int
    average_score: float | None = None
    questions_mastered: int
    questions_pending: int


# ─────────────────────────────────────────────────────────────────────
# AI DTOs
# ─────────────────────────────────────────────────────────────────────


class AIExplanationRequest(BaseModel):
    """Request for AI explanation of a question."""

    question_id: UUID | None = None
    question_text: str | None = None
    depth: str = Field(default="standard", description="brief, standard, or deep")


class AIExplanationResponse(BaseModel):
    """AI-generated explanation."""

    answer_short: str = ""
    answer_detail: str = ""
    explanation: str = ""
    knowledge_points: list[str] = []
    common_pitfalls: str | None = None
    related_questions: list[str] = []


class InterviewStartRequest(BaseModel):
    """Start an interview simulation."""

    question_id: UUID | None = None
    domain: str | None = None
    max_turns: int = Field(default=5, ge=1, le=10)


class InterviewStartResponse(BaseModel):
    """Response when starting an interview."""

    session_id: str
    first_question: str
    max_turns: int


class InterviewAnswerRequest(BaseModel):
    """Submit an answer during interview."""

    session_id: str
    answer: str


class InterviewAnswerResponse(BaseModel):
    """Response after submitting an interview answer."""

    followup_question: str | None = None
    score: int | None = None
    feedback: str | None = None
    is_done: bool
    # ReAct safety / convergence visibility (optional, backward-compatible)
    turns_remaining: int | None = None
    convergence_reason: str | None = None  # "max_turns_reached" | "score_threshold_met" | "manual_stop" | "timeout"
    is_timeout: bool | None = None


class EvaluationRequest(BaseModel):
    """Request to evaluate a user answer."""

    question_id: UUID
    user_answer: str


class EvaluationResponse(BaseModel):
    """Evaluation result."""

    score: int
    feedback: str
    missing_points: list[str] = []
    is_pass: bool
    mastery_level: int


class ReviewReportRequest(BaseModel):
    """请求生成复盘报告"""

    session_id: str | None = None
    days: int = 7
    include_feedback: bool = True


class ReviewReportResponse(BaseModel):
    """复盘报告响应"""

    report_id: str
    status: str
    period_days: int
    total_sessions: int
    mastered_count: int
    weak_areas: list[dict]
    summary: str | None = None
    recommendations: list[str] | None = None
    created_at: str


class LearningPathRequest(BaseModel):
    """请求生成学习路径"""

    focus_areas: list[str] = []
    max_items: int = 20
    strategy: str = "weak_first"


class LearningPathResponse(BaseModel):
    """学习路径响应"""

    path_id: str
    status: str
    strategy: str
    items: list[dict]
    total_weak_count: int
    created_at: str


# ─────────────────────────────────────────────────────────────────────
# Auth DTOs
# ─────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    """Login credentials."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Successful login response."""

    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    """User registration request."""

    username: str
    password: str
    email: str | None = None


class RegisterResponse(BaseModel):
    """User registration response."""

    user_id: str
    username: str
    access_token: str
    refresh_token: str
    expires_in: int


class TokenRefreshRequest(BaseModel):
    """Request to refresh an access token."""

    refresh_token: str


class TokenRefreshResponse(BaseModel):
    """Refreshed access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ─────────────────────────────────────────────────────────────────────
# Prompt Version & Observability DTOs
# ─────────────────────────────────────────────────────────────────────


class PromptVersionInfo(BaseModel):
    """Metadata for a single prompt version in a list view."""

    id: UUID | None = None
    key: str
    version: str
    description: str
    created_at: datetime
    is_active: bool = False


class PromptVersionDetail(BaseModel):
    """Full detail of a prompt version including content."""

    id: UUID
    key: str
    version: str
    description: str
    content: str
    model_hints: dict = {}
    created_at: datetime
    is_active: bool = False


class PromptVersionCompare(BaseModel):
    """Side-by-side comparison of two prompt versions."""

    key: str
    v1_version: str
    v1_content: str
    v2_version: str
    v2_content: str
    diff_summary: str


class PromptStats(BaseModel):
    """Aggregated invocation statistics for a prompt key."""

    key: str
    total_calls: int
    success_rate: float
    avg_duration_ms: float
    error_rate: float


class LLMCallLogResponse(BaseModel):
    """Single LLM call log entry."""

    id: UUID
    task_id: UUID | None = None
    session_id: str | None = None
    prompt_key: str
    prompt_version: str
    model_name: str
    duration_ms: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptVersionCreate(BaseModel):
    """Request body to register a new prompt version."""

    version: str = Field(max_length=100)
    content: str
    model_hints: dict = {}
    description: str = ""
