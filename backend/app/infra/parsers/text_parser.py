"""Text parser — handles plain text files."""

import hashlib
from pathlib import Path

from app.core.exceptions import ParseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class TextParser:
    """Read and clean plain text files."""

    supported_extensions = {".txt", ".md", ".text"}

    async def parse(self, file_path: str | Path) -> str:
        """Read a text file and return its content."""
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"File not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            # Normalize line endings
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            logger.info(f"Parsed text: {path.name}, {len(content)} chars")
            return content

        except UnicodeDecodeError as e:
            raise ParseError(f"File '{path.name}' is not valid UTF-8 text: {e}")
        except Exception as e:
            raise ParseError(f"Failed to read text file '{path.name}': {e}")

    def compute_hash(self, file_path: str | Path) -> str:
        """SHA-256 hash of the file contents."""
        path = Path(file_path)
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()
