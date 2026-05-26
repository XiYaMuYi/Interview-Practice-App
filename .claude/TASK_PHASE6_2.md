# Phase 6 Task 2: AuditService Layer

Project: `D:\AI_Project\Surprise\Interview-Practice-App`

## Goal
Create an `AuditService` class for writing audit logs, plus a helper function `get_client_ip` to extract IP from FastAPI requests.

## Context
We just created the `AuditLog` model (Task 1). Now we need a service layer to write audit entries.

Existing services pattern: see `backend/app/services/auth_service.py` — services take `AsyncSession` in constructor and use async methods.

## Tasks

### 1. Create `backend/app/services/audit_service.py`

```python
"""Audit service — writes security audit log entries."""

import uuid
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.models.audit import AuditLog


class AuditService:
    """Service for writing and querying audit logs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        action: str,
        actor_id: uuid.UUID | None = None,
        actor_username: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Write a single audit log entry."""
        entry = AuditLog(
            actor_id=actor_id,
            actor_username=actor_username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_logs(
        self,
        action: str | None = None,
        actor_id: uuid.UUID | None = None,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs with optional filters. Returns (items, total)."""
        query = select(AuditLog)
        count_query = select(AuditLog)

        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if actor_id:
            query = query.where(AuditLog.actor_id == actor_id)
            count_query = count_query.where(AuditLog.actor_id == actor_id)
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
            count_query = count_query.where(AuditLog.target_type == target_type)

        # Get total count
        count_result = await self.session.exec(count_query)
        total = len(count_result.all())

        # Get paginated results (newest first)
        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.exec(query)
        return list(result.all()), total
```

### 2. Create `backend/app/utils/request.py`

Create a utility module for extracting client IP from FastAPI requests:

```python
"""Request utilities — extract client IP, etc."""

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Extract client IP address from request, checking forwarded headers."""
    # Check X-Forwarded-For first (proxy/load balancer)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Check X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    # Fallback to direct client
    if request.client:
        return request.client.host
    return None
```

### 3. Commit

```
git add backend/app/services/audit_service.py backend/app/utils/request.py
git commit -m "feat: add AuditService and request utilities (Phase 6)"
```

## Rules
- Only create the 2 files listed above
- Do NOT modify any other files yet
- Do NOT restart dev server
- Follow existing service patterns from auth_service.py
