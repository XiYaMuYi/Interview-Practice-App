"""Schema validation tests — ensure Pydantic response schemas match ORM data."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    ChatHistoryResponse,
    ChatResponse,
    EvaluationResponse,
    InterviewAnswerResponse,
    InterviewStartResponse,
    LLMCallLogResponse,
    LoginResponse,
    QuestionResponse,
    ReviewListItem,
    StudyRecordResponse,
    StudyStatsResponse,
    TokenRefreshResponse,
)
from app.domain.schemas.resume_schemas import (
    ResumeExperienceRead,
    ResumeParseResponse,
    ResumeRead,
)


# ── StudyRecordResponse ──

class TestStudyRecordResponse:
    """Ensure the fix for the created_at bug: all required fields present."""

    def test_minimal_valid(self):
        """Should validate with only required fields."""
        data = {
            "id": uuid4(),
            "question_id": uuid4(),
            "study_type": "practice",
            "reviewed_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }
        resp = StudyRecordResponse(**data)
        assert resp.id == data["id"]
        assert resp.study_type == "practice"
        assert resp.created_at is not None

    def test_all_fields(self):
        """Should validate with all fields populated."""
        data = {
            "id": uuid4(),
            "question_id": uuid4(),
            "study_type": "review",
            "user_answer": "My answer",
            "ai_score": 80,
            "ai_feedback": "Good job",
            "mastery_level": 3,
            "duration_seconds": 120,
            "review_result": "mastered",
            "reviewed_at": datetime.utcnow(),
            "next_review_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }
        resp = StudyRecordResponse(**data)
        assert resp.ai_score == 80
        assert resp.created_at is not None

    def test_created_at_is_required(self):
        """created_at must be present — this was the bug."""
        data = {
            "id": uuid4(),
            "question_id": uuid4(),
            "study_type": "practice",
            "reviewed_at": datetime.utcnow(),
            # created_at intentionally missing
        }
        with pytest.raises(ValidationError):
            StudyRecordResponse(**data)

    def test_question_id_optional(self):
        """question_id can be None."""
        data = {
            "id": uuid4(),
            "question_id": None,
            "study_type": "practice",
            "reviewed_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        }
        resp = StudyRecordResponse(**data)
        assert resp.question_id is None


# ── QuestionResponse ──

class TestQuestionResponse:
    def test_minimal_valid(self):
        data = {
            "id": uuid4(),
            "title": "What is Python?",
            "content": "Python is a programming language.",
            "source_type": "manual",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        resp = QuestionResponse(**data)
        assert resp.title == "What is Python?"

    def test_created_at_and_updated_at_required(self):
        data = {
            "id": uuid4(),
            "title": "Q",
            "content": "C",
            "source_type": "manual",
        }
        with pytest.raises(ValidationError):
            QuestionResponse(**data)


# ── ResumeRead ──

class TestResumeRead:
    def test_minimal_valid(self):
        data = {
            "id": uuid4(),
            "file_name": "test.pdf",
            "file_path": "/uploads/test.pdf",
            "source_type": "upload",
            "parse_status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        resp = ResumeRead(**data)
        assert resp.file_name == "test.pdf"


# ── ResumeExperienceRead ──

class TestResumeExperienceRead:
    def test_minimal_valid(self):
        data = {
            "id": uuid4(),
            "resume_id": uuid4(),
            "experience_type": "work",
            "created_at": datetime.utcnow(),
        }
        resp = ResumeExperienceRead(**data)
        assert resp.experience_type == "work"


# ── ChatResponse ──

class TestChatResponse:
    def test_minimal_valid(self):
        data = {
            "session_id": "test-session",
            "assistant_message": "Hello!",
        }
        resp = ChatResponse(**data)
        assert resp.assistant_message == "Hello!"


# ── LoginResponse ──

class TestLoginResponse:
    def test_minimal_valid(self):
        data = {
            "access_token": "token123",
            "expires_in": 3600,
        }
        resp = LoginResponse(**data)
        assert resp.token_type == "bearer"  # default


# ── StudyStatsResponse ──

class TestStudyStatsResponse:
    def test_minimal_valid(self):
        data = {
            "total_sessions": 10,
            "total_reviews": 5,
            "total_practice": 5,
            "questions_mastered": 3,
            "questions_pending": 2,
        }
        resp = StudyStatsResponse(**data)
        assert resp.total_sessions == 10


# ── ReviewListItem ──

class TestReviewListItem:
    def test_minimal_valid(self):
        data = {
            "question_id": uuid4(),
            "question_title": "Test Q",
        }
        resp = ReviewListItem(**data)
        assert resp.question_title == "Test Q"
