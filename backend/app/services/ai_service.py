"""AI service — explain, interview, evaluate via LangGraph workflows.

All LLM calls go through LLMGateway — never direct model calls.
"""

import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.models import Question
from app.infra.llm.gateway import llm_gateway, prompt_registry
from app.infra.repositories import QuestionRepository

logger = get_logger(__name__)


class AIService:
    """AI-powered services: explanation, interview simulation, evaluation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = llm_gateway
        self.prompts = prompt_registry
        self.question_repo = QuestionRepository(session)

    # ── Question Explanation ────────────────────────────────────────

    async def explain_question(
        self,
        question_id: UUID | None = None,
        question_text: str | None = None,
        depth: str = "standard",
    ) -> dict:
        """Generate a layered explanation for a question.

        depth: brief (一句话), standard (面试版), deep (深入版)
        """
        # Resolve question
        question = None
        if question_id:
            question = await self.question_repo.get_by_id(question_id)
            if question is None or question.deleted_at is not None:
                raise NotFoundError("Question", str(question_id))
            question_text = f"{question.title}\n{question.content}"

        if not question_text:
            raise ValueError("Either question_id or question_text must be provided")

        # Build prompt based on depth
        depth_instructions = {
            "brief": "请用一句话回答这个问题，给出核心要点。",
            "standard": (
                "请从面试回答角度给出标准答案。要求：\n"
                "1. 先给一句话核心答案\n"
                "2. 再给面试版回答（1-2分钟可以说完）\n"
                "3. 列出关键点\n"
            ),
            "deep": (
                "请给出深度讲解。要求：\n"
                "1. 一句话核心答案\n"
                "2. 面试版回答\n"
                "3. 深入技术细节\n"
                "4. 常见易错点\n"
                "5. 关联知识点\n"
            ),
        }

        system_content = (
            f"你是一个技术面试讲解专家。{depth_instructions.get(depth, depth_instructions['standard'])}\n"
            "回答要面向面试表达，不是论文风格。\n\n"
            f"题目：{question_text}"
        )

        messages = [{"role": "system", "content": system_content}]
        response = await self.llm.chat(messages, temperature=0.7, max_tokens=3000)

        # If we have a real question, save the explanation to it
        if question:
            if depth == "brief":
                question.answer_summary = response
            else:
                question.answer_detail = response
            question.explanation = response
            question.model_version = self.llm.model_name
            question.prompt_version = "explanation-1.0"
            await self.session.flush()

        return {
            "question_id": str(question.id) if question else None,
            "answer_short": response if depth == "brief" else (question.answer_summary if question else ""),
            "answer_detail": response,
            "explanation": response,
            "depth": depth,
        }

    # ── Interview Simulation ────────────────────────────────────────

    async def start_interview(
        self,
        question_id: UUID | None = None,
        domain: str | None = None,
        max_turns: int = 5,
    ) -> dict:
        """Start an interview session. Returns the first question."""
        session_id = f"interview_{uuid.uuid4().hex[:12]}"

        if question_id:
            question = await self.question_repo.get_by_id(question_id)
            if question is None:
                raise NotFoundError("Question", str(question_id))
            first_question = f"{question.title}\n{question.content}"
            context = f"请围绕以下题目进行面试追问：\n题目：{first_question}\n\n领域：{question.domain_type or '通用'}\n难度：{question.difficulty_level or '中等'}"
        elif domain:
            context = f"请在 {domain} 领域生成面试题目，开始第一轮面试。"
            first_question = domain
        else:
            context = "请生成一个AI应用工程师相关的面试题目，开始第一轮面试。"
            first_question = "AI应用工程师面试"

        # Generate the first interview question
        system_prompt = (
            "你是一个严格的技术面试官。请生成一个面试问题，要求：\n"
            "- 问题要开放式的，不是简单的知识回忆\n"
            "- 适合AI应用工程师面试\n"
            f"{context}\n\n"
            "只输出面试题目本身，不要解释。"
        )
        messages = [{"role": "system", "content": system_prompt}]
        generated_question = await self.llm.chat(messages, temperature=0.8, max_tokens=500)

        return {
            "session_id": session_id,
            "first_question": generated_question,
            "max_turns": max_turns,
        }

    # ── Answer Evaluation ───────────────────────────────────────────

    async def evaluate_answer(self, question_id: UUID, user_answer: str) -> dict:
        """Evaluate a user's answer against a question using LLM."""
        question = await self.question_repo.get_by_id(question_id)
        if question is None or question.deleted_at is not None:
            raise NotFoundError("Question", str(question_id))

        # Use the registered evaluation prompt
        response = await self.llm.chat_json_with_prompt(
            "answer_evaluation",
            variables={
                "question": f"{question.title}\n{question.content}",
                "reference_answer": question.answer_summary or question.answer_detail or "请参考题目内容自行判断。",
                "user_answer": user_answer,
            },
            temperature=0.3,
        )

        score = response.get("score", 0)
        is_pass = response.get("is_pass", score >= 60)
        feedback = response.get("feedback", "")
        missing = response.get("missing_points", [])

        # Derive mastery level from score
        if score >= 90:
            mastery_level = 5
        elif score >= 75:
            mastery_level = 4
        elif score >= 60:
            mastery_level = 3
        elif score >= 40:
            mastery_level = 2
        else:
            mastery_level = 1

        return {
            "score": score,
            "feedback": feedback,
            "missing_points": missing,
            "is_pass": is_pass,
            "mastery_level": mastery_level,
        }

    # ── Follow-up Question Generation ───────────────────────────────

    async def generate_followup(self, original_question: str, user_answer: str) -> list[str]:
        """Generate follow-up questions based on the original question and user's answer."""
        response = await self.llm.chat_json_with_prompt(
            "followup_generator",
            variables={
                "original_question": original_question,
                "user_answer": user_answer,
            },
            temperature=0.5,
        )

        if isinstance(response, list):
            return [item.get("content", item.get("title", "")) for item in response]
        if isinstance(response, dict) and "followup_questions" in response:
            return response["followup_questions"]
        return []

    # ── Interview Flow (multi-turn) ─────────────────────────────────

    async def handle_interview_turn(
        self,
        session_id: str,
        current_turn: int,
        max_turns: int,
        question_text: str,
        user_answer: str,
    ) -> dict:
        """Handle a single turn in the interview flow.

        Returns follow-up question, score, feedback, and whether the interview is done.
        """
        # Evaluate the answer
        evaluation = await self._evaluate_single_answer(question_text, user_answer)
        score = evaluation.get("score", 0)
        feedback = evaluation.get("feedback", "")

        is_done = current_turn >= max_turns or score >= 80

        if is_done:
            # Interview complete — give final summary
            summary_prompt = (
                f"面试已结束。当前题目：{question_text}\n用户回答：{user_answer}\n"
                "请给出最终面试评价，包括：\n"
                "1. 总体评分\n"
                "2. 回答亮点\n"
                "3. 需要改进的地方\n"
                "4. 后续学习建议\n"
            )
            summary = await self.llm.chat(
                [{"role": "system", "content": summary_prompt}],
                temperature=0.7,
                max_tokens=1000,
            )
            return {
                "followup_question": None,
                "score": score,
                "feedback": summary,
                "is_done": True,
            }

        # Generate follow-up question
        followups = await self.generate_followup(question_text, user_answer)
        followup = followups[0] if followups else "请进一步深入解释你的观点。"

        return {
            "followup_question": followup,
            "score": score,
            "feedback": feedback,
            "is_done": False,
        }

    # ── Internal helpers ────────────────────────────────────────────

    async def _evaluate_single_answer(self, question_text: str, user_answer: str) -> dict:
        """Evaluate a single answer (lightweight, for interview flow)."""
        prompt = (
            "你是一个技术面试官。请评估以下回答。\n\n"
            f"问题：{question_text}\n"
            f"回答：{user_answer}\n\n"
            "请输出JSON，包含：\n"
            "- score: 0-100的整数\n"
            "- feedback: 简短反馈\n"
            "- is_pass: true/false (>=60为pass)\n"
        )
        try:
            return await self.llm.chat_json(
                [{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
        except Exception:
            return {"score": 50, "feedback": "评价失败，请重试。", "is_pass": False}
