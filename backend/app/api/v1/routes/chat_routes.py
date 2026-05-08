"""Chat routes — sessions, history, messaging with streaming support."""

import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.domain.schemas import ChatHistoryResponse, ChatMessageRequest, ChatResponse, ChatSessionListResponse
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/session")
async def create_chat_session(session: DbSession, mode: str = Query("chat", description="chat, interview, or explain")):
    """Create a new chat session."""
    service = ChatService(session)
    session_id = await service.create_session(mode=mode)
    return {"session_id": session_id, "mode": mode}


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    session: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List all chat sessions."""
    service = ChatService(session)
    sessions = await service.get_sessions(offset=offset, limit=limit)
    return ChatSessionListResponse(sessions=sessions, total=len(sessions))


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session: DbSession, session_id: str):
    """Get full chat history for a session."""
    service = ChatService(session)
    history = await service.get_history(session_id)
    messages = [
        {
            "role": h.role,
            "message": h.message,
            "message_type": h.message_type,
            "related_question_id": h.related_question_id,
            "evaluation_score": h.evaluation_score,
            "evaluation_summary": h.evaluation_summary,
        }
        for h in history
        if h.role != "system"
    ]
    return ChatHistoryResponse(session_id=session_id, messages=messages, total=len(messages))


@router.post("/message", response_model=ChatResponse)
async def send_message(session: DbSession, data: ChatMessageRequest):
    """Send a chat message and get the LLM response."""
    service = ChatService(session)

    session_id = data.session_id
    if not session_id:
        session_id = await service.create_session(mode=data.mode)

    response_text = await service.chat(
        session_id=session_id,
        user_message=data.message,
        mode=data.mode,
        related_question_id=data.related_question_id,
    )

    return ChatResponse(
        session_id=session_id,
        assistant_message=response_text,
        related_question_id=data.related_question_id,
    )


@router.post("/message/stream")
async def send_message_stream(session: DbSession, data: ChatMessageRequest):
    """Send a chat message and stream the LLM response as SSE."""
    service = ChatService(session)

    session_id = data.session_id
    if not session_id:
        session_id = await service.create_session(mode=data.mode)

    async def event_stream():
        async for chunk in service.stream_chat(
            session_id=session_id,
            user_message=data.message,
            mode=data.mode,
            related_question_id=data.related_question_id,
        ):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
