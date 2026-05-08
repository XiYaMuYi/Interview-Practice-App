"""PDF parser — extracts text from PDF files using PyMuPDF."""

import hashlib
from pathlib import Path

from app.core.exceptions import ParseError
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]


class PDFParser:
    """Extract text content from PDF files."""

    supported_extensions = {".pdf"}

    async def parse(self, file_path: str | Path) -> str:
        """Read a PDF and return its full text content."""
        if fitz is None:
            raise ParseError("PyMuPDF (fitz) is not installed. Run: pip install pymupdf")

        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"File not found: {path}")

        try:
            doc = fitz.open(str(path))
            pages = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    pages.append(f"--- Page {page_num + 1} ---\n{text}")
            doc.close()

            full_text = "\n\n".join(pages)
            logger.info(f"Parsed PDF: {path.name}, {len(pages)} pages, {len(full_text)} chars")
            return full_text

        except Exception as e:
            raise ParseError(f"Failed to parse PDF '{path.name}': {e}")

    def compute_hash(self, file_path: str | Path) -> str:
        """SHA-256 hash of the file contents."""
        path = Path(file_path)
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()
