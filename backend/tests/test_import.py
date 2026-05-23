"""Import API tests — text import and file format endpoints."""

import pytest


@pytest.mark.asyncio
class TestImportText:
    """Tests for POST /api/v1/import/text."""

    async def test_import_text_empty(self, client, db_session):
        """Empty text should be handled gracefully."""
        resp = await client.post("/api/v1/import/text", data={"text": ""})
        # Should not 500; may return validation error or empty result
        assert resp.status_code in (200, 400, 422)

    async def test_import_text_with_content(self, client, db_session):
        """Import some text content."""
        text = "Question 1: What is Python?\nAnswer: Python is a programming language."
        resp = await client.post("/api/v1/import/text", data={"text": text})
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


@pytest.mark.asyncio
class TestImportFormats:
    """Tests for GET /api/v1/import/supported-formats."""

    async def test_supported_formats(self, client, db_session):
        """Should return list of supported file extensions."""
        resp = await client.get("/api/v1/import/supported-formats")
        assert resp.status_code == 200
        body = resp.json()
        assert "extensions" in body
        assert isinstance(body["extensions"], list)
        assert "pdf" in body["extensions"] or "docx" in body["extensions"]


@pytest.mark.asyncio
class TestQuestionImport:
    """Tests for POST /api/v1/questions/import."""

    async def test_import_questions_valid(self, client, db_session):
        """Import questions with valid payload."""
        payload = {
            "questions": [
                {
                    "content": "What is a decorator in Python?",
                    "category": "python",
                    "difficulty": 3,
                    "reference_answer": "A function that modifies another function.",
                },
                {
                    "content": "Explain async/await.",
                    "category": "python",
                    "difficulty": 4,
                },
            ]
        }
        resp = await client.post("/api/v1/questions/import", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["total"] == 2

    async def test_import_questions_validation_error(self, client, db_session):
        """Empty questions list should return validation error."""
        payload = {"questions": []}
        resp = await client.post("/api/v1/questions/import", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "validation_error"
