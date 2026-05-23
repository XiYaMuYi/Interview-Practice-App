"""AI routes — explain, interview, evaluate."""

from typing import AsyncGenerator
import asyncio
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.domain.schemas import (
    AIExplanationRequest,
    AIExplanationResponse,
    EvaluationRequest,
    EvaluationResponse,
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewStartRequest,
    InterviewStartResponse,
)
from app.services.ai_service import AIService

router = APIRouter()

# Simple in-memory store for interview sessions (MVP — replace with DB later)
_interview_sessions: dict[str, dict] = {}


@router.post("/explain", response_model=AIExplanationResponse)
async def explain_question(session: DbSession, data: AIExplanationRequest):
    """Get an AI explanation for a question."""
    service = AIService(session)
    result = await service.explain_question(
        question_id=data.question_id,
        question_text=data.question_text,
        depth=data.depth,
    )
    return AIExplanationResponse(
        answer_short=result.get("answer_short") or "",
        answer_detail=result.get("answer_detail") or "",
        explanation=result.get("explanation") or "",
        knowledge_points=[],
        common_pitfalls=None,
        related_questions=[],
    )


@router.post("/interview/start", response_model=InterviewStartResponse)
async def start_interview(session: DbSession, data: InterviewStartRequest):
    """Start an interview simulation."""
    service = AIService(session)
    result = await service.start_interview(
        question_id=data.question_id,
        domain=data.domain,
        max_turns=data.max_turns,
    )

    # Store session state
    _interview_sessions[result["session_id"]] = {
        "current_turn": 0,
        "max_turns": data.max_turns,
        "question_id": str(data.question_id) if data.question_id else None,
        "last_question": result["first_question"],
    }

    return InterviewStartResponse(
        session_id=result["session_id"],
        first_question=result["first_question"],
        max_turns=result["max_turns"],
    )


@router.post("/interview/answer", response_model=InterviewAnswerResponse)
async def submit_interview_answer(session: DbSession, data: InterviewAnswerRequest):
    """Submit an answer during an interview."""
    service = AIService(session)
    session_data = _interview_sessions.get(data.session_id)
    if not session_data:
        return {"followup_question": None, "score": None, "feedback": "Session not found", "is_done": True}

    session_data["current_turn"] += 1
    current_turn = session_data["current_turn"]

    result = await service.handle_interview_turn(
        session_id=data.session_id,
        current_turn=current_turn,
        max_turns=session_data["max_turns"],
        question_text=session_data["last_question"],
        user_answer=data.answer,
    )

    # Update session state with the new question
    if not result["is_done"] and result["followup_question"]:
        session_data["last_question"] = result["followup_question"]

    return InterviewAnswerResponse(
        followup_question=result.get("followup_question"),
        score=result.get("score"),
        feedback=result.get("feedback"),
        is_done=result["is_done"],
        turns_remaining=result.get("turns_remaining"),
        convergence_reason=result.get("convergence_reason"),
        is_timeout=result.get("is_timeout"),
    )


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_answer(session: DbSession, data: EvaluationRequest):
    """Evaluate a user's answer to a question."""
    service = AIService(session)
    result = await service.evaluate_answer(
        question_id=data.question_id,
        user_answer=data.user_answer,
    )
    return EvaluationResponse(
        score=result["score"],
        feedback=result["feedback"],
        missing_points=result.get("missing_points", []),
        is_pass=result["is_pass"],
        mastery_level=result.get("mastery_level", 1),
    )


@router.post("/followup")
async def generate_followup(session: DbSession, question: str, answer: str):
    """Generate follow-up questions based on a question and user answer."""
    service = AIService(session)
    followups = await service.generate_followup(question, answer)
    return {"followup_questions": followups}


class ExplainStreamRequest(BaseModel):
    question_id: UUID | None = None
    question_text: str | None = None
    depth: str = "standard"


@router.post("/explain-stream")
async def explain_stream(
    body: ExplainStreamRequest,
    session: DbSession,
):
    """Start question explanation task. Returns task_id for SSE event consumption."""
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
    question_id: UUID,
    user_answer: str,
):
    """Stream answer evaluation via SSE."""
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.evaluate_answer_stream(
                question_id=question_id, user_answer=user_answer,
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
    session_id: str,
    current_turn: int = 1,
    max_turns: int = 5,
    question_text: str = "",
    user_answer: str = "",
):
    """Stream interview turn processing via SSE."""
    from app.infra.db.session import async_session

    async def _stream() -> AsyncGenerator[str, None]:
        async with async_session() as session:
            service = AIService(session)
            task_id, event_gen = await service.handle_interview_turn_stream(
                session_id=session_id, current_turn=current_turn, max_turns=max_turns,
                question_text=question_text, user_answer=user_answer,
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
