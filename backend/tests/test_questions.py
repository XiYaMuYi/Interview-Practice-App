"""Question API tests — CRUD, search, and detail endpoints."""

import pytest

from app.domain.models import Question, QuestionTag, Tag


@pytest.mark.asyncio
class TestQuestionCRUD:
    """Tests for basic question CRUD operations."""

    async def test_create_question(self, client, db_session):
        """POST /api/v1/questions should create a question."""
        resp = await client.post(
            "/api/v1/questions",
            json={
                "title": "New Question",
                "content": "What is the meaning of life?",
                "source_type": "manual",
                "difficulty_level": 3,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert "id" in body

    async def test_list_questions(self, client, db_session):
        """GET /api/v1/questions should return paginated questions."""
        q = Question(title="List Q1", content="Content 1", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.get("/api/v1/questions")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    async def test_list_questions_with_filters(self, client, db_session):
        """GET /api/v1/questions with source_type filter."""
        q1 = Question(title="Resume Q", content="Content", source_type="resume")
        q2 = Question(title="Manual Q", content="Content", source_type="manual")
        db_session.add_all([q1, q2])
        await db_session.flush()

        resp = await client.get("/api/v1/questions?source_type=resume")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["source_type"] == "resume"

    async def test_get_question(self, client, db_session):
        """GET /api/v1/questions/{id} should return basic question info."""
        q = Question(
            title="Get Q",
            content="Get content",
            source_type="manual",
            question_type="technical",
            domain_type="python",
            difficulty_level=2,
        )
        db_session.add(q)
        await db_session.flush()

        resp = await client.get(f"/api/v1/questions/{q.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Get Q"
        assert body["content"] == "Get content"
        assert "created_at" in body

    async def test_get_question_detail(self, client, db_session):
        """GET /api/v1/questions/{id}/detail should return full question details with tags."""
        q = Question(
            title="Detail Q",
            content="Detail content",
            source_type="manual",
            explanation="The answer is...",
            common_pitfalls="Don't forget...",
        )
        db_session.add(q)
        await db_session.flush()

        # Add a tag
        tag = Tag(name="Python", tag_type="language")
        db_session.add(tag)
        await db_session.flush()

        qt = QuestionTag(question_id=q.id, tag_id=tag.id, source_type="ai")
        db_session.add(qt)
        await db_session.flush()

        resp = await client.get(f"/api/v1/questions/{q.id}/detail")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Detail Q"
        assert body["explanation"] == "The answer is..."
        assert "tags" in body
        assert len(body["tags"]) >= 1

    async def test_update_question(self, client, db_session):
        """PUT /api/v1/questions/{id} should update fields."""
        q = Question(title="Old Title", content="Content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.put(
            f"/api/v1/questions/{q.id}",
            json={"title": "New Title"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "updated"

    async def test_delete_question(self, client, db_session):
        """DELETE /api/v1/questions/{id} should soft-delete."""
        q = Question(title="Delete Q", content="Content", source_type="manual")
        db_session.add(q)
        await db_session.flush()

        resp = await client.delete(f"/api/v1/questions/{q.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "deleted"


@pytest.mark.asyncio
class TestQuestionSearch:
    """Tests for search endpoints."""

    async def test_search_questions(self, client, db_session):
        """GET /api/v1/questions/search should return matching questions."""
        q = Question(
            title="UniqueSearchableTitle123",
            content="Search content here",
            source_type="manual",
        )
        db_session.add(q)
        await db_session.flush()

        resp = await client.get("/api/v1/questions/search?q=UniqueSearchableTitle123")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert "UniqueSearchableTitle123" in body["items"][0]["title"]

    async def test_search_no_results(self, client, db_session):
        """Search with non-matching query should return empty results."""
        resp = await client.get("/api/v1/questions/search?q=ZZZZNONEXISTENTZZZZ")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
