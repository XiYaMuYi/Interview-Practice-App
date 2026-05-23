"""Study service - study records, review scheduling, and statistics."""

from datetime import datetime, timedelta
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.models import KnowledgeNode, Question, QuestionKnowledgeNode, QuestionTag, StudyRecord, Tag
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
        return self._record_to_dict(record)

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

    async def get_study_records_with_count(
        self,
        *,
        question_id: UUID | None = None,
        study_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """List study records with real total count."""
        offset = (page - 1) * page_size
        filters = {}
        if study_type:
            filters["study_type"] = study_type

        records, total = await self.study_repo.list_with_count(
            offset=offset, limit=page_size, filters=filters
        )

        # Filter by question_id if provided
        if question_id:
            records = [r for r in records if r.question_id == question_id]
            # Re-count with question_id filter for accurate total
            from sqlalchemy import func
            q_filter_stmt = (
                __import__("sqlalchemy").select(func.count())
                .select_from(StudyRecord)
                .where(StudyRecord.question_id == question_id)
            )
            if study_type:
                q_filter_stmt = q_filter_stmt.where(StudyRecord.study_type == study_type)
            total = (await self.session.exec(q_filter_stmt)).scalar_one()

        # Batch-fetch questions to avoid N+1
        qids = list({r.question_id for r in records if r.question_id})
        question_map = {}
        if qids:
            q_stmt = select(Question).where(Question.id.in_(qids))
            q_result = await self.session.exec(q_stmt)
            questions = []
            for row in q_result.all():
                question = row
                if not isinstance(row, Question) and hasattr(row, "_mapping"):
                    question = next(iter(row._mapping.values()))
                questions.append(question)
            question_map = {q.id: q for q in questions}

        result = []
        for r in records:
            d = self._record_to_dict(r)
            if r.question_id and r.question_id in question_map:
                d["question_title"] = question_map[r.question_id].title
            else:
                d["question_title"] = None
            result.append(d)
        return result, total

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

        # Batch-fetch questions to avoid N+1
        qids = list({qid for qid, _ in due_records})
        question_map = {}
        if qids:
            q_stmt = select(Question).where(Question.id.in_(qids))
            q_result = await self.session.exec(q_stmt)
            question_map = {q.id: q for q in q_result.all()}

        items = []
        for qid, next_review in due_records:
            question = question_map.get(qid)
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

    async def get_review_list_with_count(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """Get questions due for review with real total count and pagination."""
        now = datetime.utcnow()

        # Count query
        from sqlalchemy import func

        count_stmt = (
            select(func.count(func.distinct(StudyRecord.question_id)))
            .where(
                StudyRecord.study_type == "review",
                StudyRecord.question_id.isnot(None),
                StudyRecord.next_review_at.isnot(None),
                StudyRecord.next_review_at <= now,
            )
        )
        total = (await self.session.exec(count_stmt)).scalar_one()

        # Data query with pagination
        offset = (page - 1) * page_size
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
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.exec(stmt)
        due_records = result.all()

        # Batch-fetch questions to avoid N+1
        qids = list({qid for qid, _ in due_records})
        question_map = {}
        if qids:
            q_stmt = select(Question).where(Question.id.in_(qids))
            q_result = await self.session.exec(q_stmt)
            question_map = {q.id: q for q in q_result.all()}

        items = []
        for qid, next_review in due_records:
            question = question_map.get(qid)
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
        return items, total

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
            "id": record.id,
            "question_id": record.question_id,
            "study_type": record.study_type,
            "user_answer": record.user_answer,
            "ai_score": record.ai_score,
            "ai_feedback": record.ai_feedback,
            "mastery_level": record.mastery_level,
            "duration_seconds": record.duration_seconds,
            "review_result": record.review_result,
            "reviewed_at": record.reviewed_at,
            "next_review_at": record.next_review_at,
            "created_at": record.created_at,
        }

    # - Review Report Generation -

    async def generate_review_report_stream(
        self,
        session_id: str | None = None,
        days: int = 7,
        include_feedback: bool = True,
    ) -> tuple[UUID, AsyncGenerator[str, None]]:
        """Generate a review report with aggregated study statistics.

        Returns (task_id, event_generator).
        """
        import json
        import time
        import uuid

        from app.services.task_manager import TaskManager

        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="review_report",
            source_id=session_id,
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                # Phase 1: task started
                yield _sse("task_started", {"task_id": str(task_id), "message": "开始生成复盘报告", "days": days})

                # Phase 2: SQL aggregation
                yield _sse("progress", {"task_id": str(task_id), "phase": "aggregating", "progress": 0.15, "current": "正在聚合学习数据...", "elapsed": round(time.monotonic() - start_time, 1)})

                cutoff = datetime.utcnow() - timedelta(days=days)

                # Base query filters
                base_filters = [StudyRecord.reviewed_at >= cutoff]
                if session_id:
                    base_filters.append(StudyRecord.session_id == session_id)

                # Total sessions
                total_stmt = select(func.count()).select_from(StudyRecord).where(*base_filters)
                total_sessions = (await self.session.exec(total_stmt)).scalar_one()

                # Mastered count
                mastered_stmt = select(func.count()).select_from(StudyRecord).where(
                    *base_filters, StudyRecord.review_result == "mastered"
                )
                mastered_count = (await self.session.exec(mastered_stmt)).scalar_one()

                # Average score
                avg_stmt = select(func.avg(StudyRecord.ai_score)).select_from(StudyRecord).where(
                    *base_filters, StudyRecord.ai_score.isnot(None)
                )
                avg_result = (await self.session.exec(avg_stmt)).scalar_one()
                average_score = round(float(avg_result), 2) if avg_result else None

                # By study type
                type_stmt = select(StudyRecord.study_type, func.count()).where(*base_filters).group_by(StudyRecord.study_type)
                type_result = await self.session.exec(type_stmt)
                by_type = {row[0]: row[1] for row in type_result.all()}

                # Weak areas: JOIN StudyRecord -> Question -> QuestionTag -> Tag
                # Group by tag, compute avg score and count, order by avg_score ASC
                weak_stmt = (
                    select(
                        Tag.name.label("tag_name"),
                        Tag.tag_type.label("tag_type"),
                        func.count(StudyRecord.id).label("count"),
                        func.avg(StudyRecord.ai_score).label("avg_score"),
                        func.avg(StudyRecord.mastery_level).label("avg_mastery"),
                    )
                    .join(Question, Question.id == StudyRecord.question_id)
                    .join(QuestionTag, QuestionTag.question_id == Question.id)
                    .join(Tag, Tag.id == QuestionTag.tag_id)
                    .where(*base_filters, StudyRecord.question_id.isnot(None))
                    .group_by(Tag.name, Tag.tag_type)
                    .order_by(func.avg(StudyRecord.ai_score).asc())
                    .limit(20)
                )
                weak_result = await self.session.exec(weak_stmt)
                weak_areas = []
                for row in weak_result.all():
                    weak_areas.append({
                        "tag": row.tag_name,
                        "tag_type": row.tag_type,
                        "count": row.count,
                        "avg_score": round(float(row.avg_score), 2) if row.avg_score else None,
                        "avg_mastery": round(float(row.avg_mastery), 2) if row.avg_mastery else None,
                    })

                # Weak knowledge nodes: JOIN StudyRecord -> Question -> QuestionKnowledgeNode -> KnowledgeNode
                node_stmt = (
                    select(
                        KnowledgeNode.name.label("node_name"),
                        KnowledgeNode.node_type.label("node_type"),
                        func.count(StudyRecord.id).label("count"),
                        func.avg(StudyRecord.ai_score).label("avg_score"),
                        func.avg(StudyRecord.mastery_level).label("avg_mastery"),
                    )
                    .join(Question, Question.id == StudyRecord.question_id)
                    .join(QuestionKnowledgeNode, QuestionKnowledgeNode.question_id == Question.id)
                    .join(KnowledgeNode, KnowledgeNode.id == QuestionKnowledgeNode.knowledge_node_id)
                    .where(*base_filters, StudyRecord.question_id.isnot(None))
                    .group_by(KnowledgeNode.name, KnowledgeNode.node_type)
                    .order_by(func.avg(StudyRecord.ai_score).asc())
                    .limit(20)
                )
                node_result = await self.session.exec(node_stmt)
                weak_nodes = []
                for row in node_result.all():
                    weak_nodes.append({
                        "node": row.node_name,
                        "node_type": row.node_type,
                        "count": row.count,
                        "avg_score": round(float(row.avg_score), 2) if row.avg_score else None,
                        "avg_mastery": round(float(row.avg_mastery), 2) if row.avg_mastery else None,
                    })

                yield _sse("progress", {"task_id": str(task_id), "phase": "aggregated", "progress": 0.30, "current": f"聚合完成：{total_sessions} 条记录，{len(weak_areas)} 个薄弱标签", "elapsed": round(time.monotonic() - start_time, 1)})

                # Phase 3: generate summary via AIService
                yield _sse("progress", {"task_id": str(task_id), "phase": "generating_summary", "progress": 0.40, "current": "正在生成复盘总结...", "elapsed": round(time.monotonic() - start_time, 1)})

                records_summary = json.dumps({
                    "period_days": days,
                    "total_sessions": total_sessions,
                    "mastered_count": mastered_count,
                    "average_score": average_score,
                    "by_type": by_type,
                    "weak_nodes": weak_nodes[:10],
                }, ensure_ascii=False)

                # Import AIService lazily to avoid circular imports
                from app.services.ai_service import AIService
                ai_service = AIService(self.session)

                summary_task_id, summary_gen = await ai_service.generate_review_summary_stream(
                    records_summary=records_summary,
                    weak_areas=weak_areas[:10],
                )

                summary_content = None
                async for event in summary_gen:
                    # Forward sub-task events
                    yield event
                    if event.startswith("event: content"):
                        lines = event.split("\n")
                        for line in lines:
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    summary_content = data.get("content")
                                except json.JSONDecodeError:
                                    pass

                # Phase 4: generate recommendations
                yield _sse("progress", {"task_id": str(task_id), "phase": "generating_recommendations", "progress": 0.70, "current": "正在生成改进建议...", "elapsed": round(time.monotonic() - start_time, 1)})

                mastery_trend = f"平均分数: {average_score}, 掌握率: {mastered_count}/{total_sessions}" if total_sessions > 0 else "暂无数据"

                rec_task_id, rec_gen = await ai_service.generate_review_recommendations_stream(
                    weak_areas=weak_areas[:10],
                    mastery_trend=mastery_trend,
                )

                recommendations = None
                async for event in rec_gen:
                    # Forward sub-task events
                    yield event
                    if event.startswith("event: result"):
                        lines = event.split("\n")
                        for line in lines:
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    recommendations = data.get("recommendations")
                                except json.JSONDecodeError:
                                    pass

                # Phase 5: complete
                yield _sse("task_completed", {
                    "task_id": str(task_id),
                    "report_id": str(task_id),
                    "status": "success",
                    "period_days": days,
                    "total_sessions": total_sessions,
                    "mastered_count": mastered_count,
                    "weak_areas": weak_areas,
                    "summary": summary_content,
                    "recommendations": recommendations,
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

                await task_manager.update_task(task_id, status="done", progress=1.0)
                yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})

            except Exception as e:
                logger.error(f"Review report generation failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    # - Learning Path Generation -

    async def generate_learning_path_stream(
        self,
        focus_areas: list[str] | None = None,
        max_items: int = 20,
        strategy: str = "weak_first",
    ) -> tuple[UUID, AsyncGenerator[str, None]]:
        """Generate a learning path based on weak areas.

        Returns (task_id, event_generator).
        """
        import json
        import time
        import uuid

        from app.services.task_manager import TaskManager

        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="learning_path",
            source_id=None,
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                # Phase 1: task started
                yield _sse("task_started", {"task_id": str(task_id), "message": "开始生成学习路径", "strategy": strategy})

                # Phase 2: identify weak areas
                yield _sse("progress", {"task_id": str(task_id), "phase": "identifying_weak", "progress": 0.10, "current": "正在识别薄弱知识点...", "elapsed": round(time.monotonic() - start_time, 1)})

                if focus_areas and len(focus_areas) > 0:
                    # Use specified focus areas
                    weak_tags = focus_areas
                else:
                    # Auto-identify: tags with lowest avg scores
                    weak_stmt = (
                        select(Tag.name)
                        .join(QuestionTag, QuestionTag.tag_id == Tag.id)
                        .join(StudyRecord, StudyRecord.question_id == QuestionTag.question_id)
                        .where(
                            StudyRecord.ai_score.isnot(None),
                            StudyRecord.question_id.isnot(None),
                        )
                        .group_by(Tag.name)
                        .having(func.avg(StudyRecord.ai_score) < 70)
                        .order_by(func.avg(StudyRecord.ai_score).asc())
                        .limit(10)
                    )
                    weak_result = await self.session.exec(weak_stmt)
                    weak_tags = [row[0] for row in weak_result.all()]

                if not weak_tags:
                    yield _sse("task_completed", {
                        "task_id": str(task_id),
                        "path_id": str(task_id),
                        "status": "success",
                        "strategy": strategy,
                        "items": [],
                        "total_weak_count": 0,
                        "message": "未识别到薄弱知识点，所有领域表现良好",
                        "elapsed": round(time.monotonic() - start_time, 1),
                    })
                    await task_manager.update_task(task_id, status="done", progress=1.0)
                    yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})
                    return

                yield _sse("progress", {"task_id": str(task_id), "phase": "identified", "progress": 0.30, "current": f"识别到 {len(weak_tags)} 个薄弱标签: {', '.join(weak_tags)}", "elapsed": round(time.monotonic() - start_time, 1)})

                # Phase 3: find related questions
                yield _sse("progress", {"task_id": str(task_id), "phase": "finding_questions", "progress": 0.40, "current": "正在查找关联题目...", "elapsed": round(time.monotonic() - start_time, 1)})

                # Query questions linked to weak tags, with mastery info
                q_stmt = (
                    select(
                        Question.id,
                        Question.title,
                        Question.difficulty_level,
                        Question.mastery_level,
                        func.avg(StudyRecord.ai_score).label("avg_score"),
                    )
                    .join(QuestionTag, QuestionTag.question_id == Question.id)
                    .join(Tag, Tag.id == QuestionTag.tag_id)
                    .join(StudyRecord, StudyRecord.question_id == Question.id, isouter=True)
                    .where(
                        Tag.name.in_(weak_tags),
                        Question.deleted_at.is_(None),
                    )
                    .group_by(Question.id, Question.title, Question.difficulty_level, Question.mastery_level)
                )

                if strategy == "weak_first":
                    q_stmt = q_stmt.order_by(
                        func.coalesce(func.avg(StudyRecord.ai_score), 100).asc(),
                        Question.difficulty_level.asc(),
                    )
                elif strategy == "sequential":
                    q_stmt = q_stmt.order_by(
                        Question.difficulty_level.asc(),
                        Question.created_at.asc(),
                    )
                else:  # mixed
                    q_stmt = q_stmt.order_by(
                        func.coalesce(func.avg(StudyRecord.ai_score), 100).asc(),
                        func.random(),
                    )

                q_stmt = q_stmt.limit(max_items)
                q_result = await self.session.exec(q_stmt)

                total_weak_count = len(weak_tags)
                items = []
                for idx, row in enumerate(q_result.all(), 1):
                    reason = f"薄弱标签关联"
                    if row.avg_score is not None:
                        reason = f"平均分 {row.avg_score:.0f}，需加强练习"
                    elif row.mastery_level and row.mastery_level < 3:
                        reason = f"掌握度 {row.mastery_level}/5，建议复习"

                    items.append({
                        "question_id": str(row.id),
                        "title": row.title,
                        "reason": reason,
                        "difficulty": row.difficulty_level or 3,
                        "priority": idx,
                    })

                yield _sse("progress", {"task_id": str(task_id), "phase": "path_built", "progress": 0.90, "current": f"学习路径已生成，共 {len(items)} 道题目", "elapsed": round(time.monotonic() - start_time, 1)})

                # Phase 4: complete
                yield _sse("task_completed", {
                    "task_id": str(task_id),
                    "path_id": str(task_id),
                    "status": "success",
                    "strategy": strategy,
                    "items": items,
                    "total_weak_count": total_weak_count,
                    "focus_areas": weak_tags,
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

                await task_manager.update_task(task_id, status="done", progress=1.0)
                yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})

            except Exception as e:
                logger.error(f"Learning path generation failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())
