"""Study service - study records, review scheduling, and statistics."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.models import Question, StudyRecord
from app.infra.repositories import StudyRecordRepository

logger = get_logger(__name__)

# SM-2 simplified intervals (in days)
INITIAL_INTERVAL_DAYS = 1
EASY_MULTIPLIER = 2.5
MIN_INTERVAL = 1


class StudyService:
    """Orchestrates study record creation, review scheduling (SM-2), and statistics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.study_repo = StudyRecordRepository(session)

    # - Study Records -

    async def create_study_record(self, data: dict) -> dict:
        """Record a study session."""
        record = StudyRecord(
            question_id=data.get("question_id"),
            study_type=data.get("study_type", "practice"),
            user_answer=data.get("user_answer"),
            ai_score=data.get("ai_score"),
            ai_feedback=data.get("ai_feedback"),
            mastery_level=data.get("mastery_level"),
            duration_seconds=data.get("duration_seconds"),
            review_result=data.get("review_result"),
            extra_data=data.get("extra_data"),
        )
        record = await self.study_repo.create(record)
        logger.info(
            f"Study record created: question={record.question_id}, "
            f"type={record.study_type}, score={record.ai_score}"
        )
        return {
            "id": str(record.id),
            "question_id": str(record.question_id) if record.question_id else None,
            "study_type": record.study_type,
            "reviewed_at": record.reviewed_at.isoformat(),
        }

    async def get_study_records(
        self,
        *,
        question_id: UUID | None = None,
        study_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        """List study records with optional filters."""
        filters = {}
        if study_type:
            filters["study_type"] = study_type

        records = await self.study_repo.list(offset=offset, limit=limit, filters=filters)

        # Filter by question_id if provided (not supported by base repo filters)
        if question_id:
            records = [r for r in records if r.question_id == question_id]

        # Enrich with question titles
        result = []
        for r in records:
            d = self._record_to_dict(r)
            if r.question_id:
                question = await self.session.get(Question, r.question_id)
                d["question_title"] = question.title if question else None
            else:
                d["question_title"] = None
            result.append(d)
        return result

    async def get_records_for_question(self, question_id: UUID) -> list[dict]:
        """Get all study records for a specific question."""
        records = await self.study_repo.list(
            filters={"question_id": question_id}, limit=1000
        )
        return [self._record_to_dict(r) for r in records]

    # - Review Scheduling (SM-2) -

    async def record_review(
        self,
        *,
        question_id: UUID,
        quality: int,
        user_answer: str | None = None,
        duration: int | None = None,
    ) -> dict:
        """Record a review and calculate next review date using simplified SM-2."""
        # Find the last review record for this question
        last_records = await self.study_repo.list(
            filters={"question_id": question_id, "study_type": "review"},
            offset=0,
            limit=1,
        )
        # Get the most recent by ordering desc (base repo returns in insertion order)
        last_record = last_records[0] if last_records else None

        # Calculate interval using SM-2 logic
        interval = self._calculate_interval(quality, last_record)

        next_review = datetime.utcnow() + timedelta(days=interval)

        # Determine review result
        review_result = "mastered" if quality >= 4 else "needs_reinforcement"

        record = StudyRecord(
            question_id=question_id,
            study_type="review",
            user_answer=user_answer,
            ai_score=quality * 20,  # Map 0-5 quality to 0-100 score
            mastery_level=quality,
            duration_seconds=duration,
            review_result=review_result,
            next_review_at=next_review,
            extra_data={"interval_days": interval, "quality": quality},
        )
        record = await self.study_repo.create(record)

        logger.info(
            f"Review recorded: question={question_id}, quality={quality}, "
            f"interval={interval}d, next_review={next_review.date()}"
        )
        return self._record_to_dict(record)

    async def get_review_list(self, *, limit: int = 50) -> list[dict]:
        """Get questions that are due for review."""
        now = datetime.utcnow()
        stmt = (
            select(
                StudyRecord.question_id,
                StudyRecord.next_review_at,
            )
            .where(
                StudyRecord.study_type == "review",
                StudyRecord.question_id.isnot(None),
                StudyRecord.next_review_at.isnot(None),
                StudyRecord.next_review_at <= now,
            )
            .order_by(StudyRecord.next_review_at.asc())
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        due_records = result.all()

        items = []
        for qid, next_review in due_records:
            question = await self.session.get(Question, qid)
            if question and question.deleted_at is None:
                items.append(
                    {
                        "question_id": qid,
                        "question_title": question.title,
                        "difficulty_level": question.difficulty_level,
                        "mastery_level": question.mastery_level,
                        "next_review_at": next_review,
                        "review_status": question.review_status,
                    }
                )
        return items

    # - Statistics -

    async def get_stats(self) -> dict:
        """Get aggregated study statistics."""
        # Total sessions
        total_stmt = select(func.count()).select_from(StudyRecord)
        total_sessions = (await self.session.exec(total_stmt)).one()[0]

        # By type
        review_stmt = select(func.count()).select_from(StudyRecord).where(
            StudyRecord.study_type == "review"
        )
        total_reviews = (await self.session.exec(review_stmt)).one()[0]

        practice_stmt = select(func.count()).select_from(StudyRecord).where(
            StudyRecord.study_type == "practice"
        )
        total_practice = (await self.session.exec(practice_stmt)).one()[0]

        # Average score (where score is not null)
        avg_stmt = (
            select(func.avg(StudyRecord.ai_score))
            .select_from(StudyRecord)
            .where(StudyRecord.ai_score.isnot(None))
        )
        avg_result = (await self.session.exec(avg_stmt)).one()[0]
        average_score = round(float(avg_result), 2) if avg_result else None

        # Mastered questions (review_result = mastered)
        mastered_stmt = select(func.count(func.distinct(StudyRecord.question_id))).where(
            StudyRecord.review_result == "mastered",
            StudyRecord.question_id.isnot(None),
        )
        questions_mastered = (await self.session.exec(mastered_stmt)).one()[0]

        # Pending review (next_review_at in the past)
        pending_stmt = (
            select(func.count(func.distinct(StudyRecord.question_id)))
            .where(
                StudyRecord.study_type == "review",
                StudyRecord.question_id.isnot(None),
                StudyRecord.next_review_at.isnot(None),
                StudyRecord.next_review_at <= datetime.utcnow(),
            )
        )
        questions_pending = (await self.session.exec(pending_stmt)).one()[0]

        return {
            "total_sessions": total_sessions,
            "total_reviews": total_reviews,
            "total_practice": total_practice,
            "average_score": average_score,
            "questions_mastered": questions_mastered,
            "questions_pending": questions_pending,
        }

    # - Internal helpers -

    def _calculate_interval(self, quality: int, last_record: StudyRecord | None) -> int:
        """Calculate the next review interval using simplified SM-2 algorithm."""
        if quality < 3:
            # Wrong answer - reset to minimum interval
            return MIN_INTERVAL

        if last_record and last_record.extra_data and last_record.extra_data.get("interval_days"):
            interval = int(last_record.extra_data["interval_days"] * EASY_MULTIPLIER)
        else:
            interval = INITIAL_INTERVAL_DAYS

        return max(interval, MIN_INTERVAL)

    def _record_to_dict(self, record: StudyRecord) -> dict:
        """Convert a StudyRecord to a dictionary for API response."""
        return {
            "id": str(record.id),
            "question_id": str(record.question_id) if record.question_id else None,
            "study_type": record.study_type,
            "user_answer": record.user_answer,
            "ai_score": record.ai_score,
            "ai_feedback": record.ai_feedback,
            "mastery_level": record.mastery_level,
            "duration_seconds": record.duration_seconds,
            "review_result": record.review_result,
            "reviewed_at": record.reviewed_at.isoformat(),
            "next_review_at": record.next_review_at.isoformat() if record.next_review_at else None,
            "created_at": record.created_at.isoformat(),
        }
