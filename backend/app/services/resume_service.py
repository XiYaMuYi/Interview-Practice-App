"""Resume service — upload, parse, and manage resume records."""

from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.models import Resume, ResumeExperience
from app.infra.llm.gateway import llm_gateway
from app.infra.parsers.pdf_parser import PDFParser
from app.infra.parsers.word_parser import WordParser
from app.infra.parsers.text_parser import TextParser
from app.infra.repositories.base import BaseRepository
from app.infra.storage import storage

logger = get_logger(__name__)

# Parser registry by file extension
_PARSERS = {
    ".pdf": PDFParser(),
    ".docx": WordParser(),
    ".doc": WordParser(),
    ".txt": TextParser(),
    ".md": TextParser(),
}


class ResumeService:
    """Business logic for resume upload, parsing, and CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.resume_repo = BaseRepository(Resume, session)
        self.experience_repo = BaseRepository(ResumeExperience, session)

    # ── Upload ──────────────────────────────────────────────────────

    async def upload_resume(self, file_name: str, content: bytes) -> Resume:
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

        resume.parse_status = "processing"
        await self.session.flush()

        try:
            result = await llm_gateway.chat_json_with_prompt(
                "resume_parsing",
                variables={"resume_text": resume.raw_text[:20000] if resume.raw_text else ""},
                temperature=0.1,
            )

            # Update resume with structured summary
            resume.structured_summary = result.get("summary", {})
            resume.model_version = llm_gateway.model_name
            resume.prompt_version = "1.0"
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

            return {
                "resume_id": resume_id,
                "parse_status": resume.parse_status,
                "structured_summary": resume.structured_summary,
                "experiences_count": len(saved_experiences),
            }

        except Exception as e:
            resume.parse_status = "failed"
            resume.extra_data = {"error": str(e)}
            await self.session.flush()
            logger.error(f"Resume parsing failed for {resume_id}: {e}")
            raise

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

    async def delete_resume(self, resume_id: UUID) -> bool:
        return await self.resume_repo.soft_delete(resume_id)
