"""AI service — explain, interview, evaluate via LangGraph workflows.

All LLM calls go through LLMGateway — never direct model calls.
All prompts go through PromptRegistry — no hardcoded prompt text.
"""

import asyncio
import hashlib
import json
import time
import uuid
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.models import Question
from app.infra.cache.cache_service import TTL_EXPLAIN, TTL_QUESTION, get_cache, set_cache
from app.infra.events.event_publisher import event_publisher
from app.infra.events.event_types import CACHE_HIT, CACHE_MISS, FOLLOWUP_GENERATED
from app.infra.llm.gateway import llm_gateway, prompt_registry
from app.infra.repositories import QuestionRepository
from app.services.task_manager import TaskManager

logger = get_logger(__name__)

# Depth-to-prompt_key mapping for explanation.
# Each depth level uses the same registered prompt with different max_tokens.
_DEPTH_CONFIG = {
    "brief": {"max_tokens": 500, "instruction": "请用一句话回答这个问题，给出核心要点。"},
    "standard": {"max_tokens": 1500, "instruction": (
        "请从面试回答角度给出标准答案。要求：\n"
        "1. 先给一句话核心答案\n"
        "2. 再给面试版回答（1-2分钟可以说完）\n"
        "3. 列出关键点\n"
    )},
    "deep": {"max_tokens": 3000, "instruction": (
        "请给出深度讲解。要求：\n"
        "1. 一句话核心答案\n"
        "2. 面试版回答\n"
        "3. 深入技术细节\n"
        "4. 常见易错点\n"
        "5. 关联知识点\n"
    )},
}


class AIService:
    """AI 能力的业务编排层。

    这个类是后端 Agent 相关能力的主要入口，负责把：
    - 题目讲解
    - 模拟面试
    - 答案评价
    - 追问生成
    串成一个稳定、可复用、可扩展的业务服务。

    它不直接调用模型供应商，而是统一通过 `llm_gateway` 访问。
    所有 prompt 都从 PromptRegistry 获取，不在代码中散落。
    """

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
        question = None
        if question_id:
            question = await self.question_repo.get_by_id(question_id)
            if question is None or question.deleted_at is not None:
                raise NotFoundError("Question", str(question_id))
            question_text = f"{question.title}\n{question.content}"

        if not question_text:
            raise ValueError("Either question_id or question_text must be provided")

        # Check cache: key includes prompt_version for cache invalidation
        tpl = prompt_registry.get_template("question_explanation")
        prompt_ver = f"explanation-{tpl.version}" if tpl else "explanation-1.0"
        cache_key = f"app:question:explain:{question_id or hashlib.sha256(question_text.encode()).hexdigest()[:16]}:{prompt_ver}"
        cached = await get_cache(cache_key)
        if cached is not None:
            logger.info(f"Explanation cache HIT: {cache_key}")
            try:
                await event_publisher.publish(CACHE_HIT, {
                    "task_id": None,
                    "cache_key": cache_key,
                })
            except Exception:
                pass
            return cached
        try:
            await event_publisher.publish(CACHE_MISS, {
                "task_id": None,
                "cache_key": cache_key,
            })
        except Exception:
            pass

        depth_cfg = _DEPTH_CONFIG.get(depth, _DEPTH_CONFIG["standard"])

        system_content = (
            f"你是一个技术面试讲解专家。{depth_cfg['instruction']}\n"
            "回答要面向面试表达，不是论文风格。\n\n"
            f"题目：{question_text}"
        )

        messages = [{"role": "system", "content": system_content}]
        response = await self.llm.chat(
            messages,
            temperature=0.7,
            max_tokens=depth_cfg["max_tokens"],
            prompt_key="question_explanation",
            prompt_version=prompt_ver,
        )
        try:
            await event_publisher.publish(CACHE_MISS, {
                "task_id": None,
                "cache_key": cache_key,
                "reason": "explanation_generated",
            })
        except Exception:
            pass

        if question:
            if depth == "brief":
                question.answer_summary = response
            else:
                question.answer_detail = response
            question.explanation = response
            question.model_version = self.llm.model_name
            question.prompt_version = "explanation-1.0"
            await self.session.flush()

        result = {
            "question_id": str(question.id) if question else None,
            "answer_short": response if depth == "brief" else (question.answer_summary or "" if question else ""),
            "answer_detail": response,
            "explanation": response,
            "depth": depth,
        }

        # Cache the explanation
        try:
            await set_cache(cache_key, result, ttl=TTL_EXPLAIN)
        except Exception:
            pass

        return result

    async def explain_question_stream(
        self,
        question_id: UUID | None = None,
        question_text: str | None = None,
        depth: str = "standard",
        existing_task_id: UUID | None = None,
    ) -> tuple:
        """Stream question explanation with SSE events.

        Returns (task_id, event_generator).

        If ``existing_task_id`` is provided, the generator updates that task
        record instead of creating a new one.  This allows the route handler
        to create-and-commit the task record first (so the frontend can
        subscribe immediately), then run the generator in a background task
        with a fresh DB session.
        """
        start_time = time.monotonic()

        # Threshold (in characters) for emitting accumulated ``content`` events.
        _CONTENT_INTERVAL = 50

        def _sse(event_type: str, data: dict) -> str:
            data["event_type"] = event_type
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        question = None
        if question_id:
            question = await self.question_repo.get_by_id(question_id)
            if question is None or question.deleted_at is not None:
                raise ValueError(f"Question {question_id} not found")
            question_text = f"{question.title}\n{question.content}"

        if not question_text:
            raise ValueError("Either question_id or question_text must be provided")

        task_manager = TaskManager(self.session)
        if existing_task_id is not None:
            # Background task reuses the already-created task record.
            task_id = existing_task_id
        else:
            task = await task_manager.create_task(
                task_type="explanation",
                source_id=str(question_id) if question_id else None,
            )
            task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.10, current_phase="preparing")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "preparing", "progress": 0.10, "current": "正在准备讲解...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "preparing", "progress": 0.10, "current": "正在准备讲解...", "elapsed": round(time.monotonic() - start_time, 1)})

                depth_cfg = _DEPTH_CONFIG.get(depth, _DEPTH_CONFIG["standard"])
                await task_manager.update_task(task_id, progress=0.30, current_phase="generating")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "generating", "progress": 0.30, "current": "正在生成讲解内容...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "generating", "progress": 0.30, "current": "正在生成讲解内容...", "elapsed": round(time.monotonic() - start_time, 1)})

                system_content = (
                    f"你是一个技术面试讲解专家。{depth_cfg['instruction']}\n"
                    "回答要面向面试表达，不是论文风格。\n\n"
                    f"题目：{question_text}"
                )

                stream_tpl = prompt_registry.get_template("question_explanation")
                stream_prompt_ver = f"explanation-{stream_tpl.version}" if stream_tpl else "explanation-1.0"

                # Token-level true streaming with accumulated content events
                full_text: list[str] = []
                last_content_len = 0
                async for chunk in self.llm.stream_chat(
                    [{"role": "system", "content": system_content}],
                    temperature=0.7,
                    max_tokens=depth_cfg["max_tokens"],
                    prompt_key="question_explanation",
                    prompt_version=stream_prompt_ver,
                ):
                    full_text.append(chunk)
                    await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "token": chunk})
                    yield _sse("token", {"task_id": str(task_id), "token": chunk})

                    # Emit accumulated content event every ~50 characters
                    accumulated = "".join(full_text)
                    if len(accumulated) - last_content_len >= _CONTENT_INTERVAL:
                        last_content_len = len(accumulated)
                        await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "content": accumulated})
                        yield _sse("content", {"task_id": str(task_id), "content": accumulated})

                response = "".join(full_text)

                await task_manager.update_task(task_id, progress=0.80, current_phase="saving")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "saving", "progress": 0.80, "current": "正在保存讲解...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "saving", "progress": 0.80, "current": "正在保存讲解...", "elapsed": round(time.monotonic() - start_time, 1)})

                if question:
                    if depth == "brief":
                        question.answer_summary = response
                    else:
                        question.answer_detail = response
                    question.explanation = response
                    question.model_version = self.llm.model_name
                    question.prompt_version = "explanation-1.0"
                    await self.session.flush()

                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "content": response, "depth": depth})
                yield _sse("content", {"task_id": str(task_id), "content": response, "depth": depth})

                await task_manager.update_task(task_id, status="done", progress=1.0)
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})

            except asyncio.CancelledError:
                logger.warning(f"Stream explanation cancelled for task {task_id}, marking as failed")
                try:
                    await task_manager.update_task(task_id, status="failed", progress=0.0, error_message="Connection cancelled")
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"Stream explanation failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "error": str(e), "recoverable": False})
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    # ── Interview Simulation ────────────────────────────────────────

    async def start_interview(
        self,
        question_id: UUID | None = None,
        domain: str | None = None,
        max_turns: int = 5,
    ) -> dict:
        """Start an interview session. Returns the first question.

        Uses: interview_start prompt from registry.
        """
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

        generated_question = await self.llm.chat_with_prompt(
            "interview_start",
            variables={"context": context},
            temperature=0.8,
            max_tokens=500,
        )

        return {
            "session_id": session_id,
            "first_question": generated_question,
            "max_turns": max_turns,
        }

    # ── Answer Evaluation ───────────────────────────────────────────

    async def evaluate_answer(self, question_id: UUID, user_answer: str) -> dict:
        """Evaluate a user's answer against a question using LLM.

        Uses: answer_evaluation prompt from registry.
        """
        question = await self.question_repo.get_by_id(question_id)
        if question is None or question.deleted_at is not None:
            raise NotFoundError("Question", str(question_id))

        response = await self.llm.chat_json_with_prompt(
            "interview_evaluation",
            variables={
                "question_text": f"{question.title}\n{question.content}",
                "reference_answer": question.answer_summary or question.answer_detail or "请参考题目内容自行判断。",
                "user_answer": user_answer,
            },
            temperature=0.3,
        )

        score = response.get("score", 0)
        is_pass = response.get("is_pass", score >= 60)
        feedback = response.get("feedback", "")
        missing = response.get("missing_points", [])

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

    async def evaluate_answer_stream(self, question_id: UUID, user_answer: str) -> tuple:
        """Stream answer evaluation with SSE events.

        Returns (task_id, event_generator).
        """
        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            data["event_type"] = event_type
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        question = await self.question_repo.get_by_id(question_id)
        if question is None or question.deleted_at is not None:
            raise ValueError(f"Question {question_id} not found")

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="evaluation",
            source_id=str(question_id),
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.10, current_phase="evaluating")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "evaluating", "progress": 0.10, "current": "正在评价回答...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "evaluating", "progress": 0.10, "current": "正在评价回答...", "elapsed": round(time.monotonic() - start_time, 1)})

                response = await self.llm.chat_json_with_prompt(
                    "interview_evaluation",
                    variables={
                        "question_text": f"{question.title}\n{question.content}",
                        "reference_answer": question.answer_summary or question.answer_detail or "请参考题目内容自行判断。",
                        "user_answer": user_answer,
                    },
                    temperature=0.3,
                )

                score = response.get("score", 0)
                is_pass = response.get("is_pass", score >= 60)
                feedback = response.get("feedback", "")
                missing = response.get("missing_points", [])

                if score >= 90: mastery = 5
                elif score >= 75: mastery = 4
                elif score >= 60: mastery = 3
                elif score >= 40: mastery = 2
                else: mastery = 1

                await task_manager.update_task(task_id, progress=0.80, current_phase="saving")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "saving", "progress": 0.80, "current": "正在保存评价结果...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "saving", "progress": 0.80, "current": "正在保存评价结果...", "elapsed": round(time.monotonic() - start_time, 1)})

                await task_manager.publish_task_event(str(task_id), {
                    "task_id": str(task_id),
                    "score": score, "feedback": feedback,
                    "missing_points": missing, "is_pass": is_pass,
                    "mastery_level": mastery,
                })
                yield _sse("result", {
                    "task_id": str(task_id),
                    "score": score, "feedback": feedback,
                    "missing_points": missing, "is_pass": is_pass,
                    "mastery_level": mastery,
                })

                await task_manager.update_task(task_id, status="done", progress=1.0)
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})

            except asyncio.CancelledError:
                logger.warning(f"Stream evaluation cancelled for task {task_id}, marking as failed")
                try:
                    await task_manager.update_task(task_id, status="failed", progress=0.0, error_message="Connection cancelled")
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"Stream evaluation failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "error": str(e), "recoverable": False})
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    # ── Follow-up Question Generation ───────────────────────────────

    async def generate_followup(
        self,
        original_question: str,
        user_answer: str,
        *,
        task_id: UUID | str | None = None,
    ) -> list[str]:
        """Generate follow-up questions based on the original question and user's answer.

        Uses: followup_generator prompt from registry.
        Cached by content hash + prompt_version to avoid redundant LLM calls.
        """
        from app.infra.llm.prompt_registry import prompt_registry

        template = prompt_registry.get_template("followup_generator")
        prompt_ver = f"followup-{template.version}" if template else "followup-2.0"
        q_hash = hashlib.sha256(f"{original_question}|{user_answer}".encode()).hexdigest()[:16]
        cache_key = f"app:question:followup:{q_hash}:{prompt_ver}"

        cached = await get_cache(cache_key)
        if cached is not None:
            logger.info(f"Followup cache HIT: {cache_key}")
            try:
                from app.infra.events.event_types import CACHE_HIT
                await event_publisher.publish(CACHE_HIT, {
                    "task_id": str(task_id) if task_id else None,
                    "cache_key": cache_key,
                })
            except Exception:
                pass
            return cached if isinstance(cached, list) else []

        response = await self.llm.chat_json_with_prompt(
            "interview_followup",
            variables={
                "question_text": original_question,
                "user_answer": user_answer,
                "difficulty": "medium",
                "current_turn": "1",
                "history": "",
            },
            temperature=0.5,
        )

        questions: list[str] = []
        if isinstance(response, list):
            questions = [item.get("content", item.get("title", "")) for item in response]
        elif isinstance(response, dict) and "followup_questions" in response:
            questions = response["followup_questions"]

        if questions:
            try:
                await set_cache(cache_key, questions, ttl=TTL_QUESTION)
            except Exception:
                pass

            try:
                await event_publisher.publish(FOLLOWUP_GENERATED, {
                    "task_id": str(task_id) if task_id else None,
                    "original_question": original_question[:200],
                    "followup_count": len(questions),
                    "prompt_version": prompt_ver,
                    "cache_key": cache_key,
                })
            except Exception:
                pass

        return questions

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
        Includes ReAct safety guards: turn validation, hard timeout, exception fallback.
        """
        if current_turn > max_turns:
            logger.warning(
                f"handle_interview_turn: current_turn={current_turn} exceeds max_turns={max_turns}, "
                f"forcing interview end."
            )
            return {
                "followup_question": None,
                "score": None,
                "feedback": f"面试已结束：已达到最大轮次 {max_turns}。",
                "is_done": True,
                "turns_remaining": 0,
                "convergence_reason": "max_turns_reached",
                "is_timeout": False,
            }

        turn_start = time.monotonic()
        timeout_seconds = 60

        try:
            evaluation = await self._evaluate_single_answer(question_text, user_answer)
            score = evaluation.get("score", 0)
            feedback = evaluation.get("feedback", "")

            elapsed = time.monotonic() - turn_start
            if elapsed > timeout_seconds:
                logger.warning(
                    f"handle_interview_turn: turn processing exceeded {timeout_seconds}s timeout "
                    f"(elapsed={elapsed:.1f}s), forcing end."
                )
                return {
                    "followup_question": None,
                    "score": score,
                    "feedback": feedback or "处理超时，本轮评价未能完成。",
                    "is_done": True,
                    "turns_remaining": max(0, max_turns - current_turn),
                    "convergence_reason": "timeout",
                    "is_timeout": True,
                }

            is_done = current_turn >= max_turns or score >= 80

            if is_done:
                convergence_reason = "max_turns_reached" if current_turn >= max_turns else "score_threshold_met"

                summary = await self.llm.chat_with_prompt(
                    "interview_summary",
                    variables={
                        "convergence_reason": convergence_reason,
                        "question_text": question_text,
                        "user_answer": user_answer,
                    },
                    temperature=0.7,
                    max_tokens=1000,
                )

                elapsed = time.monotonic() - turn_start
                if elapsed > timeout_seconds:
                    logger.warning(
                        f"handle_interview_turn: summary generation exceeded {timeout_seconds}s timeout."
                    )
                    summary = "评价生成超时，但本轮面试已结束。建议进入下一题或复习。"

                return {
                    "followup_question": None,
                    "score": score,
                    "feedback": summary,
                    "is_done": True,
                    "turns_remaining": 0,
                    "convergence_reason": convergence_reason,
                    "is_timeout": False,
                }

            followups = await self.generate_followup(question_text, user_answer)
            followup = followups[0] if followups else "请进一步深入解释你的观点。"

            return {
                "followup_question": followup,
                "score": score,
                "feedback": feedback,
                "is_done": False,
                "turns_remaining": max(0, max_turns - current_turn),
                "convergence_reason": None,
                "is_timeout": False,
            }

        except Exception as e:
            logger.error(f"handle_interview_turn: unexpected exception: {e}")
            return {
                "followup_question": None,
                "score": None,
                "feedback": "本轮处理失败，请重试。",
                "is_done": True,
                "turns_remaining": max(0, max_turns - current_turn),
                "convergence_reason": "manual_stop",
                "is_timeout": False,
            }

    async def handle_interview_turn_stream(
        self,
        session_id: str,
        current_turn: int,
        max_turns: int,
        question_text: str,
        user_answer: str,
    ) -> tuple:
        """Stream interview turn processing with SSE events.

        Returns (task_id, event_generator).
        Includes ReAct safety guards: turn validation, hard timeout, exception fallback.
        """
        start_time = time.monotonic()
        timeout_seconds = 60

        # Threshold (in characters) for emitting accumulated ``content`` events.
        _CONTENT_INTERVAL = 50

        def _sse(event_type: str, data: dict) -> str:
            data["event_type"] = event_type
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="interview_turn",
            source_id=None,
        )
        task_id = task.id

        if current_turn > max_turns:
            logger.warning(
                f"handle_interview_turn_stream: current_turn={current_turn} exceeds max_turns={max_turns}, "
                f"forcing interview end."
            )
            await task_manager.update_task(task_id, status="done", progress=1.0)

            async def _early_done_gen() -> AsyncGenerator[str, None]:
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "validation", "progress": 1.0, "current": "面试已结束：已达到最大轮次。", "elapsed": 0.0})
                yield _sse("progress", {"task_id": str(task_id), "phase": "validation", "progress": 1.0, "current": "面试已结束：已达到最大轮次。", "elapsed": 0.0})
                await task_manager.publish_task_event(str(task_id), {
                    "task_id": str(task_id), "status": "done",
                    "is_done": True, "score": None,
                    "feedback": f"面试已结束：已达到最大轮次 {max_turns}。",
                    "turns_remaining": 0,
                    "convergence_reason": "max_turns_reached",
                    "is_timeout": False,
                    "elapsed": 0.0,
                })
                yield _sse("done", {
                    "task_id": str(task_id), "status": "done",
                    "is_done": True, "score": None,
                    "feedback": f"面试已结束：已达到最大轮次 {max_turns}。",
                    "turns_remaining": 0,
                    "convergence_reason": "max_turns_reached",
                    "is_timeout": False,
                    "elapsed": 0.0,
                })

            return (task_id, _early_done_gen())

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.10, current_phase="evaluating")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "evaluating", "progress": 0.10, "current": f"正在评价第 {current_turn} 轮回答...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "evaluating", "progress": 0.10, "current": f"正在评价第 {current_turn} 轮回答...", "elapsed": round(time.monotonic() - start_time, 1)})

                evaluation = await self._evaluate_single_answer(question_text, user_answer)
                score = evaluation.get("score", 0)
                feedback = evaluation.get("feedback", "")

                elapsed = time.monotonic() - start_time
                if elapsed > timeout_seconds:
                    logger.warning(
                        f"handle_interview_turn_stream: turn processing exceeded {timeout_seconds}s timeout "
                        f"(elapsed={elapsed:.1f}s), forcing end."
                    )
                    await task_manager.update_task(task_id, status="done", progress=1.0)
                    await task_manager.publish_task_event(str(task_id), {
                        "task_id": str(task_id), "status": "done",
                        "is_done": True, "score": score,
                        "feedback": feedback or "处理超时，本轮评价未能完成。",
                        "turns_remaining": max(0, max_turns - current_turn),
                        "convergence_reason": "timeout",
                        "is_timeout": True,
                        "elapsed": round(elapsed, 1),
                    })
                    yield _sse("done", {
                        "task_id": str(task_id), "status": "done",
                        "is_done": True, "score": score,
                        "feedback": feedback or "处理超时，本轮评价未能完成。",
                        "turns_remaining": max(0, max_turns - current_turn),
                        "convergence_reason": "timeout",
                        "is_timeout": True,
                        "elapsed": round(elapsed, 1),
                    })
                    return

                await task_manager.publish_task_event(str(task_id), {
                    "task_id": str(task_id), "turn": current_turn,
                    "score": score, "feedback": feedback,
                })
                yield _sse("evaluation", {
                    "task_id": str(task_id), "turn": current_turn,
                    "score": score, "feedback": feedback,
                })

                is_done = current_turn >= max_turns or score >= 80

                if is_done:
                    convergence_reason = "max_turns_reached" if current_turn >= max_turns else "score_threshold_met"

                    await task_manager.update_task(task_id, progress=0.70, current_phase="summarizing")
                    await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "summarizing", "progress": 0.70, "current": "正在生成最终评价...", "elapsed": round(time.monotonic() - start_time, 1)})
                    yield _sse("progress", {"task_id": str(task_id), "phase": "summarizing", "progress": 0.70, "current": "正在生成最终评价...", "elapsed": round(time.monotonic() - start_time, 1)})

                    # Token-level streaming for interview summary
                    summary_parts: list[str] = []
                    last_content_len = 0
                    async for chunk in self.llm.stream_chat_with_prompt(
                        "interview_summary",
                        variables={
                            "convergence_reason": convergence_reason,
                            "question_text": question_text,
                            "user_answer": user_answer,
                        },
                        temperature=0.7,
                        max_tokens=1000,
                    ):
                        summary_parts.append(chunk)
                        await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "token": chunk})
                        yield _sse("token", {"task_id": str(task_id), "token": chunk})

                        # Emit accumulated content every ~50 chars
                        accumulated = "".join(summary_parts)
                        if len(accumulated) - last_content_len >= _CONTENT_INTERVAL:
                            last_content_len = len(accumulated)
                            await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "content": accumulated})
                            yield _sse("content", {"task_id": str(task_id), "content": accumulated})

                    summary = "".join(summary_parts)

                    elapsed = time.monotonic() - start_time
                    if elapsed > timeout_seconds:
                        logger.warning(
                            f"handle_interview_turn_stream: summary generation exceeded {timeout_seconds}s timeout."
                        )
                        summary = "评价生成超时，但本轮面试已结束。建议进入下一题或复习。"

                    await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "summary": summary})
                    yield _sse("summary", {"task_id": str(task_id), "summary": summary})

                    await task_manager.update_task(task_id, status="done", progress=1.0)
                    await task_manager.publish_task_event(str(task_id), {
                        "task_id": str(task_id), "status": "done",
                        "is_done": True, "score": score,
                        "feedback": summary,
                        "turns_remaining": 0,
                        "convergence_reason": convergence_reason,
                        "is_timeout": False,
                        "elapsed": round(elapsed, 1),
                    })
                    yield _sse("done", {
                        "task_id": str(task_id), "status": "done",
                        "is_done": True, "score": score,
                        "feedback": summary,
                        "turns_remaining": 0,
                        "convergence_reason": convergence_reason,
                        "is_timeout": False,
                        "elapsed": round(elapsed, 1),
                    })
                else:
                    await task_manager.update_task(task_id, progress=0.60, current_phase="generating_followup")
                    await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "generating_followup", "progress": 0.60, "current": "正在生成下一轮追问...", "elapsed": round(time.monotonic() - start_time, 1)})
                    yield _sse("progress", {"task_id": str(task_id), "phase": "generating_followup", "progress": 0.60, "current": "正在生成下一轮追问...", "elapsed": round(time.monotonic() - start_time, 1)})

                    followups = await self.generate_followup(question_text, user_answer, task_id=task_id)
                    followup = followups[0] if followups else "请进一步深入解释你的观点。"

                    await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "followup_question": followup})
                    yield _sse("followup", {"task_id": str(task_id), "followup_question": followup})

                    await task_manager.update_task(task_id, status="done", progress=1.0)
                    await task_manager.publish_task_event(str(task_id), {
                        "task_id": str(task_id), "status": "done",
                        "is_done": False, "score": score,
                        "feedback": feedback, "followup_question": followup,
                        "turns_remaining": max(0, max_turns - current_turn),
                        "convergence_reason": None,
                        "is_timeout": False,
                        "elapsed": round(time.monotonic() - start_time, 1),
                    })
                    yield _sse("done", {
                        "task_id": str(task_id), "status": "done",
                        "is_done": False, "score": score,
                        "feedback": feedback, "followup_question": followup,
                        "turns_remaining": max(0, max_turns - current_turn),
                        "convergence_reason": None,
                        "is_timeout": False,
                        "elapsed": round(time.monotonic() - start_time, 1),
                    })

            except asyncio.CancelledError:
                logger.warning(f"Stream interview turn cancelled for task {task_id}, marking as failed")
                try:
                    await task_manager.update_task(task_id, status="failed", progress=0.0, error_message="Connection cancelled")
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"Stream interview turn failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "error": "本轮处理失败，请重试。", "recoverable": True})
                yield _sse("error", {"task_id": str(task_id), "error": "本轮处理失败，请重试。", "recoverable": True})

        return (task_id, _event_generator())

    # ── Review Summary ──────────────────────────────────────────────

    async def generate_review_summary_stream(
        self,
        records_summary: str,
        weak_areas: list[dict],
    ) -> tuple:
        """Stream a Chinese review summary from aggregated study data.

        Returns (task_id, event_generator).
        """
        start_time = time.monotonic()

        # Threshold (in characters) for emitting accumulated ``content`` events.
        _CONTENT_INTERVAL = 50

        def _sse(event_type: str, data: dict) -> str:
            data["event_type"] = event_type
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="review_summary",
            source_id=None,
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.10, current_phase="generating")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "generating", "progress": 0.10, "current": "正在生成复盘总结...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "generating", "progress": 0.10, "current": "正在生成复盘总结...", "elapsed": round(time.monotonic() - start_time, 1)})

                weak_areas_text = json.dumps(weak_areas, ensure_ascii=False, indent=2)

                # Token-level true streaming with accumulated content events
                content_parts: list[str] = []
                last_content_len = 0
                async for chunk in self.llm.stream_chat_with_prompt(
                    "review_summary",
                    variables={
                        "records_summary": records_summary,
                        "weak_areas": weak_areas_text,
                    },
                    temperature=0.7,
                    max_tokens=2000,
                ):
                    content_parts.append(chunk)
                    await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "token": chunk})
                    yield _sse("token", {"task_id": str(task_id), "token": chunk})

                    # Emit accumulated content event every ~50 characters
                    accumulated = "".join(content_parts)
                    if len(accumulated) - last_content_len >= _CONTENT_INTERVAL:
                        last_content_len = len(accumulated)
                        await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "content": accumulated})
                        yield _sse("content", {"task_id": str(task_id), "content": accumulated})

                full_content = "".join(content_parts)

                await task_manager.update_task(task_id, progress=0.80, current_phase="yielding")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "yielding", "progress": 0.80, "current": "正在输出结果...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "yielding", "progress": 0.80, "current": "正在输出结果...", "elapsed": round(time.monotonic() - start_time, 1)})

                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "content": full_content})
                yield _sse("content", {"task_id": str(task_id), "content": full_content})

                await task_manager.update_task(task_id, status="done", progress=1.0)
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})

            except Exception as e:
                logger.error(f"Stream review summary failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "error": str(e), "recoverable": False})
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    # ── Review Recommendations ──────────────────────────────────────

    async def generate_review_recommendations_stream(
        self,
        weak_areas: list[dict],
        mastery_trend: str,
    ) -> tuple:
        """Stream improvement recommendations from weak areas.

        Returns (task_id, event_generator).
        """
        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            data["event_type"] = event_type
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="review_recommendations",
            source_id=None,
        )
        task_id = task.id

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.10, current_phase="generating")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "generating", "progress": 0.10, "current": "正在生成改进建议...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "generating", "progress": 0.10, "current": "正在生成改进建议...", "elapsed": round(time.monotonic() - start_time, 1)})

                weak_areas_text = json.dumps(weak_areas, ensure_ascii=False, indent=2)

                response = await self.llm.chat_json_with_prompt(
                    "review_recommendations",
                    variables={
                        "weak_areas": weak_areas_text,
                        "mastery_trend": mastery_trend,
                    },
                    temperature=0.7,
                    max_tokens=1000,
                )

                recommendations = response if isinstance(response, list) else response.get("recommendations", [])

                await task_manager.update_task(task_id, progress=0.80, current_phase="yielding")
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "phase": "yielding", "progress": 0.80, "current": "正在输出结果...", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("progress", {"task_id": str(task_id), "phase": "yielding", "progress": 0.80, "current": "正在输出结果...", "elapsed": round(time.monotonic() - start_time, 1)})

                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "recommendations": recommendations})
                yield _sse("result", {"task_id": str(task_id), "recommendations": recommendations})

                await task_manager.update_task(task_id, status="done", progress=1.0)
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})
                yield _sse("done", {"task_id": str(task_id), "status": "done", "elapsed": round(time.monotonic() - start_time, 1)})

            except Exception as e:
                logger.error(f"Stream review recommendations failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                await task_manager.publish_task_event(str(task_id), {"task_id": str(task_id), "error": str(e), "recoverable": False})
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    # ── LangGraph Streaming ─────────────────────────────────────────

    async def run_interview_graph_stream(
        self,
        input_text: str,
        *,
        domain: str | None = None,
        max_turns: int = 5,
    ) -> tuple:
        """Run the interview LangGraph workflow with SSE streaming.

        Uses LangGraph's astream() to yield per-node execution events.
        Returns (task_id, event_generator).
        """
        from app.graphs.interview_graph import interview_graph

        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="interview_graph",
            source_id=None,
        )
        task_id = task.id

        initial_state: dict = {
            "input_text": input_text,
            "input_source": "user",
            "session_id": f"interview_{uuid.uuid4().hex[:12]}",
            "metadata": {"max_turns": max_turns, "followup_turns": 0},
        }
        if domain:
            initial_state["domain_type"] = domain

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.05, current_phase="starting")
                yield _sse("progress", {"task_id": str(task_id), "phase": "starting", "progress": 0.05, "current": "正在启动面试工作流...", "elapsed": round(time.monotonic() - start_time, 1)})

                node_progress = 0
                total_nodes = 7  # extractor, classifier, retriever, interviewer, evaluator, explainer, persister

                async for node_output in interview_graph.astream(initial_state):
                    for node_name, state_update in node_output.items():
                        node_progress += 1
                        progress_val = round(0.10 + (0.80 * node_progress / total_nodes), 2)

                        await task_manager.update_task(
                            task_id, progress=progress_val, current_phase=node_name
                        )

                        # Build concise summary of what this node produced
                        summary_parts = []
                        if node_name == "extractor":
                            summary_parts.append("内容提取完成")
                        elif node_name == "classifier":
                            summary_parts.append(f"分类完成: {state_update.get('domain_type', '?')} / 难度{state_update.get('difficulty_level', '?')}")
                        elif node_name == "retriever":
                            hits = len(state_update.get("retrieval_hits", []))
                            summary_parts.append(f"检索到 {hits} 条相关内容")
                        elif node_name == "explainer":
                            summary_parts.append("讲解生成完成")
                        elif node_name == "interviewer":
                            followups = state_update.get("followup_questions", [])
                            summary_parts.append(f"生成 {len(followups)} 条追问")
                        elif node_name == "evaluator":
                            score = state_update.get("user_score", 0)
                            summary_parts.append(f"评分: {score}")
                        elif node_name == "persister":
                            summary_parts.append("结果已标记保存")

                        yield _sse("node_completed", {
                            "task_id": str(task_id),
                            "node": node_name,
                            "progress": progress_val,
                            "summary": " / ".join(summary_parts),
                            "state_update": {k: v for k, v in state_update.items() if k != "chat_history" and not k.startswith("_")},
                            "elapsed": round(time.monotonic() - start_time, 1),
                        })

                        # If evaluator scored high enough, yield followup questions
                        if node_name == "evaluator" and state_update.get("review_needed"):
                            yield _sse("review_hint", {
                                "task_id": str(task_id),
                                "score": state_update.get("user_score", 0),
                                "feedback": state_update.get("feedback", ""),
                            })

                await task_manager.update_task(task_id, status="done", progress=1.0)
                yield _sse("done", {
                    "task_id": str(task_id),
                    "status": "done",
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

            except asyncio.CancelledError:
                logger.warning(f"LangGraph interview stream cancelled for task {task_id}")
                try:
                    await task_manager.update_task(task_id, status="failed", progress=0.0, error_message="Connection cancelled")
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"LangGraph interview stream failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    async def run_explanation_graph_stream(
        self,
        input_text: str,
        *,
        depth: str = "standard",
    ) -> tuple:
        """Run the explanation LangGraph workflow with SSE streaming.

        Uses LangGraph's astream() for per-node events.
        Returns (task_id, event_generator).
        """
        from app.graphs.explanation_graph import explanation_graph

        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="explanation_graph",
            source_id=None,
        )
        task_id = task.id

        initial_state: dict = {
            "input_text": input_text,
            "input_source": "user",
            "session_id": f"explain_{uuid.uuid4().hex[:12]}",
            "metadata": {"depth": depth},
        }

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.05, current_phase="starting")
                yield _sse("progress", {"task_id": str(task_id), "phase": "starting", "progress": 0.05, "current": "正在启动讲解工作流...", "elapsed": round(time.monotonic() - start_time, 1)})

                node_progress = 0
                total_nodes = 4  # extractor, classifier, explainer, persister

                async for node_output in explanation_graph.astream(initial_state):
                    for node_name, state_update in node_output.items():
                        node_progress += 1
                        progress_val = round(0.10 + (0.80 * node_progress / total_nodes), 2)

                        await task_manager.update_task(
                            task_id, progress=progress_val, current_phase=node_name
                        )

                        summary = ""
                        if node_name == "extractor":
                            summary = "内容提取完成"
                        elif node_name == "classifier":
                            summary = f"分类完成: {state_update.get('domain_type', '?')}"
                        elif node_name == "explainer":
                            summary = "讲解生成完成"
                        elif node_name == "persister":
                            summary = "结果已标记保存"

                        yield _sse("node_completed", {
                            "task_id": str(task_id),
                            "node": node_name,
                            "progress": progress_val,
                            "summary": summary,
                            "state_update": {k: v for k, v in state_update.items() if k != "chat_history" and not k.startswith("_")},
                            "elapsed": round(time.monotonic() - start_time, 1),
                        })

                        # Yield explanation content when explainer node finishes
                        if node_name == "explainer":
                            yield _sse("content", {
                                "task_id": str(task_id),
                                "answer_short": state_update.get("answer_short", ""),
                                "answer_detail": state_update.get("answer_detail", ""),
                                "explanation": state_update.get("explanation", ""),
                                "common_pitfalls": state_update.get("common_pitfalls", ""),
                            })

                await task_manager.update_task(task_id, status="done", progress=1.0)
                yield _sse("done", {
                    "task_id": str(task_id),
                    "status": "done",
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

            except asyncio.CancelledError:
                logger.warning(f"LangGraph explanation stream cancelled for task {task_id}")
                try:
                    await task_manager.update_task(task_id, status="failed", progress=0.0, error_message="Connection cancelled")
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"LangGraph explanation stream failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    async def run_review_graph_stream(
        self,
        question_id: str = "",
        question_text: str = "",
        user_score: int = 0,
    ) -> tuple:
        """Run the review LangGraph workflow with SSE streaming.

        Uses LangGraph's astream() for per-node events.
        Returns (task_id, event_generator).
        """
        from app.graphs.review_graph import review_graph

        start_time = time.monotonic()

        def _sse(event_type: str, data: dict) -> str:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n"

        task_manager = TaskManager(self.session)
        task = await task_manager.create_task(
            task_type="review_graph",
            source_id=question_id or None,
        )
        task_id = task.id

        initial_state: dict = {
            "question_id": question_id,
            "question_text": question_text,
            "user_score": user_score,
            "session_id": f"review_{uuid.uuid4().hex[:12]}",
        }

        async def _event_generator() -> AsyncGenerator[str, None]:
            try:
                await task_manager.update_task(task_id, status="processing", progress=0.05, current_phase="starting")
                yield _sse("progress", {"task_id": str(task_id), "phase": "starting", "progress": 0.05, "current": "正在启动复习工作流...", "elapsed": round(time.monotonic() - start_time, 1)})

                node_progress = 0
                total_nodes = 4  # load_question, evaluator, schedule, persister

                async for node_output in review_graph.astream(initial_state):
                    for node_name, state_update in node_output.items():
                        node_progress += 1
                        progress_val = round(0.10 + (0.80 * node_progress / total_nodes), 2)

                        await task_manager.update_task(
                            task_id, progress=progress_val, current_phase=node_name
                        )

                        summary = ""
                        if node_name == "load_question":
                            summary = "题目加载完成"
                        elif node_name == "evaluator":
                            summary = f"复习评价完成: 掌握度{state_update.get('mastery_level', '?')}"
                        elif node_name == "schedule":
                            summary = f"复习周期设定完成: {state_update.get('review_cycle', '?')}天"
                        elif node_name == "persister":
                            summary = "结果已标记保存"

                        yield _sse("node_completed", {
                            "task_id": str(task_id),
                            "node": node_name,
                            "progress": progress_val,
                            "summary": summary,
                            "state_update": {k: v for k, v in state_update.items() if k != "chat_history" and not k.startswith("_")},
                            "elapsed": round(time.monotonic() - start_time, 1),
                        })

                        # Yield review schedule when schedule node finishes
                        if node_name == "schedule":
                            yield _sse("review_schedule", {
                                "task_id": str(task_id),
                                "mastery_level": state_update.get("mastery_level", 1),
                                "review_cycle": state_update.get("review_cycle", 1),
                                "review_needed": state_update.get("review_needed", False),
                            })

                await task_manager.update_task(task_id, status="done", progress=1.0)
                yield _sse("done", {
                    "task_id": str(task_id),
                    "status": "done",
                    "elapsed": round(time.monotonic() - start_time, 1),
                })

            except asyncio.CancelledError:
                logger.warning(f"LangGraph review stream cancelled for task {task_id}")
                try:
                    await task_manager.update_task(task_id, status="failed", progress=0.0, error_message="Connection cancelled")
                except Exception:
                    pass
                raise

            except Exception as e:
                logger.error(f"LangGraph review stream failed: {e}")
                await task_manager.update_task(task_id, status="failed", progress=0.0, error_message=str(e)[:500])
                yield _sse("error", {"task_id": str(task_id), "error": str(e), "recoverable": False})

        return (task_id, _event_generator())

    # ── Internal helpers ────────────────────────────────────────────

    async def _evaluate_single_answer(self, question_text: str, user_answer: str) -> dict:
        """Evaluate a single answer (lightweight, for interview flow).

        Uses: interview_single_eval prompt from registry.
        """
        try:
            return await self.llm.chat_json_with_prompt(
                "interview_single_eval",
                variables={"question_text": question_text, "user_answer": user_answer},
                temperature=0.3,
                max_tokens=500,
            )
        except Exception:
            return {"score": 50, "feedback": "评价失败，请重试。", "is_pass": False}
