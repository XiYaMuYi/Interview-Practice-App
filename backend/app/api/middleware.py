"""Audit middleware — logs 401/403 responses as security events."""

import asyncio

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.domain.models.audit import AuditLog
from app.infra.db.session import async_session
from app.utils.request import get_client_ip


class AuditMiddleware(BaseHTTPMiddleware):
    """Automatically log unauthorized access attempts."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Only log 401/403 responses
        if response.status_code not in (401, 403):
            return response

        # Skip logging for auth endpoints (login failures are handled separately)
        path = request.url.path
        if path.startswith("/api/v1/auth/"):
            return response

        # Fire-and-forget audit log (non-blocking)
        ip_address = get_client_ip(request)
        action = "access.unauthorized"
        detail = f"{response.status_code} on {request.method} {path}"

        asyncio.create_task(
            self._log_audit_event(
                action=action,
                detail=detail,
                ip_address=ip_address,
            )
        )

        return response

    @staticmethod
    async def _log_audit_event(action: str, detail: str, ip_address: str | None) -> None:
        """Write audit log entry using a dedicated DB session."""
        try:
            async with async_session() as session:
                entry = AuditLog(
                    action=action,
                    detail=detail,
                    ip_address=ip_address,
                )
                session.add(entry)
                await session.commit()
        except Exception:
            # Never let audit logging failures break the request
            pass
