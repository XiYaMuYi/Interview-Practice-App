# Phase 6 Task 3: Audit Middleware for Unauthorized Access

Project: `D:\AI_Project\Surprise\Interview-Practice-App`

## Goal
Create a FastAPI middleware that automatically logs 401/403 responses as audit events.

## Context
Per architecture doc, unauthorized access attempts must be logged. We have:
- `AuditService` in `backend/app/services/audit_service.py`
- `get_client_ip` in `backend/app/utils/request.py`
- `AuditLog` model in `backend/app/domain/models/audit.py`

## Task

### 1. Create `backend/app/api/middleware.py`

Create a FastAPI middleware that:
- Intercepts all responses
- If status code is 401 or 403, writes an audit log entry
- Uses direct DB session (not through dependency injection, since middleware runs outside request context)

```python
"""Audit middleware — logs 401/403 responses as security events."""

import asyncio

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
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
```

### 2. Register middleware in `backend/app/api/v1/register_routes.py`

Find where the `app` FastAPI instance is created or where middleware is registered. Add the AuditMiddleware import and registration.

Look for patterns like `app.add_middleware(...)` or the FastAPI app creation. If using `register_routes.py`, add after app creation:

```python
from app.api.middleware import AuditMiddleware

app.add_middleware(AuditMiddleware)
```

If the middleware registration doesn't fit in register_routes.py, find the correct file where the FastAPI app is configured (likely `backend/main.py` or similar).

### 3. Commit

```
git add backend/app/api/middleware.py
git add <whatever file you added middleware registration to>
git commit -m "feat: add audit middleware for 401/403 logging (Phase 6)"
```

## Rules
- Do NOT restart dev server
- Follow existing middleware patterns if any exist
- The middleware must be non-blocking (fire-and-forget)
- Never let audit failures break the main request flow
