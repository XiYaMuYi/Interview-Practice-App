"""Import routes — file upload and text paste."""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from app.core.exceptions import ParseError
from app.api.deps import DbSession
from app.services.import_service import ImportService

router = APIRouter()


@router.post("/text")
async def import_text(session: DbSession, text: str = Form(...)):
    """Import questions from pasted text."""
    service = ImportService(session)
    result = await service.import_text(text)
    return {"status": "success", **result}


@router.post("/file")
async def import_file(session: DbSession, file: UploadFile = File(...)):
    """Import questions from an uploaded file (PDF, DOCX, TXT, MD)."""
    content = await file.read()
    if not content:
        raise ParseError("Uploaded file is empty")

    service = ImportService(session)
    result = await service.import_file(file_name=file.filename or "unknown", content=content)
    return {"status": "success", **result}


@router.post("/upload")
async def upload_file(session: DbSession, file: UploadFile = File(...)):
    """Upload a file for parsing and question extraction (alias for /file)."""
    content = await file.read()
    if not content:
        raise ParseError("Uploaded file is empty")

    service = ImportService(session)
    result = await service.import_file(file_name=file.filename or "unknown", content=content)
    return {"status": "success", **result}


@router.get("/supported-formats")
async def supported_formats():
    """Return list of supported file extensions for import."""
    from app.infra.parsers import ParserFactory

    extensions = [ext.lstrip(".") for ext in ParserFactory.supported_extensions()]
    return {"extensions": extensions}


@router.post("/text-stream")
async def import_text_stream(
    session: DbSession,
    text: str = Form(...),
):
    """Stream text import with SSE progress events."""
    service = ImportService(session)
    task_id, event_gen = await service.import_text_stream(text)

    return StreamingResponse(
        event_gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/text-stream-async")
async def import_text_stream_async(
    session: DbSession,
    text: str = Form(...),
    source_type: str = Form(default="paste"),
):
    """Submit text import to RabbitMQ queue for async processing.

    Returns a task_id that can be used to track progress via
    GET /api/v1/tasks/{task_id} or SSE event stream.
    Falls back to synchronous stream if RabbitMQ is unavailable.
    """
    service = ImportService(session)
    result = await service.import_text_stream_async(text, source_type=source_type)
    return {"status": "success", **result}
