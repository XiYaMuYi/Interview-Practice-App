"""Resume service — upload, parse, and manage resume records."""

import asyncio
import re
import time
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.models import Resume, ResumeExperience
from app.infra.cache.cache_service import TTL_SUMMARY, delete_cache, get_cache, set_cache
from app.infra.events.event_publisher import event_publisher
from app.infra.events.event_types import TASK_DONE
from app.infra.llm.gateway import llm_gateway
from app.infra.llm.prompt_registry import prompt_registry
from app.infra.messaging.queue_service import QUEUE_RESUME_PARSE, publish_to_queue
from app.infra.parsers.pdf_parser import PDFParser
from app.infra.parsers.word_parser import WordParser
from app.infra.parsers.text_parser import TextParser
from app.infra.repositories.base import BaseRepository
from app.infra.storage import storage
from app.services.task_manager import TaskManager

logger = get_logger(__name__)

# Parser registry by file extension
_PARSERS = {
    ".pdf": PDFParser(),
    ".docx": WordParser(),
    ".doc": WordParser(),
    ".txt": TextParser(),
    ".md": TextParser(),
}


# ── Section keywords for chunking ──

_SECTION_KEYWORDS = {
    "experience": [
        "工作经历", "工作经验", "工作背景",
        "实习经历", "实习经验",
    ],
    "education": [
        "教育背景", "教育经历",
    ],
    "project": [
        "项目经验", "项目经历",
    ],
    "skills": [
        "专业技能", "技能特长", "技术栈",
    ],
    "other": [
        "个人优势", "自我评价", "自我介绍", "获奖情况",
    ],
}


def chunk_resume_text(text: str) -> list[dict]:
    """Split resume text into logical chunks by section keywords.

    Uses regex to split on common resume section headers like
    work experience, education, projects, skills.
    Falls back to paragraph-based chunking if no headers found.

    Returns list of {"type": str, "text": str} dicts.
    """
    # Build a combined regex pattern for all section keywords
    all_keywords = []
    for chunk_type, keywords in _SECTION_KEYWORDS.items():
        for kw in keywords:
            all_keywords.append((kw, chunk_type))

    # Find all section header positions
    pattern = "|".join(re.escape(kw) for kw, _ in all_keywords)
    matches = list(re.finditer(pattern, text))

    if not matches:
        # Fallback: split by paragraphs, group every 3-5 paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [{"type": "other", "text": text}]

        chunks = []
        group_size = min(5, max(3, len(paragraphs) // 3)) or 3
        for i in range(0, len(paragraphs), group_size):
            group = paragraphs[i : i + group_size]
            chunks.append({"type": "other", "text": "\n\n".join(group)})
        return chunks

    # Split text by section headers
    chunks = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()

        # Determine chunk type from the matched keyword
        matched_kw = match.group(0)
        chunk_type = "other"
        for kw, ctype in all_keywords:
            if kw == matched_kw:
                chunk_type = ctype
                break

        chunks.append({"type": chunk_type, "text": section_text})

    return chunks


# ── Streaming helpers ──


def _sse(event_type: str, data: dict) -> str:
    """Format a dict as an SSE event string."""
    import json
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _chunk_type_label(chunk_type: str) -> str:
    """Map internal chunk type to user-facing label."""
    labels = {
        "experience": "工作经历",
        "education": "教育背景",
        "project": "项目经历",
        "skills": "专业技能",
        "other": "其他内容",
    }
    return labels.get(chunk_type, chunk_type)


class ResumeService:
    """Business logic for resume upload, parsing, and CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.resume_repo = BaseRepository(Resume, session)
        self.experience_repo = BaseRepository(ResumeExperience, session)

    # ── Upload ──────────────────────────────────────────────────────

    async def upload_resume(self, file_name: str, content: bytes, *, user_id: str | None = None) -> Resume:
        """Save uploaded file and create a resume record."""
        relative_path = await storage.save(file_name, content, subfolder="resumes")
        absolute_path = storage.absolute_path(relative_path)

        # Extract text using the appropriate parser
        suffix = Path(file_name).suffix.lower()
        parser = _PARSERS.get(suffix)
        raw_text: str | None = None
        if parser is not None:
            try:
                raw_text = await parser.parse(absolute_path)  # type: ignore[union-attr]
            except Exception as e:
                logger.warning(f"Parser failed for {file_name}: {e}")
        else:
            logger.warning(f"Unsupported file type: {suffix}")

        resume = Resume(
            user_id=user_id,
            file_name=file_name,
            file_path=relative_path,
            source_type="upload",
            parse_status="pending" if raw_text else "failed",
            raw_text=raw_text[:50000] if raw_text else None,
        )
        return await self.resume_repo.create(resume)

    # ── Parse ───────────────────────────────────────────────────────

    async def parse_resume(self, resume_id: UUID) -> dict:
        """Parse a resume using LLM and extract structured data."""
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None or resume.deleted_at is not None:
            raise NotFoundError("Resume", str(resume_id))

        # Check cache first
        cache_key = f"app:resume:summary:{resume_id}"
        cached = await get_cache(cache_key)
        if cached is not None:
            logger.info(f"Resume summary cache HIT: {resume_id}")
            return cached

        resume.parse_status = "processing"
        await self.session.flush()

        try:
            result = await llm_gateway.chat_json_with_prompt(
                "resume_parsing",
                variables={"text": resume.raw_text[:20000] if resume.raw_text else ""},
                temperature=0.1,
            )

            # Update resume with structured summary
            resume.structured_summary = result.get("summary", {})
            resume.model_version = llm_gateway.model_name
            resume_tpl = prompt_registry.get_template("resume_parsing")
            resume.prompt_version = resume_tpl.version if resume_tpl else "1.0"
            resume.parse_status = "parsed"
            await self.session.flush()

            # Extract experiences
            experiences_data = result.get("experiences", [])
            saved_experiences = []
            for exp_data in experiences_data[:20]:  # max 20 experiences
                exp = ResumeExperience(
                    resume_id=resume_id,
                    experience_type=exp_data.get("experience_type", "work"),
                    company_or_project=exp_data.get("company_or_project"),
                    role_title=exp_data.get("role_title"),
                    start_date=exp_data.get("start_date"),
                    end_date=exp_data.get("end_date"),
                    description=exp_data.get("description"),
                    tech_stack=exp_data.get("tech_stack"),
                    extracted_keywords=exp_data.get("extracted_keywords"),
                    confidence=exp_data.get("confidence"),
                )
                saved_experiences.append(exp)

            if saved_experiences:
                self.session.add_all(saved_experiences)
                await self.session.flush()

            result = {
                "resume_id": resume_id,
                "parse_status": resume.parse_status,
                "structured_summary": resume.structured_summary,
                "experiences_count": len(saved_experiences),
                "model_version": resume.model_version,
                "prompt_version": resume.prompt_version,
            }

            # Cache the summary
            try:
                await set_cache(cache_key, result, ttl=TTL_SUMMARY)
            except Exception:
                pass  # Graceful fallback

            # Publish task done event
            try:
                await event_publisher.publish(TASK_DONE, {
                    "task_id": None,
                    "task_type": "resume_parse",
                    "source_id": str(resume_id),
                    "experiences_count": len(saved_experiences),
                })
            except Exception:
                pass

            return result

        except Exception as e:
            resume.parse_status = "parsing_failed"
            resume.extra_data = {"error": str(e)}
            await self.session.flush()
            logger.error(f"Resume parsing failed for {resume_id}: {e}")
            return {
                "resume_id": resume_id,
                "parse_status": resume.parse_status,
                "structured_summary": None,
                "experiences_count": 0,
                "model_version": None,
                "prompt_version": None,
                "error": str(e),
            }

    # ── Streaming Parse ─────────────────────────────────────────────

    async def parse_resume_stream(
        self,
        resume_id: UUID,
        *,
        generate_questions: bool = False,
        max_questions: int = 20,
    ) -> tuple[UUID, AsyncGenerator]:
        """Create a streaming parse task for a resume.

        Returns (task_id, event_generator) where event_generator yields SSE events.

        When generate_questions=True, the pipeline continues into question
        generation after parsing completes (content production + interview
        asset pipeline in one stream).

        Events emitted:
        - progress: {"phase": str, "progress": float, "current": str, "elapsed": float}
        - chunk_saved: {"chunk_index": int, "chunk_type": str, "total": int}
        - question_saved: {"question_id": str, "total_generated": int}  (when generate_questions=True)
        - done: {"task_id": str, "status": str}
        - error: {"error": str, "recoverable": bool}
        """
        import json

        start_time = time.monotonic()
        task_manager = TaskManager(self.session)

        # 1. Read resume record
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None or resume.deleted_at is not None:
            raise NotFoundError("Resume", str(resume_id))

        if not resume.raw_text:
            raise NotFoundError("Resume has no extracted text", str(resume_id))

        raw_text = resume.raw_text

        # 2. Create task
        task = await task_manager.create_task(
            task_type="resume_parse", source_id=str(resume_id)
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                # 3. Push progress: reading
                await task_manager.update_task(
                    task_id, status="running", progress=0.05, current_phase="reading"
                )
                yield _sse("progress", {
                    "task_id": str(task_id),
                    "phase": "reading",
                    "progress": 0.05,
                    "current": "正在读取简历...",
                    "elapsed": time.monotonic() - start_time,
                })

                # 4. Update resume parse_status
                resume.parse_status = "processing"
                await self.session.flush()

                # 5. Chunk the resume text
                chunks = chunk_resume_text(raw_text)

                # 6. Push progress: chunking
                await task_manager.update_task(
                    task_id, progress=0.10, current_phase="chunking", total_chunks=len(chunks)
                )
                yield _sse("progress", {
                    "task_id": str(task_id),
                    "phase": "chunking",
                    "progress": 0.10,
                    "current": f"已切分为 {len(chunks)} 个区块",
                    "elapsed": time.monotonic() - start_time,
                    "total_chunks": len(chunks),
                })

                # 8. Process each chunk
                all_experiences = []
                all_summaries = []
                failed_chunks = 0

                for i, chunk in enumerate(chunks):
                    phase_progress = 0.10 + (0.85 * (i + 1) / len(chunks))
                    chunk_label = _chunk_type_label(chunk["type"])

                    # 8a. Push progress
                    await task_manager.update_task(
                        task_id,
                        progress=phase_progress,
                        current_phase="parsing",
                        processed_chunks=i,
                    )
                    yield _sse("progress", {
                        "task_id": str(task_id),
                        "phase": "parsing",
                        "progress": round(phase_progress, 2),
                        "current": f"正在解析{chunk_label}...",
                        "elapsed": time.monotonic() - start_time,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    })

                    # 8b. Call LLM
                    try:
                        result = await llm_gateway.chat_json_with_prompt(
                            "resume_parsing",
                            variables={"text": chunk["text"]},
                            temperature=0.1,
                        )

                        # 8c. Parse returned JSON
                        summary = result.get("summary", {})
                        experiences_data = result.get("experiences", [])
                        all_summaries.append(summary)

                        # 8d. Create ResumeExperience records
                        for exp_data in experiences_data[:20]:
                            exp = ResumeExperience(
                                resume_id=resume_id,
                                experience_type=exp_data.get("experience_type", chunk["type"]),
                                company_or_project=exp_data.get("company_or_project"),
                                role_title=exp_data.get("role_title"),
                                start_date=exp_data.get("start_date"),
                                end_date=exp_data.get("end_date"),
                                description=exp_data.get("description"),
                                tech_stack=exp_data.get("tech_stack"),
                                extracted_keywords=exp_data.get("extracted_keywords"),
                                confidence=exp_data.get("confidence"),
                            )
                            self.session.add(exp)
                            all_experiences.append(exp)

                        await self.session.flush()

                        # 8e. Push chunk_saved event
                        yield _sse("chunk_saved", {
                            "task_id": str(task_id),
                            "chunk_index": i,
                            "chunk_type": chunk["type"],
                            "experiences_count": len(experiences_data),
                            "total": len(chunks),
                        })

                    except Exception as e:
                        failed_chunks += 1
                        logger.warning(
                            f"Chunk {i} ({chunk['type']}) parsing failed: {e}"
                        )
                        yield _sse("error", {
                            "task_id": str(task_id),
                            "error": f"Chunk {i} failed: {str(e)}",
                            "recoverable": True,
                            "chunk_index": i,
                        })

                    # 8f. Update task processed_chunks
                    await task_manager.update_task(
                        task_id, processed_chunks=i + 1, progress=phase_progress
                    )

                # 9. All chunks completed
                if failed_chunks == len(chunks):
                    # All chunks failed
                    resume.parse_status = "parsing_failed"
                    await self.session.flush()
                    await task_manager.update_task(
                        task_id, status="failed", progress=0.0,
                        error_message="All chunks failed to parse"
                    )
                    yield _sse("error", {
                        "task_id": str(task_id),
                        "error": "All chunks failed to parse",
                        "recoverable": False,
                    })
                else:
                    # At least some chunks succeeded
                    resume.parse_status = "parsed"

                    # Build structured_summary from all summaries
                    merged_summary = {}
                    for s in all_summaries:
                        if s:
                            merged_summary.update(s)
                    if all_experiences:
                        merged_summary["experiences_count"] = len(all_experiences)
                    resume.structured_summary = merged_summary
                    resume.model_version = llm_gateway.model_name
                    resume_tpl = prompt_registry.get_template("resume_parsing")
                    resume.prompt_version = resume_tpl.version if resume_tpl else "1.0"
                    await self.session.flush()

                    if not generate_questions:
                        # Parse complete — question generation is a separate flow.
                        await task_manager.update_task(
                            task_id, status="done", progress=1.0
                        )
                        yield _sse("done", {
                            "task_id": str(task_id),
                            "status": "done",
                            "experiences_count": len(all_experiences),
                            "elapsed": time.monotonic() - start_time,
                        })
                    else:
                        # ── Continue into question generation (delegate to shared helper)
                        yield _sse("progress", {
                            "task_id": str(task_id),
                            "phase": "generating_questions",
                            "progress": 0.90,
                            "current": "解析完成，正在生成面试题目...",
                            "elapsed": round(time.monotonic() - start_time, 1),
                        })

                        # Build question context from experiences
                        context_parts = []
                        if resume.structured_summary:
                            context_parts.append(
                                f"候选人信息：{json.dumps(resume.structured_summary, ensure_ascii=False)}"
                            )
                        for exp in all_experiences:
                            parts = []
                            if exp.company_or_project:
                                parts.append(exp.company_or_project)
                            if exp.role_title:
                                parts.append(exp.role_title)
                            if exp.description:
                                parts.append(exp.description)
                            if exp.tech_stack:
                                parts.append(f"技术栈: {exp.tech_stack}")
                            context_parts.append("\n".join(parts))

                        question_text = "\n\n".join(context_parts)[:10000] if context_parts else raw_text[:5000]

                        async for event in self._generate_and_save_questions_stream(
                            question_text=question_text,
                            raw_text=raw_text,
                            resume_id=resume_id,
                            task_id=task_id,
                            task_manager=task_manager,
                            task_type="resume_parse_with_questions",
                            max_questions=max_questions,
                            start_time=start_time,
                        ):
                            yield event

            except asyncio.CancelledError:
                logger.warning(f"Parse stream cancelled for task {task_id}, marking as failed")
                try:
                    await task_manager.update_task(
                        task_id, status="failed", progress=0.0,
                        error_message="Connection cancelled"
                    )
                except Exception:
                    pass  # Best effort — DB session may also be closed
                raise  # Re-raise so uvicorn can clean up the cancel scope

            except Exception as e:
                logger.error(f"Streaming resume parse failed for {resume_id}: {e}")
                await task_manager.update_task(
                    task_id, status="failed", progress=0.0,
                    error_message=str(e)[:500]
                )
                yield _sse("error", {
                    "task_id": str(task_id),
                    "error": str(e),
                    "recoverable": False,
                })

        return task_id, _event_generator()

    # ── Async (Queue-based) Parse ─────────────────────────────────────

    async def parse_resume_stream_async(self, resume_id: UUID) -> dict:
        """Submit resume parsing to RabbitMQ queue instead of synchronous SSE.

        Returns a task_id that can be used to track progress.
        Falls back to the synchronous stream if RabbitMQ is unavailable.
        """
        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="resume_parse_async", source_id=str(resume_id)
        )

        published = await publish_to_queue(
            QUEUE_RESUME_PARSE,
            message={
                "task_id": str(task.id),
                "resume_id": str(resume_id),
            },
        )

        if not published:
            logger.warning("RabbitMQ unavailable, falling back to sync parse_resume_stream")
            return await self.parse_resume_stream(resume_id)

        logger.info(f"Resume parse task {task.id} submitted to queue {QUEUE_RESUME_PARSE}")
        return {"task_id": str(task.id), "queued": True}

    async def parse_resume_background(self, resume_id: UUID) -> dict:
        """Process resume parsing in the background without SSE.

        This is the consumer-side execution path for RabbitMQ workers.
        """
        result = await self.parse_resume(resume_id)
        return result

    async def _generate_and_save_questions_stream(
        self,
        *,
        question_text: str,
        raw_text: str,
        resume_id: UUID,
        task_id: UUID,
        task_manager,
        task_type: str = "generate_questions",
        max_questions: int = 20,
        start_time: float,
    ) -> AsyncGenerator[str, None]:
        """Shared SSE generator for resume-driven question generation.

        Used by parse_resume_stream (when generate_questions=True),
        regenerate_questions_stream, and generate_questions_from_resume_stream.
        """
        from app.services.import_service import ImportService

        try:
            await task_manager.update_task(
                task_id, status="processing", progress=0.10, current_phase="generating"
            )
            yield _sse("progress", {
                "task_id": str(task_id),
                "phase": "generating",
                "progress": 0.10,
                "current": "正在生成面试题目...",
                "elapsed": round(time.monotonic() - start_time, 1),
            })

            generated = await llm_gateway.chat_json_with_prompt(
                "question_generation",
                variables={"text": question_text},
                temperature=0.7,
            )
            if isinstance(generated, dict) and "questions" in generated:
                generated = generated["questions"]
            if not isinstance(generated, list):
                generated = []

            yield _sse("progress", {
                "task_id": str(task_id),
                "phase": "saving",
                "progress": 0.50,
                "current": f"已生成 {len(generated)} 条题目，正在保存...",
                "elapsed": round(time.monotonic() - start_time, 1),
            })

            import_service = ImportService(self.session)
            total_questions = 0
            skipped = 0

            for q_data in generated:
                try:
                    question = await import_service._save_question(
                        q_data,
                        raw_text[:200],
                        source_type="resume",
                        source_ref=str(resume_id),
                    )
                    total_questions += 1
                    yield _sse("question_saved", {
                        "task_id": str(task_id),
                        "question_id": str(question.id),
                        "content": question.content[:100],
                        "total_generated": total_questions,
                    })
                    if total_questions >= max_questions:
                        break
                except Exception as e:
                    skipped += 1
                    logger.warning(f"Failed to save resume question (non-fatal): {e}")

            await task_manager.update_task(task_id, status="done", progress=1.0)
            yield _sse("done", {
                "task_id": str(task_id),
                "status": "done",
                "questions_generated": total_questions,
                "questions_skipped": skipped,
                "elapsed": round(time.monotonic() - start_time, 1),
            })

        except asyncio.CancelledError:
            logger.warning(f"Generate questions stream cancelled for task {task_id}")
            try:
                await task_manager.update_task(
                    task_id, status="failed", progress=0.0,
                    error_message="Connection cancelled"
                )
            except Exception:
                pass
            raise

        except Exception as e:
            logger.error(f"Generate questions stream failed: {e}")
            await task_manager.update_task(
                task_id, status="failed", progress=0.0,
                error_message=str(e)[:500]
            )
            yield _sse("error", {
                "task_id": str(task_id),
                "error": str(e),
                "recoverable": False,
            })

    # ── CRUD ────────────────────────────────────────────────────────

    async def get_resume(self, resume_id: UUID) -> Resume:
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None or resume.deleted_at is not None:
            raise NotFoundError("Resume", str(resume_id))
        return resume

    async def list_resumes(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Resume]:
        return list(
            await self.resume_repo.list(
                filters={"deleted_at": None},
                offset=offset,
                limit=limit,
            )
        )

    async def list_resumes_with_count(
        self, *, page: int = 1, page_size: int = 20, user_id: str | None = None
    ) -> tuple[list[Resume], int]:
        """List resumes with real total count."""
        from sqlalchemy import func

        offset = (page - 1) * page_size

        # Count non-deleted resumes
        count_stmt = (
            __import__("sqlalchemy")
            .select(func.count())
            .select_from(Resume)
            .where(Resume.deleted_at.is_(None))
        )
        if user_id is not None:
            count_stmt = count_stmt.where(Resume.user_id == user_id)
        total = (await self.session.exec(count_stmt)).scalar_one()

        # Data query
        from sqlalchemy import select as sa_select

        data_stmt = (
            sa_select(Resume)
            .where(Resume.deleted_at.is_(None))
            .offset(offset)
            .limit(page_size)
            .order_by(Resume.created_at.desc())
        )
        if user_id is not None:
            data_stmt = data_stmt.where(Resume.user_id == user_id)
        result = await self.session.exec(data_stmt)
        return list(result.scalars().all()), total

    async def delete_resume(self, resume_id: UUID) -> bool:
        return await self.resume_repo.soft_delete(resume_id)

    async def find_by_user_and_hash(self, user_id: str, file_hash: str) -> Resume | None:
        """Find an existing resume for the same user with identical file hash."""
        from sqlalchemy import select as sa_select
        stmt = sa_select(Resume).where(
            Resume.user_id == user_id,
            Resume.extra_data["file_hash"].astext == file_hash,
            Resume.deleted_at.is_(None),
        ).limit(1)
        result = await self.session.exec(stmt)
        return result.first()

    async def regenerate_questions_stream(
        self,
        resume_id: UUID,
        *,
        count: int = 10,
    ) -> tuple[UUID, AsyncGenerator[str, None]]:
        """Regenerate interview questions from resume_experiences via SSE stream."""
        import json
        import time

        from app.services.task_manager import TaskManager

        start_time = time.monotonic()
        task_manager = TaskManager(self.session)

        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None or resume.deleted_at is not None:
            raise NotFoundError("Resume", str(resume_id))

        # Fetch experiences
        exps = await self.experience_repo.list(filters={"resume_id": resume_id})
        if not exps:
            raise NotFoundError("No experiences found for resume", str(resume_id))

        # Build question context from experiences
        context_parts = []
        if resume.structured_summary:
            context_parts.append(
                f"候选人信息：{json.dumps(resume.structured_summary, ensure_ascii=False)}"
            )
        for exp in exps:
            parts = []
            if exp.company_or_project:
                parts.append(exp.company_or_project)
            if exp.role_title:
                parts.append(exp.role_title)
            if exp.description:
                parts.append(exp.description)
            if exp.tech_stack:
                parts.append(f"技术栈: {exp.tech_stack}")
            context_parts.append("\n".join(parts))

        question_text = "\n\n".join(context_parts)[:10000]
        raw_text = resume.raw_text or ""

        task = await task_manager.create_task(
            task_type="regenerate_questions", source_id=str(resume_id)
        )
        task_id = task.id

        return (
            task_id,
            self._generate_and_save_questions_stream(
                question_text=question_text,
                raw_text=raw_text,
                resume_id=resume_id,
                task_id=task_id,
                task_manager=task_manager,
                task_type="regenerate_questions",
                max_questions=count,
                start_time=start_time,
            ),
        )

    async def generate_questions_from_resume_stream(
        self,
        resume_id: UUID,
        *,
        max_questions: int = 20,
    ) -> tuple[UUID, AsyncGenerator[str, None]]:
        """Generate interview questions from a parsed resume via SSE stream.

        This is the dedicated Content Production entry point for
        resume-driven question bank generation. It is separate from
        resume parsing (parse_resume_stream).
        """
        import json

        start_time = time.monotonic()
        task_manager = TaskManager(self.session)

        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None or resume.deleted_at is not None:
            raise NotFoundError("Resume", str(resume_id))

        if resume.parse_status != "parsed":
            raise ValueError(
                f"Resume must be parsed before generating questions. "
                f"Current status: {resume.parse_status}"
            )

        # Build question context from experiences
        context_parts = []
        if resume.structured_summary:
            context_parts.append(
                f"候选人信息：{json.dumps(resume.structured_summary, ensure_ascii=False)}"
            )

        exps = await self.experience_repo.list(filters={"resume_id": resume_id})
        for exp in exps:
            parts = []
            if exp.company_or_project:
                parts.append(exp.company_or_project)
            if exp.role_title:
                parts.append(exp.role_title)
            if exp.description:
                parts.append(exp.description)
            if exp.tech_stack:
                parts.append(f"技术栈: {exp.tech_stack}")
            context_parts.append("\n".join(parts))

        question_text = "\n\n".join(context_parts)[:10000] if context_parts else (resume.raw_text or "")[:5000]
        raw_text = resume.raw_text or ""

        task = await task_manager.create_task(
            task_type="resume_generate_questions", source_id=str(resume_id)
        )
        task_id = task.id

        return (
            task_id,
            self._generate_and_save_questions_stream(
                question_text=question_text,
                raw_text=raw_text,
                resume_id=resume_id,
                task_id=task_id,
                task_manager=task_manager,
                task_type="resume_generate_questions",
                max_questions=max_questions,
                start_time=start_time,
            ),
        )

    async def list_experiences(self, resume_id: UUID) -> list[ResumeExperience]:
        """List all experiences for a given resume."""
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None or resume.deleted_at is not None:
            raise NotFoundError("Resume", str(resume_id))
        results = await self.experience_repo.list(
            filters={"resume_id": resume_id},
            order_by="created_at",
        )
        return list(results)
