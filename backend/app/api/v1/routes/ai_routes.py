"""AI routes — explain, interview, evaluate (streaming)."""

from typing import AsyncGenerator
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession, get_user_context, UserContext
from app.domain.schemas import (
    InterviewStartRequest,
    InterviewStartResponse,
)
from app.services.ai_service import AIService

router = APIRouter()


@router.post("/interview/start", response_model=InterviewStartResponse)
async def start_interview(session: DbSession, data: InterviewStartRequest, user_ctx: UserContext = Depends(get_user_context)):
    """Start an interview simulation."""
    service = AIService(session)
    result = await service.start_interview(
        question_id=data.question_id,
        domain=data.domain,
        max_turns=data.max_turns,
    )

    return InterviewStartResponse(
        session_id=result["session_id"],
        first_question=result["first_question"],
        max_turns=result["max_turns"],
    )


class ExplainStreamRequest(BaseModel):
    question_id: UUID | None = None
    question_text: str | None = None
    depth: str = "standard"


class EvaluationStreamRequest(BaseModel):
    question_id: UUID
    user_answer: str


class InterviewTurnStreamRequest(BaseModel):
    session_id: str
    current_turn: int = 1
    max_turns: int = 5
    question_text: str = ""
    user_answer: str = ""


@router.post("/explain-stream")
async def explain_stream(
    body: ExplainStreamRequest,
    session: DbSession,
):
    """Start question explanation task. Returns task_id for SSE event consumption."""
    if body.question_id is None and not body.question_text:
        raise ValueError("Either question_id or question_text must be provided")

    service = AIService(session)
    task_id, event_gen = await service.explain_question_stream(
        question_id=body.question_id, question_text=body.question_text, depth=body.depth,
    )

    # Commit the task record immediately so the SSE events endpoint
    # can find it — the frontend polls /tasks/{id}/events right away.
    await session.commit()

    # Consume the generator in the background with its own DB session.
    # The generator's TaskManager needs a live session for update_task() calls.
    # We pass the original task_id so the background task updates the SAME
    # record the frontend subscribed to — not a new one.
    from app.infra.db.session import async_session

    async def _run_task() -> None:
        async with async_session() as bg_session:
            bg_service = AIService(bg_session)
            try:
                _, bg_gen = await bg_service.explain_question_stream(
                    question_id=body.question_id,
                    question_text=body.question_text,
                    depth=body.depth,
                    existing_task_id=task_id,
                )
                async for _event in bg_gen:
                    pass
                await bg_session.commit()
            except Exception:
                await bg_session.rollback()
                raise

    asyncio.create_task(_run_task())
    return {"task_id": str(task_id)}


@router.post("/evaluate-stream")
async def evaluate_stream(
    body: EvaluationStreamRequest,
):
    """Stream answer evaluation via SSE."""
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.evaluate_answer_stream(
                question_id=body.question_id, user_answer=body.user_answer,
            )
            try:
                async for event in event_gen:
                    yield event
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/interview/turn-stream")
async def interview_turn_stream(
    body: InterviewTurnStreamRequest,
):
    """Stream interview turn processing via SSE."""
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.handle_interview_turn_stream(
                session_id=body.session_id, current_turn=body.current_turn, max_turns=body.max_turns,
                question_text=body.question_text, user_answer=body.user_answer,
            )
            try:
                async for event in event_gen:
                    yield event
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── LangGraph Streaming Endpoints ─────────────────────────────────────


@router.post("/graph/interview-stream")
async def interview_graph_stream(
    input_text: str,
    domain: str | None = None,
    max_turns: int = 5,
):
    """Run the full interview LangGraph workflow with SSE per-node events.

    Each node completion emits a `node_completed` event with the node name,
    progress, and state update. The final `done` event signals workflow completion.
    """
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.run_interview_graph_stream(
                input_text=input_text, domain=domain, max_turns=max_turns,
            )
            try:
                async for event in event_gen:
                    yield event
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/graph/explain-stream")
async def explanation_graph_stream(
    input_text: str,
    depth: str = "standard",
):
    """Run the explanation LangGraph workflow with SSE per-node events.

    Emits `node_completed` events and a `content` event when the explainer
    node finishes with the generated explanation.
    """
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.run_explanation_graph_stream(
                input_text=input_text, depth=depth,
            )
            try:
                async for event in event_gen:
                    yield event
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/graph/review-stream")
async def review_graph_stream(
    question_id: str = "",
    question_text: str = "",
    user_score: int = 0,
):
    """Run the review LangGraph workflow with SSE per-node events.

    Emits `node_completed` events and a `review_schedule` event with
    mastery level and review cycle information.
    """
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.run_review_graph_stream(
                question_id=question_id, question_text=question_text, user_score=user_score,
            )
            try:
                async for event in event_gen:
                    yield event
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
