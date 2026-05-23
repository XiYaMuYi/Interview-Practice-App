"""Study API tests — records, review, stats, and the created_at bug fix."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.domain.models import Question, StudyRecord


@pytest.mark.asyncio
class TestCreateStudyRecord:
    """Tests for POST /api/v1/study/records — the endpoint with the created_at bug."""

    async def test_create_study_record_returns_created_at(self, client, db_session):
        """The bug fix: response must include created_at field."""
        # Create a question first (FK constraint)
        q = Question(title="Test Q", content="Test content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/study/records",
            json={"question_id": str(q.id), "study_type": "practice"},
        )
        assert resp.status_code == 200, f"Unexpected response: {resp.text}"
        body = resp.json()
        assert "created_at" in body, "created_at field missing from response — bug not fixed!"
        assert body["created_at"] is not None
        assert body["study_type"] == "practice"

    async def test_create_study_record_all_fields(self, client, db_session):
        """Response should include all StudyRecordResponse fields."""
        q = Question(title="Full Q", content="Full content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/study/records",
            json={
                "question_id": str(q.id),
                "study_type": "practice",
                "user_answer": "My answer here",
                "duration_seconds": 120,
            },
        )
        assert resp.status_code == 200, f"Unexpected response: {resp.text}"
        body = resp.json()
        assert body["user_answer"] == "My answer here"
        assert body["duration_seconds"] == 120
        assert body["created_at"] is not None
        assert body["reviewed_at"] is not None

    async def test_create_study_record_requires_question_id(self, client, db_session):
        """StudySessionCreate requires a valid question_id (UUID, not nullable in schema)."""
        resp = await client.post(
            "/api/v1/study/records",
            json={"question_id": None, "study_type": "review"},
        )
        # Should reject null question_id — schema requires it
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestReviewEndpoint:
    """Tests for POST /api/v1/study/review."""

    async def test_record_review_returns_created_at(self, client, db_session):
        """Review endpoint should also return all required fields."""
        q = Question(title="Review Q", content="Review content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/study/review",
            json={"question_id": str(q.id), "quality": 4},
        )
        assert resp.status_code == 200, f"Unexpected response: {resp.text}"
        body = resp.json()
        assert "created_at" in body
        assert body["review_result"] == "mastered"  # quality >= 4

    async def test_record_review_needs_reinforcement(self, client, db_session):
        """Low quality score should result in needs_reinforcement."""
        q = Question(title="Bad Q", content="Bad content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/study/review",
            json={"question_id": str(q.id), "quality": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["review_result"] == "needs_reinforcement"


@pytest.mark.asyncio
class TestStudyListEndpoints:
    """Tests for GET study endpoints."""

    async def test_list_study_records(self, client, db_session):
        """GET /api/v1/study/records should return paginated results."""
        q = Question(title="List Q", content="List content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        sr = StudyRecord(question_id=q.id, study_type="practice")
        db_session.add(sr)
        await db_session.flush()

        resp = await client.get("/api/v1/study/records?study_type=practice")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 1

    async def test_get_study_stats(self, client, db_session):
        """GET /api/v1/study/stats should return aggregated stats."""
        resp = await client.get("/api/v1/study/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_sessions" in body
        assert "total_reviews" in body
        assert "total_practice" in body

    async def test_get_records_for_question(self, client, db_session):
        """GET /api/v1/study/records/{question_id} should return records for that question."""
        q = Question(title="Rec Q", content="Rec content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        sr = StudyRecord(question_id=q.id, study_type="practice")
        db_session.add(sr)
        await db_session.flush()

        resp = await client.get(f"/api/v1/study/records/{q.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "question_id" in body
        assert "items" in body
        assert body["total"] >= 1
