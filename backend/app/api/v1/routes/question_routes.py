"""Question routes — list, detail, CRUD, search, classification."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.services.question_service import QuestionService

router = APIRouter()


@router.post("/extract")
async def extract_questions(session: DbSession, text: str, source_type: str = Query("paste", max_length=50)):
    """Extract questions from raw text using LLM and save to database."""
    from app.services.import_service import ImportService

    service = ImportService(session)
    result = await service.import_text(text, source_type=source_type)
    return result


@router.get("")
@router.get("/")
async def list_questions(
    session: DbSession,
    query: str | None = Query(None, description="Full-text search in title/content"),
    domain_type: str | None = Query(None),
    question_type: str | None = Query(None),
    difficulty_level: int | None = Query(None, ge=1, le=5),
    source_type: str | None = Query(None, description="Filter by source: resume/file/text/manual/ai"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List questions with optional filters."""
    service = QuestionService(session)
    questions = await service.list_questions(
        query=query,
        domain_type=domain_type,
        question_type=question_type,
        difficulty_level=difficulty_level,
        source_type=source_type,
        offset=offset,
        limit=limit,
    )
    return {
        "total": len(questions),
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": str(q.id),
                "title": q.title,
                "question_type": q.question_type,
                "domain_type": q.domain_type,
                "difficulty_level": q.difficulty_level,
                "source_type": q.source_type,
            }
            for q in questions
        ],
    }


@router.get("/search")
async def search_questions(
    session: DbSession,
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search questions by title/content keywords using SQL LIKE."""
    service = QuestionService(session)
    questions = await service.list_questions(query=q, offset=0, limit=limit)
    return {
        "total": len(questions),
        "limit": limit,
        "query": q,
        "items": [
            {
                "id": str(qq.id),
                "title": qq.title,
                "question_type": qq.question_type,
                "domain_type": qq.domain_type,
                "difficulty_level": qq.difficulty_level,
            }
            for qq in questions
        ],
    }


@router.get("/{question_id}")
async def get_question(session: DbSession, question_id: UUID):
    """Get a single question by ID."""
    service = QuestionService(session)
    question = await service.get_question(question_id)
    return {
        "id": str(question.id),
        "title": question.title,
        "content": question.content,
        "source_type": question.source_type,
        "question_type": question.question_type,
        "domain_type": question.domain_type,
        "difficulty_level": question.difficulty_level,
        "difficulty_score": question.difficulty_score,
        "answer_summary": question.answer_summary,
        "explanation": question.explanation,
        "common_pitfalls": question.common_pitfalls,
        "created_at": question.created_at.isoformat(),
    }


@router.post("")
@router.post("/")
async def create_question(session: DbSession, data: dict):
    """Create a new question manually."""
    service = QuestionService(session)
    question = await service.create_question(data)
    return {"status": "created", "id": str(question.id)}


@router.put("/{question_id}")
async def update_question(session: DbSession, question_id: UUID, data: dict):
    """Update a question's fields."""
    service = QuestionService(session)
    question = await service.update_question(question_id, data)
    return {"status": "updated", "id": str(question.id)}


@router.delete("/{question_id}")
async def delete_question(session: DbSession, question_id: UUID):
    """Soft-delete a question."""
    service = QuestionService(session)
    deleted = await service.delete_question(question_id)
    return {"status": "deleted" if deleted else "not_found"}


@router.post("/{question_id}/classify")
async def classify_question(session: DbSession, question_id: UUID):
    """Re-classify a question using the LLM."""
    service = QuestionService(session)
    result = await service.classify_question(question_id)
    return {"status": "classified", **result}


@router.post("/{question_id}/embed")
async def embed_question(session: DbSession, question_id: UUID):
    """Generate an embedding for a question."""
    service = QuestionService(session)
    await service.embed_question(question_id)
    return {"status": "embedded"}


@router.get("/{question_id}/detail")
async def get_question_detail(session: DbSession, question_id: UUID):
    """Get full question detail including tags and knowledge nodes."""
    service = QuestionService(session)
    question = await service.get_question_with_relations(question_id)

    detail = {
        "id": str(question.id),
        "title": question.title,
        "content": question.content,
        "source_type": question.source_type,
        "source_ref": question.source_ref,
        "source_excerpt": question.source_excerpt,
        "question_type": question.question_type,
        "domain_type": question.domain_type,
        "difficulty_level": question.difficulty_level,
        "difficulty_score": question.difficulty_score,
        "answer_summary": question.answer_summary,
        "answer_detail": question.answer_detail,
        "explanation": question.explanation,
        "common_pitfalls": question.common_pitfalls,
        "review_status": question.review_status,
        "created_at": question.created_at.isoformat(),
        "tags": [
            {
                "tag_name": qt.tag.name if qt.tag else None,
                "tag_type": qt.tag.tag_type if qt.tag else None,
                "source_type": qt.source_type,
                "confidence": qt.confidence,
            }
            for qt in (question.tags or [])
        ],
        "knowledge_nodes": [
            {
                "node_name": qkn.knowledge_node.name if qkn.knowledge_node else None,
                "node_type": qkn.knowledge_node.node_type if qkn.knowledge_node else None,
                "relation_type": qkn.relation_type,
                "confidence": qkn.confidence,
            }
            for qkn in (question.knowledge_nodes or [])
        ],
    }
    return detail


@router.post("/search/semantic")
async def semantic_search(session: DbSession, query: str, top_k: int = Query(10, ge=1, le=50)):
    """Search questions by semantic similarity using embeddings."""
    from app.services.question_service import QuestionService

    service = QuestionService(session)
    results = await service.semantic_search(query, top_k=top_k)
    return {"items": results, "total": len(results)}


@router.post("/auto-classify")
async def auto_classify_new(session: DbSession, data: dict):
    """Create a question and auto-classify it in one step."""
    service = QuestionService(session)
    question = await service.create_question(data)
    classification = await service.classify_question(question.id)
    await service.auto_link_knowledge_nodes(question.id)
    return {
        "status": "created_and_classified",
        "id": str(question.id),
        "classification": classification,
    }
