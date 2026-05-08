"""Import service — orchestrates file upload, parsing, and question extraction."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ParseError
from app.core.logging import get_logger
from app.domain.enums import ParseStatus, SourceType
from app.domain.models import File, Question, QuestionKnowledgeNode
from app.infra.llm.gateway import llm_gateway
from app.infra.parsers import ParserFactory
from app.infra.repositories import FileRepository, KnowledgeNodeRepository, QuestionRepository
from app.infra.storage import storage

logger = get_logger(__name__)


class ImportService:
    """Orchestrates the import pipeline: store → parse → extract → persist."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.file_repo = FileRepository(session)
        self.question_repo = QuestionRepository(session)
        self.knowledge_node_repo = KnowledgeNodeRepository(session)

    # ── Text paste import ─────────────────────────────────────────

    async def import_text(self, text: str, *, source_type: str = "paste") -> dict:
        """Import questions from pasted text."""
        if not text.strip():
            raise ParseError("Empty text provided")

        logger.info(f"Importing text: {len(text)} chars, source={source_type}")

        # Extract questions via LLM
        extracted = await self._extract_questions(text)

        # Extract knowledge nodes
        knowledge_nodes = await self._extract_knowledge_nodes(text)

        # Save questions
        saved_questions = []
        for q_data in extracted:
            question = await self._save_question(q_data, text[:200], source_type=source_type)
            saved_questions.append(question)

        return {
            "questions_extracted": len(saved_questions),
            "knowledge_nodes": len(knowledge_nodes),
            "question_ids": [str(q.id) for q in saved_questions],
        }

    # ── File upload import ────────────────────────────────────────

    async def import_file(self, file_name: str, content: bytes) -> dict:
        """Import questions from an uploaded file."""
        # 1. Save file
        relative_path = await storage.save(file_name, content)
        absolute_path = storage.absolute_path(relative_path)

        # 2. Compute hash and check for duplicates
        parser = ParserFactory.get_parser(absolute_path)
        file_hash = parser.compute_hash(absolute_path)

        existing = await self.file_repo.get_by_hash(file_hash)
        if existing:
            logger.info(f"Duplicate file detected (hash={file_hash[:8]}...), returning existing record")
            return {"message": "File already imported", "file_id": str(existing.id)}

        # 3. Create file record (pending status)
        file_record = File(
            file_name=file_name,
            file_path=relative_path,
            file_type=absolute_path.suffix.lower().lstrip("."),
            source_type=SourceType.upload.value,
            parse_status=ParseStatus.pending.value,
            file_hash=file_hash,
        )
        file_record = await self.file_repo.create(file_record)

        # 4. Parse file
        file_record.parse_status = ParseStatus.processing.value
        await self.session.flush()

        try:
            text = await parser.parse(absolute_path)
            file_record.parse_status = ParseStatus.success.value
            await self.session.flush()
        except Exception as e:
            file_record.parse_status = ParseStatus.failed.value
            file_record.parse_error = str(e)
            await self.session.flush()
            raise ParseError(f"Failed to parse '{file_name}': {e}")

        # 5. Extract and save questions
        extracted = await self._extract_questions(text)
        knowledge_nodes = await self._extract_knowledge_nodes(text)

        saved_questions = []
        for q_data in extracted:
            question = await self._save_question(q_data, text[:200], source_type=SourceType.upload.value, source_ref=str(file_record.id))
            saved_questions.append(question)

        return {
            "file_id": str(file_record.id),
            "file_name": file_name,
            "parse_status": file_record.parse_status,
            "questions_extracted": len(saved_questions),
            "knowledge_nodes": len(knowledge_nodes),
            "question_ids": [str(q.id) for q in saved_questions],
        }

    # ── Internal helpers ──────────────────────────────────────────

    async def _extract_questions(self, text: str) -> list[dict]:
        """Call LLM to extract questions from text."""
        try:
            result = await llm_gateway.chat_json_with_prompt(
                "question_extraction",
                variables={"text": text[:10000]},  # Truncate to avoid token limits
                temperature=0.3,
            )
            # Handle both array-at-top-level and {"questions": [...]} formats
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "questions" in result:
                return result["questions"]
            return []
        except Exception as e:
            logger.warning(f"Question extraction failed: {e}")
            return []

    async def _extract_knowledge_nodes(self, text: str) -> list[dict]:
        """Call LLM to extract knowledge nodes from text."""
        try:
            result = await llm_gateway.chat_json_with_prompt(
                "knowledge_node_extraction",
                variables={"text": text[:10000]},
                temperature=0.3,
            )
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.warning(f"Knowledge node extraction failed: {e}")
            return []

    async def _save_question(
        self,
        q_data: dict,
        source_excerpt: str,
        *,
        source_type: str = "paste",
        source_ref: str | None = None,
    ) -> Question:
        """Persist a single extracted question to the database."""
        import hashlib

        content = q_data.get("content", q_data.get("title", ""))
        title = q_data.get("title", content[:80])
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Check for duplicates by hash
        existing = await self.question_repo.list(filters={"content_hash": content_hash})
        if existing:
            return existing[0]

        question = Question(
            title=title[:500],
            content=content,
            content_hash=content_hash,
            source_type=source_type,
            source_ref=source_ref,
            source_excerpt=source_excerpt[:500] if source_excerpt else None,
            question_type=q_data.get("question_type"),
            domain_type=q_data.get("domain_type"),
            difficulty_level=q_data.get("difficulty_level"),
            model_version=llm_gateway.model_name,
            prompt_version="1.0",
        )
        return await self.question_repo.create(question)
