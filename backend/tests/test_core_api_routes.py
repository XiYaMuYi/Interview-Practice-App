from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.routes import import_routes, question_routes, study_routes
from app.infra.db.session import get_db


@pytest.fixture
async def api_client():
    app = FastAPI(redirect_slashes=False)

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db
    app.include_router(question_routes.router, prefix="/api/v1/questions")
    app.include_router(study_routes.router, prefix="/api/v1/study")
    app.include_router(import_routes.router, prefix="/api/v1/import")

    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_create_study_record_backfills_created_at(api_client, monkeypatch):
    question_id = uuid4()
    reviewed_at = datetime.utcnow()

    class FakeStudyService:
        def __init__(self, session):
            self.session = session

        async def create_study_record(self, data):
            return {
                "id": str(uuid4()),
                "question_id": str(data["question_id"]),
                "study_type": data["study_type"],
                "reviewed_at": reviewed_at.isoformat(),
            }

    monkeypatch.setattr(study_routes, "StudyService", FakeStudyService)

    response = await api_client.post(
        "/api/v1/study/records",
        json={"question_id": str(question_id), "study_type": "practice"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question_id"] == str(question_id)
    assert body["study_type"] == "practice"
    assert body["created_at"] == body["reviewed_at"]


@pytest.mark.asyncio
async def test_questions_create_list_and_detail(api_client, monkeypatch):
    question_id = uuid4()
    created_at = datetime.utcnow()
    question = SimpleNamespace(
        id=question_id,
        title="Python GIL",
        content="What is the GIL?",
        source_type="manual",
        question_type="concept",
        domain_type="python",
        difficulty_level=2,
        difficulty_score=None,
        answer_summary="A lock around bytecode execution.",
        explanation=None,
        common_pitfalls=None,
        source_ref=None,
        source_excerpt=None,
        answer_detail=None,
        review_status=None,
        created_at=created_at,
        tags=[],
        knowledge_nodes=[],
    )

    class FakeQuestionService:
        def __init__(self, session):
            self.session = session

        async def create_question(self, data):
            return question

        async def list_questions_with_count(self, **kwargs):
            return [question], 1

        async def get_question_with_relations(self, requested_id):
            assert requested_id == question_id
            return question

    monkeypatch.setattr(question_routes, "QuestionService", FakeQuestionService)

    create_response = await api_client.post(
        "/api/v1/questions",
        json={"title": "Python GIL", "content": "What is the GIL?", "source_type": "manual"},
    )
    list_response = await api_client.get("/api/v1/questions")
    detail_response = await api_client.get(f"/api/v1/questions/{question_id}/detail")

    assert create_response.status_code == 200
    assert create_response.json() == {"status": "created", "id": str(question_id)}
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == str(question_id)
    assert detail_response.status_code == 200
    assert detail_response.json()["knowledge_nodes"] == []


@pytest.mark.asyncio
async def test_import_text_returns_result(api_client, monkeypatch):
    question_id = uuid4()

    class FakeImportService:
        def __init__(self, session):
            self.session = session

        async def import_text(self, text):
            assert text == "Explain Python iterators"
            return {
                "questions_extracted": 1,
                "knowledge_nodes": 1,
                "question_ids": [str(question_id)],
            }

    monkeypatch.setattr(import_routes, "ImportService", FakeImportService)

    response = await api_client.post(
        "/api/v1/import/text",
        data={"text": "Explain Python iterators"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "questions_extracted": 1,
        "knowledge_nodes": 1,
        "question_ids": [str(question_id)],
    }
