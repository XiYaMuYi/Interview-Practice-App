"""Import routes — file upload and text paste."""

from fastapi import APIRouter, File, Form, UploadFile
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


@router.get("/supported-formats")
async def supported_formats():
    """Return list of supported file extensions for import."""
    from app.infra.parsers import ParserFactory

    return {"extensions": ParserFactory.supported_extensions()}
