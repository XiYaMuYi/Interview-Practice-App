"""题目相关 API 路由。

这里是题库侧的 HTTP 入口，负责把前端请求转给 QuestionService。
它本身不承载复杂业务，只做路由、参数收集和响应组织。
"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.common.pagination import build_paginated_response
from app.services.question_service import QuestionService

router = APIRouter()


@router.post("/import")
async def import_questions(session: DbSession, data: dict):
    """批量导入自定义题目。

    接收 questions: List[dict]，每条包含 content、category、difficulty、reference_answer，
    批量插入 questions 表，source_type 标记为 "CUSTOM"。
    """
    from pydantic import BaseModel, Field, ValidationError

    class QuestionImportItem(BaseModel):
        content: str = Field(min_length=1, max_length=5000)
        category: str | None = Field(default=None, max_length=100)
        difficulty: int | None = Field(default=None, ge=1, le=5)
        reference_answer: str | None = None

    class ImportQuestionsRequest(BaseModel):
        questions: list[QuestionImportItem] = Field(min_length=1, max_length=200)

    try:
        req = ImportQuestionsRequest(**data)
    except ValidationError as exc:
        return {"status": "validation_error", "errors": exc.errors(), "total": 0, "success": 0, "failed": 0}

    service = QuestionService(session)
    results: list[dict] = []
    success_count = 0
    failed_count = 0

    for idx, item in enumerate(req.questions):
        try:
            question_data = {
                "title": item.content[:80],
                "content": item.content,
                "source_type": "CUSTOM",
                "domain_type": item.category,
                "difficulty_level": item.difficulty,
                "answer_summary": item.reference_answer,
            }
            question = await service.create_question(question_data)
            results.append({
                "index": idx,
                "status": "success",
                "id": str(question.id),
                "title": question.title,
            })
            success_count += 1
        except Exception as exc:
            results.append({
                "index": idx,
                "status": "failed",
                "error": str(exc),
                "content_preview": item.content[:50],
            })
            failed_count += 1

    return {
        "status": "completed",
        "total": len(req.questions),
        "success": success_count,
        "failed": failed_count,
        "results": results,
    }


@router.post("/extract")
async def extract_questions(session: DbSession, text: str, source_type: str = Query("paste", max_length=50)):
    """从原始文本中提取题目并保存。

    这是导入链路中的“文本提取”入口，适用于粘贴题目、导入笔记、
    或把外部材料快速转成题库内容。
    """
    from app.services.import_service import ImportService

    service = ImportService(session)
    result = await service.import_text(text, source_type=source_type)
    return result


@router.get("")
@router.get("/")
async def list_questions(
    session: DbSession,
    user_id: str | None = Query(None, description="Filter by user_id"),
    query: str | None = Query(None, description="Full-text search in title/content"),
    domain_type: str | None = Query(None),
    question_type: str | None = Query(None),
    difficulty_level: int | None = Query(None, ge=1, le=5),
    source_type: str | None = Query(None, description="Filter by source: resume/file/text/manual/ai"),
    source_ref: str | None = Query(None, description="Filter by source_ref (e.g. resume_id)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页列出题目。

    支持关键词搜索、领域筛选、题型筛选、难度筛选和来源筛选。
    这是前端题目列表页最主要依赖的接口之一。
    """
    service = QuestionService(session)
    questions, total = await service.list_questions_with_count(
        user_id=user_id,
        query=query,
        domain_type=domain_type,
        question_type=question_type,
        difficulty_level=difficulty_level,
        source_type=source_type,
        source_ref=source_ref,
        page=page,
        page_size=page_size,
    )
    return build_paginated_response(
        items=[
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
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/search")
async def search_questions(
    session: DbSession,
    q: str = Query(..., min_length=1, description="Search keyword"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """按关键词搜索题目，并返回分页结果。

    适合前端的搜索框联动分页使用。
    """
    service = QuestionService(session)
    questions, total = await service.list_questions_with_count(
        query=q,
        page=page,
        page_size=page_size,
    )
    return build_paginated_response(
        items=[
            {
                "id": str(qq.id),
                "title": qq.title,
                "question_type": qq.question_type,
                "domain_type": qq.domain_type,
                "difficulty_level": qq.difficulty_level,
                "source_type": qq.source_type,
            }
            for qq in questions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{question_id}")
async def get_question(session: DbSession, question_id: UUID):
    """按 ID 获取单个题目的基础信息。

    这个接口通常用于题目详情页或面试页的快速加载。
    """
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
    """手动创建题目。

    适用于后台录入、人工维护题库、或从外部系统导入后再补充字段。
    """
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
    """获取题目完整详情。

    这个接口会返回题目正文、来源、标签、知识节点、讲解、复习状态等，
    主要服务于详情页、练习页和面试页。
    """
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
    """按语义相似度搜索题目。

    这是 RAG 检索的面向业务入口，适合做“相关题推荐”“相似题召回”。
    """
    from app.services.question_service import QuestionService

    service = QuestionService(session)
    results = await service.semantic_search(query, top_k=top_k)
    return {"items": results, "total": len(results)}


@router.post("/auto-classify")
async def auto_classify_new(session: DbSession, data: dict):
    """创建题目后自动分类并关联知识节点。

    这是一个便捷接口，适合导入链路或后台批处理使用。
    """
    service = QuestionService(session)
    question = await service.create_question(data)
    classification = await service.classify_question(question.id)
    await service.auto_link_knowledge_nodes(question.id)
    return {
        "status": "created_and_classified",
        "id": str(question.id),
        "classification": classification,
    }
