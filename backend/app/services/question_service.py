"""Question service — CRUD, classification, search, and knowledge-node linking."""

import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.enums import QuestionType
from app.domain.models import KnowledgeNode, Question, QuestionKnowledgeNode, QuestionTag, Tag
from app.infra.llm.gateway import llm_gateway
from app.infra.repositories import KnowledgeNodeRepository, QuestionRepository, TagRepository
from app.infra.vectorstore.pgvector_store import PGVectorStore

logger = get_logger(__name__)


class QuestionService:
    """Business logic for question CRUD, classification, and search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.question_repo = QuestionRepository(session)
        self.tag_repo = TagRepository(session)
        self.knowledge_node_repo = KnowledgeNodeRepository(session)
        self.vector_store = PGVectorStore(session)

    # ── CRUD ──────────────────────────────────────────────────────

    async def create_question(self, data: dict) -> Question:
        """Create a new question, auto-computing content_hash."""
        content = data.get("content", "")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Check duplicate
        existing = await self.question_repo.list(filters={"content_hash": content_hash})
        if existing:
            return existing[0]

        question = Question(
            title=data.get("title", content[:80])[:500],
            content=content,
            content_hash=content_hash,
            source_type=data.get("source_type", "manual"),
            source_id=data.get("source_id"),
            source_ref=data.get("source_ref"),
            source_excerpt=data.get("source_excerpt"),
            question_type=data.get("question_type"),
            domain_type=data.get("domain_type"),
            difficulty_level=data.get("difficulty_level"),
            difficulty_score=data.get("difficulty_score"),
            model_version=llm_gateway.model_name,
        )
        return await self.question_repo.create(question)

    async def get_question(self, question_id: UUID) -> Question:
        question = await self.question_repo.get_by_id(question_id)
        if question is None or question.deleted_at is not None:
            raise NotFoundError("Question", str(question_id))
        return question

    async def get_question_with_relations(self, question_id: UUID) -> Question:
        """Get a question with tags and knowledge_nodes eagerly loaded."""
        from sqlalchemy.orm import selectinload

        question = await self.question_repo.get_by_id(question_id)
        if question is None or question.deleted_at is not None:
            raise NotFoundError("Question", str(question_id))

        # Eagerly load relationships
        await self.session.refresh(question, attribute_names=["tags", "knowledge_nodes"])

        # Load nested tag and knowledge_node relationships
        for qt in (question.tags or []):
            if qt.tag_id and not hasattr(qt, "_tag_loaded"):
                tag = await self.session.get(Tag, qt.tag_id)
                qt.tag = tag  # type: ignore[attr-defined]
        for qkn in (question.knowledge_nodes or []):
            if qkn.knowledge_node_id and not hasattr(qkn, "_kn_loaded"):
                kn = await self.session.get(KnowledgeNode, qkn.knowledge_node_id)
                qkn.knowledge_node = kn  # type: ignore[attr-defined]

        return question

    async def list_questions(
        self,
        *,
        query: str | None = None,
        domain_type: str | None = None,
        question_type: str | None = None,
        difficulty_level: int | None = None,
        source_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Question]:
        return list(
            await self.question_repo.search(
                query=query,
                domain_type=domain_type,
                question_type=question_type,
                difficulty_level=difficulty_level,
                source_type=source_type,
                offset=offset,
                limit=limit,
            )
        )

    async def list_questions_with_count(
        self,
        *,
        query: str | None = None,
        domain_type: str | None = None,
        question_type: str | None = None,
        difficulty_level: int | None = None,
        source_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Question], int]:
        """Return (items, total_count) using a real COUNT query."""
        offset = (page - 1) * page_size
        items, total = await self.question_repo.search_with_count(
            query=query,
            domain_type=domain_type,
            question_type=question_type,
            difficulty_level=difficulty_level,
            source_type=source_type,
            offset=offset,
            limit=page_size,
        )
        return list(items), total

    async def update_question(self, question_id: UUID, updates: dict) -> Question:
        question = await self.question_repo.get_by_id(question_id)
        if question is None:
            raise NotFoundError("Question", str(question_id))

        # Don't allow updating content_hash directly
        updates.pop("content_hash", None)
        updated = await self.question_repo.update(question_id, updates)
        if updated is None:
            raise NotFoundError("Question", str(question_id))
        return updated

    async def delete_question(self, question_id: UUID) -> bool:
        return await self.question_repo.soft_delete(question_id)

    # ── Classification ────────────────────────────────────────────

    async def classify_question(self, question_id: UUID) -> dict:
        """Re-classify an existing question via LLM."""
        question = await self.get_question(question_id)

        result = await llm_gateway.chat_json_with_prompt(
            "question_classification",
            variables={"title": question.title, "content": question.content[:3000]},
            temperature=0.3,
        )

        # Update the question with classification results
        updates = {}
        if "question_type" in result:
            updates["question_type"] = result["question_type"]
        if "domain_type" in result:
            updates["domain_type"] = result["domain_type"]
        if "difficulty_level" in result:
            updates["difficulty_level"] = result["difficulty_level"]
        if "difficulty_score" in result:
            updates["difficulty_score"] = result["difficulty_score"]

        if updates:
            await self.question_repo.update(question_id, updates)

        # Process tags if provided
        tags = result.get("tags", [])
        if tags:
            await self._assign_tags(question_id, tags)

        return result

    async def _assign_tags(self, question_id: UUID, tag_names: list[str]) -> None:
        """Create or find tags and link them to the question."""
        for name in tag_names[:5]:  # max 5
            tag = await self.tag_repo.get_by_name(name)
            if tag is None:
                tag = Tag(name=name, tag_type="custom")
                tag = await self.tag_repo.create(tag)

            qt = QuestionTag(question_id=question_id, tag_id=tag.id, source_type="ai")
            self.session.add(qt)

    # ── Knowledge nodes ───────────────────────────────────────────

    async def link_to_knowledge_nodes(
        self,
        question_id: UUID,
        node_ids: list[UUID],
        *,
        relation_type: str = "related",
        confidence: float | None = None,
    ) -> list[QuestionKnowledgeNode]:
        """Link a question to existing knowledge nodes."""
        links: list[QuestionKnowledgeNode] = []
        for node_id in node_ids:
            node = await self.knowledge_node_repo.get_by_id(node_id)
            if node is None:
                continue
            link = QuestionKnowledgeNode(
                question_id=question_id,
                knowledge_node_id=node_id,
                relation_type=relation_type,
                confidence=confidence,
            )
            self.session.add(link)
            links.append(link)
        return links

    async def auto_link_knowledge_nodes(self, question_id: UUID) -> list[QuestionKnowledgeNode]:
        """Extract knowledge nodes from the question text and auto-link."""
        question = await self.get_question(question_id)

        # Search for existing nodes that match the question content
        all_nodes = await self.session.exec(
            __import__("sqlalchemy").select(KnowledgeNode).where(KnowledgeNode.deleted_at.is_(None) if hasattr(KnowledgeNode, "deleted_at") else True)
        )
        nodes = all_nodes.all()

        # Simple keyword matching for MVP — in production, use vector similarity
        question_text = f"{question.title} {question.content}".lower()
        matched_nodes = []
        for node in nodes:
            if node.name.lower() in question_text:
                matched_nodes.append(node)

        return await self.link_to_knowledge_nodes(
            question_id,
            [n.id for n in matched_nodes[:5]],
            relation_type="related",
            confidence=0.5,
        )

    # ── Vector search ─────────────────────────────────────────────

    async def semantic_search(self, query: str, *, top_k: int = 10) -> list[dict]:
        """Search questions by semantic similarity using embeddings."""
        embeddings = await llm_gateway.embed([query])
        if not embeddings:
            return []

        results = await self.vector_store.search_similar(
            query_embedding=embeddings[0],
            limit=top_k,
        )
        return results

    async def search_similar_questions(self, question_id: UUID, *, limit: int = 10) -> list[dict]:
        """Find semantically similar questions via pgvector."""
        question = await self.get_question(question_id)
        text = f"{question.title}. {question.content[:500]}"
        embeddings = await llm_gateway.embed([text])
        if not embeddings:
            return []

        return await self.vector_store.search_similar(
            query_embedding=embeddings[0],
            limit=limit,
        )

    async def embed_question(self, question_id: UUID) -> None:
        """Generate and store an embedding for a question."""
        question = await self.get_question(question_id)
        text = f"{question.title}. {question.content[:500]}"
        embeddings = await llm_gateway.embed([text])
        if embeddings:
            await self.vector_store.upsert(question_id, embeddings[0])
