# Phase 6 Task 4: Inject Audit Calls into Business Logic

Project: `D:\AI_Project\Surprise\Interview-Practice-App`

## Goal
Add audit logging calls to admin routes and auth service for sensitive operations.

## Context
Per architecture doc §11.3, these operations MUST be audited:
- user approve / reject → already in `admin_routes.py` review_user endpoint
- user disable / enable → need to add if endpoints exist
- admin role change → need to add if endpoints exist

We have:
- `AuditService` in `backend/app/services/audit_service.py`
- `get_client_ip` in `backend/app/utils/request.py`
- `AuditMiddleware` already handles 401/403 auto-logging

## Task

### 1. Modify `backend/app/api/v1/routes/admin_routes.py`

Add audit logging to the `review_user` endpoint (POST /users/{user_id}/review):

- Import `Request` from fastapi, `AuditService` from services, `get_client_ip` from utils
- Add `request: Request` parameter to the review_user endpoint
- After successful review, call `audit_service.log()` to record the action

The action value should be:
- "user.approve" when action is "approved"
- "user.reject" when action is "rejected"

target_type should be "user", target_id should be the user_id string.
detail should include the username and reviewer info.

Code to add (inject into review_user endpoint, after `await session.commit()`):

```python
# Audit log
audit_service = AuditService(session)
await audit_service.log(
    action=f"user.{data.action}",  # "user.approve" or "user.reject"
    actor_id=admin.id,
    actor_username=admin.username,
    target_type="user",
    target_id=user_id,
    detail=f"Admin {admin.username} {data.action} user {user.username}" + (f" (remark: {data.remark})" if data.remark else ""),
    ip_address=get_client_ip(request),
)
```

Note: Since the session is already committed, you need to use a separate session or flush the audit log. Use the pattern from the middleware: create the AuditLog directly with `session.add()` and `await session.commit()` in a try/except.

Actually, better approach: do the audit log BEFORE `await session.commit()` — so it commits in the same transaction. Move the audit log call to just before the commit line.

### 2. Commit

```
git add backend/app/api/v1/routes/admin_routes.py
git commit -m "feat: add audit logging to user review endpoint (Phase 6)"
```

## Rules
- Only modify admin_routes.py
- Do NOT restart dev server
- Audit log should be part of the same transaction as the review action
- If audit logging fails, it should not break the review operation
