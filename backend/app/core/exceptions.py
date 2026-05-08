from fastapi import HTTPException


class AppException(HTTPException):
    """Base application exception with standardized HTTP response."""

    def __init__(self, status_code: int, detail: str, code: str | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(status_code=404, detail=f"{resource} '{identifier}' not found", code="NOT_FOUND")


class ConflictError(AppException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail, code="CONFLICT")


class ParseError(AppException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=detail, code="PARSE_ERROR")


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(status_code=401, detail=detail, code="UNAUTHORIZED")
