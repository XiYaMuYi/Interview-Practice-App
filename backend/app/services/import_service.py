"""Import service — orchestrates file upload, parsing, and question extraction."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ParseError
from app.core.logging import get_logger
from app.domain.enums import ParseStatus, SourceType
from app.domain.models import File, Question, QuestionKnowledgeNode
from app.infra.data_isolation import UserContext, ensure_owned_by
from app.infra.events.event_publisher import event_publisher
from app.infra.events.event_types import CHUNK_PROCESSED, QUESTION_GENERATED
from app.infra.llm.gateway import llm_gateway
from app.infra.messaging.queue_service import QUEUE_IMPORT_EXTRACT, publish_to_queue
from app.infra.parsers import ParserFactory
from app.infra.repositories import FileRepository, KnowledgeNodeRepository, QuestionRepository
from app.infra.storage import storage

logger = get_logger(__name__)


def _extract_prompt_version() -> str:
    """Derive prompt_version from the question_extraction template."""
    from app.infra.llm.prompt_registry import prompt_registry
    tpl = prompt_registry.get_template("question_extraction")
    return tpl.version if tpl else "1.0"


def chunk_import_text(text: str, chunk_size: int = 3000) -> list[str]:
    """Split import text into chunks for incremental question extraction.

    Priority:
    1. Split by question number patterns (1. 2. 3. or 一、二、三、)
    2. Split by blank lines + question marks
    3. Fallback: fixed-size chunks

    Max chunk size: 5000 chars.
    """
    import re

    # Strategy 1: split by numbered question markers
    pattern = r'(?=(?:^|\n\n)\s*(?:\d+[.、）)]|第[一二三四五六七八九十\d]+[题部分]))'
    segments = re.split(pattern, text, flags=re.MULTILINE)
    segments = [s.strip() for s in segments if s.strip()]

    if len(segments) > 1 and max(len(s) for s in segments) <= 5000:
        # Good split by question numbers
        chunks = []
        current = ""
        for seg in segments:
            if len(current) + len(seg) > chunk_size and current:
                chunks.append(current)
                current = seg
            else:
                current = current + "\n\n" + seg if current else seg
        if current:
            chunks.append(current)
        return chunks

    # Strategy 2: split by double newlines (paragraphs), group into chunks
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text]

    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current)
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current:
        chunks.append(current)

    # Cap at 5000 chars per chunk
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > 5000:
            for i in range(0, len(chunk), 4000):
                final_chunks.append(chunk[i:i+5000])
        else:
            final_chunks.append(chunk)

    return final_chunks


class ImportService:
    """Orchestrates the import pipeline: store → parse → extract → persist."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.file_repo = FileRepository(session)
        self.question_repo = QuestionRepository(session)
        self.knowledge_node_repo = KnowledgeNodeRepository(session)

    # ── Text paste import ─────────────────────────────────────────

    async def import_text(self, text: str, *, source_type: str = "paste", user_ctx: UserContext | None = None) -> dict:
        """Import questions from pasted text."""
        if not text.strip():
            raise ParseError("Empty text provided")

        logger.info(f"Importing text: {len(text)} chars, source={source_type}")

        # Extract questions via LLM
        extracted = await self._extract_questions(text)

        # Extract knowledge nodes (non-fatal if this fails)
        try:
            knowledge_nodes = await self._extract_knowledge_nodes(text)
        except Exception as e:
            logger.warning(f"Knowledge node extraction failed (non-fatal): {e}")
            knowledge_nodes = []

        # Save questions
        saved_questions = []
        for q_data in extracted:
            try:
                question = await self._save_question(q_data, text[:200], source_type=source_type, user_ctx=user_ctx)
                saved_questions.append(question)
            except Exception as e:
                logger.warning(f"Failed to save question (non-fatal): {e}")
                continue

        return {
            "questions_extracted": len(saved_questions),
            "knowledge_nodes": len(knowledge_nodes),
            "question_ids": [str(q.id) for q in saved_questions],
        }

    # ── Streaming text import ─────────────────────────────────────

    async def import_text_stream(
        self, text: str, source_type: str = "paste", user_ctx: UserContext | None = None
    ) -> tuple[UUID, "AsyncGenerator[str, None]"]:
        """Stream text import with SSE events.

        Returns (task_id, event_generator).
        """
        import asyncio
        import json
        import time
        from typing import AsyncGenerator

        from app.services.task_manager import TaskManager, sse_event_stream

        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        if not text.strip():
            raise ValueError("Empty text provided")

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="import_extract", source_id=None
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                # Phase: chunking
                await task_manager.update_task(
                    task_id, status="processing", progress=0.05, current_phase="chunking"
                )
                yield _sse("progress", {
                    "task_id": str(task_id), "phase": "chunking",
                    "progress": 0.05, "current": "正在切分文本...",
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

                chunks = chunk_import_text(text)
                await task_manager.update_task(
                    task_id, total_chunks=len(chunks), progress=0.10
                )
                yield _sse("progress", {
                    "task_id": str(task_id), "phase": "chunking",
                    "progress": 0.10, "current": f"已切分为 {len(chunks)} 个区块",
                    "total_chunks": len(chunks),
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

                total_questions = 0
                failed_chunks = 0

                for i, chunk in enumerate(chunks):
                    chunk_progress = 0.10 + (0.85 * (i + 1) / len(chunks))
                    await task_manager.update_task(
                        task_id, progress=chunk_progress, current_phase="extracting",
                        processed_chunks=i
                    )
                    yield _sse("progress", {
                        "task_id": str(task_id), "phase": "extracting",
                        "progress": round(chunk_progress, 2),
                        "current": f"正在提取第 {i+1}/{len(chunks)} 块...",
                        "elapsed": round(time.monotonic() - start_time, 1),
                    })

                    try:
                        extracted = await self._extract_questions(chunk)
                        for q_data in extracted:
                            try:
                                question = await self._save_question(
                                    q_data, chunk[:200], source_type=source_type, user_ctx=user_ctx
                                )
                                total_questions += 1
                                yield _sse("question_saved", {
                                    "task_id": str(task_id),
                                    "question_id": str(question.id),
                                    "content": question.content[:100],
                                    "total_generated": total_questions,
                                })
                                # Publish event
                                try:
                                    await event_publisher.publish(QUESTION_GENERATED, {
                                        "task_id": str(task_id),
                                        "question_id": str(question.id),
                                        "content_preview": question.content[:100],
                                        "total_generated": total_questions,
                                    })
                                except Exception:
                                    pass
                            except Exception as e:
                                logger.warning(f"Failed to save question: {e}")
                    except Exception as e:
                        failed_chunks += 1
                        logger.warning(f"Chunk {i} extraction failed: {e}")
                        yield _sse("error", {
                            "task_id": str(task_id),
                            "error": f"Block {i+1} failed: {str(e)[:200]}",
                            "recoverable": True,
                        })

                    await task_manager.update_task(task_id, processed_chunks=i + 1)
                    # Publish chunk processed event
                    try:
                        await event_publisher.publish(CHUNK_PROCESSED, {
                            "task_id": str(task_id),
                            "chunk_index": i + 1,
                            "total_chunks": len(chunks),
                        })
                    except Exception:
                        pass

                if total_questions > 0:
                    await task_manager.update_task(
                        task_id, status="done", progress=1.0
                    )
                    yield _sse("done", {
                        "task_id": str(task_id), "status": "done",
                        "total_questions": total_questions,
                        "elapsed": round(time.monotonic() - start_time, 1),
                    })
                else:
                    await task_manager.update_task(
                        task_id, status="failed", progress=0.0,
                        error_message="No questions extracted"
                    )
                    yield _sse("error", {
                        "task_id": str(task_id),
                        "error": "No questions could be extracted",
                        "recoverable": False,
                    })

            except asyncio.CancelledError:
                logger.warning(f"Stream import cancelled for task {task_id}, marking as failed")
                try:
                    await task_manager.update_task(
                        task_id, status="failed", progress=0.0,
                        error_message="Connection cancelled"
                    )
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"Stream import failed: {e}")
                await task_manager.update_task(
                    task_id, status="failed", progress=0.0,
                    error_message=str(e)[:500]
                )
                yield _sse("error", {
                    "task_id": str(task_id),
                    "error": str(e), "recoverable": False,
                })

        return task_id, _event_generator()

    # ── File upload import ────────────────────────────────────────

    async def import_file(self, file_name: str, content: bytes, *, user_ctx: UserContext | None = None) -> dict:
        """Import questions from an uploaded file."""
        # 1. Save file
        relative_path = await storage.save(file_name, content)
        absolute_path = storage.absolute_path(relative_path)

        # 2. Compute hash and check for duplicates
        parser = ParserFactory.get_parser(absolute_path)
        file_hash = parser.compute_hash(absolute_path)

        existing = await self.file_repo.get_by_hash(file_hash)
        if existing:
            # Reuse existing file record — re-parse and re-extract.
            # The global content_hash dedup in _save_question() will skip
            # already-existing questions, so this is safe as an incremental import:
            # existing questions are preserved, new ones get added.
            file_record = existing
            logger.info(
                f"File hash match (hash={file_hash[:8]}...), re-extracting "
                f"(existing questions will be deduped by content_hash)"
            )
        else:
            # 3. Create new file record (pending status)
            file_record = File(
                user_id=user_ctx.user_id if user_ctx else None,
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
            question = await self._save_question(q_data, text[:200], source_type=SourceType.upload.value, source_ref=str(file_record.id), user_ctx=user_ctx)
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
        """Call LLM to extract questions from text.

        For long documents (>30K chars), splits into overlapping chunks and
        extracts questions from each chunk, then deduplicates by content.
        """
        try:
            CHUNK_SIZE = 30000
            OVERLAP = 3000  # Overlap to avoid splitting mid-question

            if len(text) <= CHUNK_SIZE:
                chunks = [text]
            else:
                chunks = []
                start = 0
                while start < len(text):
                    end = start + CHUNK_SIZE
                    if end < len(text):
                        # Find a good split point (newline) within the overlap zone
                        search_start = max(start, end - OVERLAP)
                        newline_pos = text.rfind("\n", search_start, end)
                        if newline_pos > start:
                            end = newline_pos + 1
                    chunks.append(text[start:end])
                    start = end - OVERLAP if end < len(text) else end

            logger.info(f"Question extraction: {len(chunks)} chunk(s) from {len(text)} chars")

            all_questions = []
            for i, chunk in enumerate(chunks):
                result = await llm_gateway.chat_json_with_prompt(
                    "question_extraction",
                    variables={"text": chunk},
                    temperature=0.3,
                )
                if isinstance(result, list):
                    all_questions.extend(result)
                elif isinstance(result, dict) and "questions" in result:
                    all_questions.extend(result["questions"])

            # Deduplicate by content
            seen_contents = set()
            unique_questions = []
            for q in all_questions:
                content = q.get("content", q.get("title", ""))
                if content not in seen_contents:
                    seen_contents.add(content)
                    unique_questions.append(q)

            if len(unique_questions) < len(all_questions):
                logger.info(
                    f"Deduplicated questions: {len(all_questions)} -> {len(unique_questions)} "
                    f"(removed {len(all_questions) - len(unique_questions)} duplicates)"
                )

            return unique_questions
        except Exception as e:
            logger.warning(f"Question extraction failed: {e}")
            return []

    async def _extract_knowledge_nodes(self, text: str) -> list[dict]:
        """Call LLM to extract knowledge nodes from text."""
        try:
            # Use same chunking strategy as question extraction for long docs
            CHUNK_SIZE = 30000
            OVERLAP = 3000

            if len(text) <= CHUNK_SIZE:
                chunks = [text]
            else:
                chunks = []
                start = 0
                while start < len(text):
                    end = start + CHUNK_SIZE
                    if end < len(text):
                        search_start = max(start, end - OVERLAP)
                        newline_pos = text.rfind("\n", search_start, end)
                        if newline_pos > start:
                            end = newline_pos + 1
                    chunks.append(text[start:end])
                    start = end - OVERLAP if end < len(text) else end

            all_nodes = []
            for chunk in chunks:
                result = await llm_gateway.chat_json_with_prompt(
                    "knowledge_node_extraction",
                    variables={"text": chunk},
                    temperature=0.3,
                )
                if isinstance(result, list):
                    all_nodes.extend(result)

            # Deduplicate by node name
            seen_names = set()
            unique_nodes = []
            for node in all_nodes:
                name = node.get("name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    unique_nodes.append(node)

            return unique_nodes
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
        user_ctx: UserContext | None = None,
    ) -> Question:
        """Persist a single extracted question to the database.

        Deduplication strategy (two-tier):
        1. Global dedup: check by content_hash across ALL sources. If a
           question with the same content already exists anywhere, return it.
           This prevents duplicate questions from paste / upload / cross-resume
           imports.
        2. Resume-scoped dedup (legacy): if source_type == "resume" AND a
           matching question exists with the same source_ref, return that one.
        """
        import hashlib

        content = q_data.get("content", q_data.get("title", ""))
        title = q_data.get("title", content[:80])
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Tier 1: Global dedup — same content anywhere → skip
        existing_global = await self.question_repo.list(
            filters={"content_hash": content_hash}
        )
        if existing_global:
            logger.info(
                f"Global dedup hit: content_hash={content_hash[:12]}... "
                f"source_type={source_type}, returning existing question {existing_global[0].id}"
            )
            return existing_global[0]

        # Tier 2: Resume-scoped dedup (belt-and-suspenders)
        if source_ref and source_type == "resume":
            existing_resume = await self.question_repo.list(
                filters={"content_hash": content_hash, "source_ref": source_ref}
            )
            if existing_resume:
                logger.info(
                    f"Resume-scoped dedup hit: content_hash={content_hash[:12]}... "
                    f"source_ref={source_ref[:12]}..., returning existing question {existing_resume[0].id}"
                )
                return existing_resume[0]

        question = Question(
            user_id=user_ctx.user_id if user_ctx else None,
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
            prompt_version=_extract_prompt_version(),
        )
        return await self.question_repo.create(question)

    # ── File listing / ownership ─────────────────────────────────────

    async def list_files(self, *, user_ctx: UserContext | None = None, offset: int = 0, limit: int = 50) -> list[File]:
        """List files filtered by user context. Admin sees all."""
        filters: dict = {}
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                filters["user_id"] = None
            else:
                filters["__user_filter_mode"] = "owned_or_public"
                filters["__user_id"] = user_ctx.user_id
        return list(
            await self.file_repo.list(filters=filters, offset=offset, limit=limit)
        )

    async def get_file(self, file_id: UUID, *, user_ctx: UserContext | None = None) -> File | None:
        """Get a file by ID, checking ownership."""
        file = await self.file_repo.get_by_id(file_id)
        if file is None:
            return None
        if user_ctx is None or user_ctx.is_admin:
            return file
        ensure_owned_by(user_ctx, file.user_id, "file")
        return file

    # ── Async (Queue-based) Import ─────────────────────────────────

    async def import_text_stream_async(self, text: str, source_type: str = "paste", *, user_ctx: UserContext | None = None) -> dict:
        """Submit text import to RabbitMQ queue instead of synchronous SSE.

        Returns a task_id that can be used to track progress.
        Falls back to the synchronous stream if RabbitMQ is unavailable.
        """
        from app.services.task_manager import TaskManager

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="import_extract_async", source_id=None
        )

        await task_manager.update_task(task.id, status="processing", progress=0.05, current_phase="queued")

        published = await publish_to_queue(
            QUEUE_IMPORT_EXTRACT,
            message={
                "task_id": str(task.id),
                "text_preview": text[:500],
                "source_type": source_type,
            },
        )

        if not published:
            logger.warning("RabbitMQ unavailable, falling back to sync import_text_stream")
            return await self.import_text_stream(text, source_type)

        logger.info(f"Import extract task {task.id} submitted to queue {QUEUE_IMPORT_EXTRACT}")
        return {"task_id": str(task.id), "queued": True}
