"""Exam service - mock exam session management, question selection, and auto-grading."""

import json
import random
import re
import time
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.models import ExamAnswer, ExamSession, Question, StudyRecord
from app.infra.data_isolation import UserContext, ensure_owned_by
from app.infra.llm.gateway import LLMGateway

logger = get_logger(__name__)


class ExamService:
    """Orchestrates exam session creation, question selection, submission, and grading."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.llm = LLMGateway()

    async def create_exam_session(
        self,
        *,
        user_ctx: UserContext | None = None,
        title: str | None,
        duration_minutes: int,
        question_count: int,
        difficulty_filter: str | None,
        source_filter: str | None,
    ) -> dict:
        """Create a new exam session with selected questions."""
        # Build question selection query - include public + user-owned
        q_stmt = select(Question).where(Question.deleted_at.is_(None))
        # User isolation
        if user_ctx and user_ctx.is_admin:
            pass
        elif user_ctx and user_ctx.is_anonymous:
            q_stmt = q_stmt.where(Question.user_id.is_(None))
        elif user_ctx:
            from sqlalchemy import or_
            q_stmt = q_stmt.where(
                or_(Question.user_id == user_ctx.user_id, Question.user_id.is_(None))
            )

        if difficulty_filter:
            if difficulty_filter == "easy":
                q_stmt = q_stmt.where(Question.difficulty_level <= 2)
            elif difficulty_filter == "medium":
                q_stmt = q_stmt.where(Question.difficulty_level.in_([2, 3, 4]))
            elif difficulty_filter == "hard":
                q_stmt = q_stmt.where(Question.difficulty_level >= 4)

        if source_filter:
            q_stmt = q_stmt.where(Question.source_type == source_filter)

        selected = await self.session.scalars(q_stmt)
        all_questions = list(selected)

        if not all_questions:
            raise ValueError("没有找到符合条件的题目")

        # Randomly select questions
        sampled = random.sample(all_questions, min(question_count, len(all_questions)))
        question_ids = [q.id for q in sampled]

        session_record = ExamSession(
            user_id=user_ctx.user_id if (user_ctx and not user_ctx.is_admin) else None,
            title=title or f"模拟考试 {time.strftime('%Y-%m-%d %H:%M')}",
            duration_minutes=duration_minutes,
            total_questions=len(question_ids),
            difficulty_filter=difficulty_filter,
            source_filter=source_filter,
            question_ids=[str(qid) for qid in question_ids],
            status="pending",
        )
        self.session.add(session_record)
        await self.session.commit()
        await self.session.refresh(session_record)

        # Convert UUIDs to strings for JSON serialization
        question_ids_str = [str(qid) for qid in question_ids]

        logger.info(
            f"Exam session created: id={session_record.id}, "
            f"questions={len(question_ids_str)}, duration={duration_minutes}min"
        )

        return {
            "id": str(session_record.id),
            "title": session_record.title,
            "duration_minutes": session_record.duration_minutes,
            "total_questions": session_record.total_questions,
            "question_ids": question_ids_str,
            "created_at": session_record.created_at.isoformat(),
        }

    async def get_exam_session(self, session_id: UUID, *, user_ctx: UserContext | None = None) -> dict | None:
        """Get exam session details."""
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            return None
        # Ownership check
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                if exam.user_id is not None:
                    return None
            elif exam.user_id is not None and exam.user_id != user_ctx.user_id:
                return None

        # Fetch questions
        question_ids = [UUID(qid) for qid in exam.question_ids]
        q_stmt = select(Question).where(Question.id.in_(question_ids))
        question_result = await self.session.scalars(q_stmt)
        questions = list(question_result.all())

        # Fetch answers
        a_stmt = select(ExamAnswer).where(ExamAnswer.session_id == session_id)
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                a_stmt = a_stmt.where(ExamAnswer.user_id.is_(None))
            else:
                from sqlalchemy import or_ as _or
                a_stmt = a_stmt.where(_or(ExamAnswer.user_id == user_ctx.user_id, ExamAnswer.user_id.is_(None)))
        answer_result = await self.session.scalars(a_stmt)
        answers = {str(a.question_id): a for a in answer_result.all()}

        questions_data = []
        for q in questions:
            answer = answers.get(str(q.id))
            questions_data.append({
                "id": str(q.id),
                "title": q.title,
                "content": q.content,
                "difficulty_level": q.difficulty_level,
                "domain_type": q.domain_type,
                "answered": answer is not None and answer.user_answer is not None,
                "score": float(answer.score) if answer and answer.score is not None else None,
                "user_answer": answer.user_answer if answer else None,
                "feedback": answer.feedback if answer else None,
            })

        return {
            "id": str(exam.id),
            "title": exam.title,
            "duration_minutes": exam.duration_minutes,
            "total_questions": exam.total_questions,
            "status": exam.status,
            "started_at": exam.started_at.isoformat() if exam.started_at else None,
            "submitted_at": exam.submitted_at.isoformat() if exam.submitted_at else None,
            "total_score": float(exam.total_score) if exam.total_score is not None else None,
            "questions": questions_data,
            "created_at": exam.created_at.isoformat(),
        }

    async def start_exam(self, session_id: UUID, *, user_ctx: UserContext | None = None) -> dict:
        """Mark exam as started."""
        from datetime import datetime
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            raise ValueError("考试不存在")
        # Ownership check
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                if exam.user_id is not None:
                    raise ValueError("无权访问此考试")
            elif exam.user_id is not None and exam.user_id != user_ctx.user_id:
                raise ValueError("无权访问此考试")
        if exam.status == "in_progress":
            return {
                "id": str(exam.id),
                "status": exam.status,
                "started_at": exam.started_at.isoformat() if exam.started_at else None,
            }
        if exam.status != "pending":
            raise ValueError(f"考试状态不正确: {exam.status}")

        exam.status = "in_progress"
        exam.started_at = datetime.utcnow()
        self.session.add(exam)
        await self.session.commit()
        await self.session.refresh(exam)

        return {"id": str(exam.id), "status": exam.status, "started_at": exam.started_at.isoformat()}

    async def submit_answer(
        self,
        session_id: UUID,
        question_id: UUID,
        user_answer: str,
        *,
        user_ctx: UserContext | None = None,
    ) -> dict:
        """Save or update an answer during exam."""
        # Verify session exists and is in progress
        exam = await self.session.get(ExamSession, session_id)
        if not exam or exam.status not in ("in_progress", "pending"):
            raise ValueError("考试不存在或未开始")
        # Ownership check
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                if exam.user_id is not None:
                    raise ValueError("无权访问此考试")
            elif exam.user_id is not None and exam.user_id != user_ctx.user_id:
                raise ValueError("无权访问此考试")

        # Check if answer exists
        a_stmt = select(ExamAnswer).where(
            ExamAnswer.session_id == session_id,
            ExamAnswer.question_id == question_id,
        )
        answer_result = await self.session.scalars(a_stmt)
        answer = answer_result.first()

        if answer:
            answer.user_answer = user_answer
            answer.updated_at = __import__("datetime").datetime.utcnow()
        else:
            answer = ExamAnswer(
                session_id=session_id,
                question_id=question_id,
                user_id=user_ctx.user_id if (user_ctx and not user_ctx.is_admin) else None,
                user_answer=user_answer,
            )
            self.session.add(answer)

        await self.session.commit()
        await self.session.refresh(answer)

        return {
            "id": str(answer.id),
            "question_id": str(answer.question_id),
            "saved": True,
        }

    async def submit_exam(self, session_id: UUID, *, user_ctx: UserContext | None = None) -> dict:
        """Submit exam and start grading."""
        from datetime import datetime
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            raise ValueError("考试不存在")
        # Ownership check
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                if exam.user_id is not None:
                    raise ValueError("无权访问此考试")
            elif exam.user_id is not None and exam.user_id != user_ctx.user_id:
                raise ValueError("无权访问此考试")

        exam.status = "submitted"
        exam.submitted_at = datetime.utcnow()
        self.session.add(exam)
        await self.session.commit()

        return {"id": str(exam.id), "status": exam.status, "submitted_at": exam.submitted_at.isoformat()}

    async def grade_exam(self, session_id: UUID, *, user_ctx: UserContext | None = None) -> AsyncGenerator[dict, None]:
        """Grade all answers in an exam session using LLM."""
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            raise ValueError("考试不存在")
        # Ownership check
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                if exam.user_id is not None:
                    raise ValueError("无权访问此考试")
            elif exam.user_id is not None and exam.user_id != user_ctx.user_id:
                raise ValueError("无权访问此考试")

        # Fetch all questions and answers
        question_ids = [UUID(qid) for qid in exam.question_ids]
        q_stmt = select(Question).where(Question.id.in_(question_ids))
        question_result = await self.session.scalars(q_stmt)
        questions = {q.id: q for q in question_result.all()}

        a_stmt = select(ExamAnswer).where(ExamAnswer.session_id == session_id)
        if user_ctx and not user_ctx.is_admin:
            if user_ctx.is_anonymous:
                a_stmt = a_stmt.where(ExamAnswer.user_id.is_(None))
            else:
                from sqlalchemy import or_ as _or
                a_stmt = a_stmt.where(_or(ExamAnswer.user_id == user_ctx.user_id, ExamAnswer.user_id.is_(None)))
        answer_result = await self.session.scalars(a_stmt)
        answers = {a.question_id: a for a in answer_result.all()}

        total_questions = len(question_ids)
        total_score = 0.0
        graded_count = 0

        yield {
            "event": "grading_progress",
            "graded": 0,
            "total": total_questions,
            "question_id": None,
            "question_title": "Starting grading",
            "score": None,
            "feedback": "Grading started",
        }

        for qid in question_ids:
            question = questions.get(qid)
            answer = answers.get(qid)

            if not question:
                continue

            user_answer_text = answer.user_answer if answer else ""

            # Grade each answer using LLM
            try:
                text = await self.llm.chat_with_prompt(
                    prompt_key="answer_evaluation",
                    variables={
                        "question": f"{question.title}\n{question.content}" if question.content else (question.title or ""),
                        "reference_answer": question.answer_summary or question.answer_detail or "",
                        "user_answer": user_answer_text or "未作答",
                    },
                    temperature=0.3,
                    max_tokens=500,
                )
                # Parse score from response (expect JSON like {"score": 85, "feedback": "..."})
                json_match = re.search(r'\{[^}]+\}', text)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        score = float(parsed.get("score", 50))
                        feedback = parsed.get("feedback", text[:200])
                    except json.JSONDecodeError:
                        score = 50.0
                        feedback = text[:200]
                else:
                    score = 50.0
                    feedback = text[:200]

                # Ensure score is 0-100
                score = max(0, min(100, score))

            except Exception as e:
                logger.error(f"Failed to grade question {qid}: {e}")
                score = 0.0
                feedback = f"评分失败: {str(e)[:100]}"

            # Save or update answer
            if answer:
                answer.score = score
                answer.feedback = feedback
                answer.updated_at = __import__("datetime").datetime.utcnow()
                self.session.add(answer)
            else:
                answer = ExamAnswer(
                    session_id=session_id,
                    question_id=qid,
                    user_answer="",
                    score=score,
                    feedback=feedback,
                )
                self.session.add(answer)

            await self.session.commit()

            graded_count += 1
            total_score += score

            yield {
                "event": "grading_progress",
                "graded": graded_count,
                "total": total_questions,
                "question_id": str(qid),
                "question_title": question.title[:50],
                "score": score,
                "feedback": feedback[:100],
            }

        # Update exam total score
        avg_score = total_score / total_questions if total_questions > 0 else 0
        exam.total_score = round(avg_score, 1)
        exam.status = "graded"
        self.session.add(exam)
        await self.session.commit()

        yield {
            "event": "grading_complete",
            "total_score": exam.total_score,
            "graded": graded_count,
            "total": total_questions,
        }
