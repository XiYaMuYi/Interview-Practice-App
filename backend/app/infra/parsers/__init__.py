"""Parser factory — selects the right parser based on file extension."""

from pathlib import Path

from app.core.exceptions import ParseError


class ParserFactory:
    """Return the appropriate parser for a given file path."""

    _parsers: dict[str, type] = {}

    @classmethod
    def register(cls, extensions: set[str], parser_cls: type) -> None:
        for ext in extensions:
            cls._parsers[ext.lower()] = parser_cls

    @classmethod
    def get_parser(cls, file_path: str | Path):
        ext = Path(file_path).suffix.lower()
        parser_cls = cls._parsers.get(ext)
        if parser_cls is None:
            raise ParseError(f"Unsupported file type: '{ext}'. Supported: {sorted(cls._parsers.keys())}")
        return parser_cls()

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return sorted(cls._parsers.keys())


# ── Auto-register parsers on import ─────────────────────────────────

from app.infra.parsers.pdf_parser import PDFParser
from app.infra.parsers.text_parser import TextParser
from app.infra.parsers.word_parser import WordParser

ParserFactory.register(PDFParser.supported_extensions, PDFParser)
ParserFactory.register(WordParser.supported_extensions, WordParser)
ParserFactory.register(TextParser.supported_extensions, TextParser)
