# Phase 6 Task 5: Audit Log Query API Endpoint

Project: `D:\AI_Project\Surprise\Interview-Practice-App`

## Goal
Create a paginated GET endpoint for querying audit logs (admin only).

## Context
We have the AuditService with list_logs() method. Now we need an API endpoint.

Existing patterns:
- Admin routes in `backend/app/api/v1/routes/admin_routes.py` use `get_current_admin_user` for auth
- Pagination follows the protocol from `03_Database_Schema.md`: `page` + `page_size` params, returns `total` + `items`
- Schemas in `backend/app/domain/schemas/__init__.py`

## Task

### 1. Add schema in `backend/app/domain/schemas/__init__.py`

Add these schemas at the end of the Auth DTOs section or in a new Audit DTOs section:

```python
# ─────────────────────────────────────────────────────────────────────
# Audit DTOs
# ─────────────────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    """Single audit log entry."""

    id: UUID
    actor_id: UUID | None
    actor_username: str | None
    action: str
    target_type: str | None
    target_id: str | None
    detail: str | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""

    total: int
    page: int
    page_size: int
    items: list[AuditLogResponse]
```

### 2. Add endpoint in `backend/app/api/v1/routes/admin_routes.py`

Add a new endpoint:

```python
@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    target_type: str | None = None,
    session: DbSession = Depends(get_db_session),  # use the existing session dependency
    _admin: User = Depends(get_current_admin_user),
):
    """List audit logs with pagination and filters (admin only)."""
    from app.services.audit_service import AuditService

    offset = (page - 1) * page_size
    service = AuditService(session)
    items, total = await service.list_logs(
        action=action,
        target_type=target_type,
        limit=page_size,
        offset=offset,
    )
    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            AuditLogResponse(
                id=item.id,
                actor_id=item.actor_id,
                actor_username=item.actor_username,
                action=item.action,
                target_type=item.target_type,
                target_id=item.target_id,
                detail=item.detail,
                ip_address=item.ip_address,
                created_at=item.created_at,
            )
            for item in items
        ],
    )
```

Check how the existing endpoints get the session — use the same pattern (DbSession from deps.py).

### 3. Commit

```
git add backend/app/domain/schemas/__init__.py backend/app/api/v1/routes/admin_routes.py
git commit -m "feat: add paginated audit log query API endpoint (Phase 6)"
```

## Rules
- Only modify the 2 files listed
- Do NOT restart dev server
- Follow existing pagination patterns from the project
- Endpoint is admin-only (use get_current_admin_user dependency)
