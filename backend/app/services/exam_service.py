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
        user_id: str | None,
        title: str | None,
        duration_minutes: int,
        question_count: int,
        difficulty_filter: str | None,
        source_filter: str | None,
    ) -> dict:
        """Create a new exam session with selected questions."""
        # Build question selection query
        q_stmt = select(Question).where(Question.deleted_at.is_(None))

        if difficulty_filter:
            if difficulty_filter == "easy":
                q_stmt = q_stmt.where(Question.difficulty_level <= 2)
            elif difficulty_filter == "medium":
                q_stmt = q_stmt.where(Question.difficulty_level.in_([2, 3, 4]))
            elif difficulty_filter == "hard":
                q_stmt = q_stmt.where(Question.difficulty_level >= 4)

        if source_filter:
            q_stmt = q_stmt.where(Question.source_type == source_filter)

        result = await self.session.exec(q_stmt)
        all_questions = result.all()

        if not all_questions:
            raise ValueError("没有找到符合条件的题目")

        # Randomly select questions
        selected = random.sample(all_questions, min(question_count, len(all_questions)))
        question_ids = [q.id for q in selected]

        session_record = ExamSession(
            user_id=user_id,
            title=title or f"模拟考试 {time.strftime('%Y-%m-%d %H:%M')}",
            duration_minutes=duration_minutes,
            total_questions=len(question_ids),
            difficulty_filter=difficulty_filter,
            source_filter=source_filter,
            question_ids=[str(qid) for qid in question_ids],
            status="pending",
        )
        session_record = self.session.add(session_record)
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

    async def get_exam_session(self, session_id: UUID) -> dict | None:
        """Get exam session details."""
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            return None

        # Fetch questions
        question_ids = [UUID(qid) for qid in exam.question_ids]
        q_stmt = select(Question).where(Question.id.in_(question_ids))
        q_result = await self.session.exec(q_stmt)
        questions = q_result.all()

        # Fetch answers
        a_stmt = select(ExamAnswer).where(ExamAnswer.session_id == session_id)
        a_result = await self.session.exec(a_stmt)
        answers = {str(a.question_id): a for a in a_result.all()}

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

    async def start_exam(self, session_id: UUID) -> dict:
        """Mark exam as started."""
        from datetime import datetime
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            raise ValueError("考试不存在")
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
    ) -> dict:
        """Save or update an answer during exam."""
        # Verify session exists and is in progress
        exam = await self.session.get(ExamSession, session_id)
        if not exam or exam.status not in ("in_progress", "pending"):
            raise ValueError("考试不存在或未开始")

        # Check if answer exists
        a_stmt = select(ExamAnswer).where(
            ExamAnswer.session_id == session_id,
            ExamAnswer.question_id == question_id,
        )
        a_result = await self.session.exec(a_stmt)
        answer = a_result.first()

        if answer:
            answer.user_answer = user_answer
            answer.updated_at = __import__("datetime").datetime.utcnow()
        else:
            answer = ExamAnswer(
                session_id=session_id,
                question_id=question_id,
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

    async def submit_exam(self, session_id: UUID) -> dict:
        """Submit exam and start grading."""
        from datetime import datetime
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            raise ValueError("考试不存在")

        exam.status = "submitted"
        exam.submitted_at = datetime.utcnow()
        self.session.add(exam)
        await self.session.commit()

        return {"id": str(exam.id), "status": exam.status, "submitted_at": exam.submitted_at.isoformat()}

    async def grade_exam(self, session_id: UUID) -> AsyncGenerator[dict, None]:
        """Grade all answers in an exam session using LLM."""
        exam = await self.session.get(ExamSession, session_id)
        if not exam:
            raise ValueError("考试不存在")

        # Fetch all questions and answers
        question_ids = [UUID(qid) for qid in exam.question_ids]
        q_stmt = select(Question).where(Question.id.in_(question_ids))
        q_result = await self.session.exec(q_stmt)
        questions = {q.id: q for q in q_result.all()}

        a_stmt = select(ExamAnswer).where(ExamAnswer.session_id == session_id)
        a_result = await self.session.exec(a_stmt)
        answers = {a.question_id: a for a in a_result.all()}

        total_questions = len(question_ids)
        total_score = 0.0
        graded_count = 0

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
