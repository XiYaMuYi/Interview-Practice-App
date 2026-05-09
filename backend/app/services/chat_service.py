"""Chat service — session management, history, and LLM streaming."""

import uuid
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.models import ChatHistory, Question
from app.infra.llm.gateway import llm_gateway, prompt_registry
from app.infra.repositories import ChatHistoryRepository

logger = get_logger(__name__)


class ChatService:
    """Manages chat sessions, message history, and LLM interactions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chat_repo = ChatHistoryRepository(session)

    # ── Session Management ──────────────────────────────────────────

    async def create_session(self, *, user_id: str | None = None, mode: str = "chat") -> str:
        """Create a new chat session and return the session ID."""
        session_id = f"{mode}_{uuid.uuid4().hex[:12]}"
        # Create a system message to mark session start
        system_msg = ChatHistory(
            session_id=session_id,
            user_id=user_id,
            role="system",
            message=f"Session started. Mode: {mode}",
            message_type="system",
        )
        await self.chat_repo.create(system_msg)
        logger.info(f"Chat session created: {session_id}, mode={mode}")
        return session_id

    async def get_sessions(self, *, user_id: str | None = None, offset: int = 0, limit: int = 20) -> list[dict]:
        """List chat sessions with message counts."""
        stmt = (
            select(ChatHistory.session_id, ChatHistory.created_at)
            .group_by(ChatHistory.session_id, ChatHistory.created_at)
            .order_by(ChatHistory.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        rows = result.all()

        sessions = []
        for row in rows:
            count_stmt = select(__import__("sqlalchemy").func.count()).select_from(ChatHistory).where(
                ChatHistory.session_id == row[0]
            )
            count_result = await self.session.exec(count_stmt)
            sessions.append({
                "session_id": row[0],
                "created_at": row[1],
                "message_count": count_result.one(),
            })
        return sessions

    async def get_sessions_with_count(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """List chat sessions with real total count."""
        from sqlalchemy import func as sa_func

        offset = (page - 1) * page_size

        # Count distinct sessions
        count_stmt = select(sa_func.count(sa_func.distinct(ChatHistory.session_id)))
        total = (await self.session.exec(count_stmt)).one()

        # Data query
        stmt = (
            select(ChatHistory.session_id, ChatHistory.created_at)
            .group_by(ChatHistory.session_id, ChatHistory.created_at)
            .order_by(ChatHistory.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.exec(stmt)
        rows = result.all()

        sessions = []
        for row in rows:
            count_stmt = select(sa_func.count()).select_from(ChatHistory).where(
                ChatHistory.session_id == row[0]
            )
            count_result = await self.session.exec(count_stmt)
            sessions.append({
                "session_id": row[0],
                "created_at": row[1],
                "message_count": count_result.one(),
            })
        return sessions, total

    # ── Message History ─────────────────────────────────────────────

    async def get_history(self, session_id: str) -> list[ChatHistory]:
        """Get full chat history for a session, ordered by time."""
        return list(await self.chat_repo.get_by_session(session_id))

    async def save_message(
        self,
        session_id: str,
        role: str,
        message: str,
        *,
        message_type: str | None = None,
        related_question_id: UUID | None = None,
        user_id: str | None = None,
    ) -> ChatHistory:
        """Persist a chat message."""
        record = ChatHistory(
            session_id=session_id,
            user_id=user_id,
            role=role,
            message=message,
            message_type=message_type,
            related_question_id=related_question_id,
        )
        return await self.chat_repo.create(record)

    # ── Chat with LLM ───────────────────────────────────────────────

    async def chat(
        self,
        session_id: str,
        user_message: str,
        *,
        mode: str = "chat",
        related_question_id: UUID | None = None,
        user_id: str | None = None,
    ) -> str:
        """Send a user message, get LLM response, and persist both."""
        # Save user message
        await self.save_message(
            session_id, "user", user_message,
            related_question_id=related_question_id, user_id=user_id,
        )

        # Build messages from history
        messages = await self._build_messages(session_id, user_message, mode=mode)

        # Load context question if applicable
        question_context = ""
        if related_question_id:
            question = await self.session.get(Question, related_question_id)
            if question:
                question_context = f"\n\n相关题目：{question.title}\n{question.content[:1000]}"

        # Select prompt based on mode
        if mode == "interview":
            system_prompt = self._get_interview_system_prompt(question_context)
        elif mode == "explain":
            system_prompt = self._get_explain_system_prompt(question_context)
        else:
            system_prompt = self._get_chat_system_prompt(question_context)

        messages = [{"role": "system", "content": system_prompt}] + messages

        # Call LLM
        response = await llm_gateway.chat(messages, temperature=0.7, max_tokens=2048)

        # Save assistant response
        await self.save_message(session_id, "assistant", response, message_type=mode, user_id=user_id)

        return response

    async def stream_chat(
        self,
        session_id: str,
        user_message: str,
        *,
        mode: str = "chat",
        related_question_id: UUID | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response, save user message immediately and assistant at end."""
        # Save user message
        await self.save_message(
            session_id, "user", user_message,
            related_question_id=related_question_id, user_id=user_id,
        )

        # Build messages
        messages = await self._build_messages(session_id, user_message, mode=mode)

        question_context = ""
        if related_question_id:
            question = await self.session.get(Question, related_question_id)
            if question:
                question_context = f"\n\n相关题目：{question.title}\n{question.content[:1000]}"

        if mode == "interview":
            system_prompt = self._get_interview_system_prompt(question_context)
        elif mode == "explain":
            system_prompt = self._get_explain_system_prompt(question_context)
        else:
            system_prompt = self._get_chat_system_prompt(question_context)

        messages = [{"role": "system", "content": system_prompt}] + messages

        # Stream response and accumulate full text
        full_response = []
        async for chunk in llm_gateway.stream_chat(messages, temperature=0.7, max_tokens=2048):
            full_response.append(chunk)
            yield chunk

        # Save complete assistant response
        await self.save_message(
            session_id, "assistant", "".join(full_response),
            message_type=mode, user_id=user_id,
        )

    # ── Internal helpers ────────────────────────────────────────────

    async def _build_messages(self, session_id: str, latest_message: str, *, mode: str = "chat") -> list[dict]:
        """Build message list from chat history, limited to last 20 messages."""
        history = await self.chat_repo.get_by_session(session_id)
        # Exclude system messages, limit to last 20
        msgs = [h for h in history if h.role != "system"][-20:]
        return [{"role": h.role, "content": h.message} for h in msgs]

    def _get_chat_system_prompt(self, question_context: str) -> str:
        return (
            "你是一个AI面试学习助手。帮助用户理解面试相关的技术问题。\n"
            "回答要清晰、结构化，适合面试表达。\n"
            f"{question_context}"
        )

    def _get_explain_system_prompt(self, question_context: str) -> str:
        return (
            "你是一个技术面试讲解专家。请对题目进行分层讲解：\n"
            "1. 一句话核心答案\n"
            "2. 面试版回答（30秒-1分钟）\n"
            "3. 深入讲解（关键技术细节）\n"
            "4. 常见易错点\n"
            f"{question_context}"
        )

    def _get_interview_system_prompt(self, question_context: str) -> str:
        return (
            "你是一个严格但专业的AI面试官。请模拟真实的技术面试：\n"
            "- 根据用户的回答，决定是继续追问还是进入评价\n"
            "- 追问要逐步深入，暴露用户回答中的空洞\n"
            "- 不要一次给太多提示\n"
            "- 如果用户回答得很好，继续提高难度\n"
            "- 如果用户回答不好，引导式提问帮助理解\n"
            f"{question_context}"
        )
