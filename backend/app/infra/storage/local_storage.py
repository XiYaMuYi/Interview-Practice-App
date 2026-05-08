"""Local file storage — saves uploaded files with organized directory structure."""

import os
import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppException


class StorageError(AppException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail, code="STORAGE_ERROR")


class LocalStorage:
    """Local filesystem storage with date-based subdirectories and unique filenames."""

    def __init__(self) -> None:
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    async def save(self, file_name: str, content: bytes, *, subfolder: str | None = None) -> str:
        """Save file content and return the relative path string."""
        if len(content) > self.max_bytes:
            raise StorageError(f"File too large: {len(content)} bytes exceeds {self.max_bytes} byte limit")

        # Build directory: uploads/YYYY/MM/DD/ or uploads/{subfolder}/
        if subfolder:
            dir_path = self.upload_dir / subfolder
        else:
            now = datetime.utcnow()
            dir_path = self.upload_dir / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"

        dir_path.mkdir(parents=True, exist_ok=True)

        # Unique filename: original-stem + uuid + extension
        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        unique_name = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
        full_path = dir_path / unique_name

        full_path.write_bytes(content)
        # Return path relative to upload_dir for portability
        return str(full_path.relative_to(self.upload_dir))

    async def save_stream(self, file_name: str, chunks, *, subfolder: str | None = None) -> str:
        """Save streaming file content and return the relative path string."""
        if subfolder:
            dir_path = self.upload_dir / subfolder
        else:
            now = datetime.utcnow()
            dir_path = self.upload_dir / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"

        dir_path.mkdir(parents=True, exist_ok=True)

        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        unique_name = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
        full_path = dir_path / unique_name

        total_bytes = 0
        with open(full_path, "wb") as f:
            async for chunk in chunks:
                total_bytes += len(chunk)
                if total_bytes > self.max_bytes:
                    full_path.unlink(missing_ok=True)
                    raise StorageError(f"File too large: exceeds {self.max_bytes} byte limit")
                f.write(chunk)

        return str(full_path.relative_to(self.upload_dir))

    async def read(self, relative_path: str) -> bytes:
        """Read file content by relative path."""
        full_path = self.upload_dir / relative_path
        if not full_path.exists():
            raise StorageError(f"File not found: {relative_path}")
        return full_path.read_bytes()

    async def delete(self, relative_path: str) -> None:
        """Delete a file by relative path."""
        full_path = self.upload_dir / relative_path
        if full_path.exists():
            full_path.unlink()

    def absolute_path(self, relative_path: str) -> Path:
        """Get the absolute filesystem path for a stored file."""
        return self.upload_dir / relative_path


# ── Singleton ──────────────────────────────────────────────────────

storage = LocalStorage()
