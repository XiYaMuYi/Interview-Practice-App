"""AI routes — explain, interview, evaluate."""

from uuid import UUID

from fastapi import APIRouter

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
        answer_short=result.get("answer_short", ""),
        answer_detail=result.get("answer_detail", ""),
        explanation=result.get("explanation", ""),
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
