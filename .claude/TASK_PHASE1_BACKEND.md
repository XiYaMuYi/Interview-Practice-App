# Phase 1: Backend Auth & Review System

You are working in: D:\AI_Project\Surprise\Interview-Practice-App

## Documents to Read FIRST (in this order)
1. `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
2. `readme/01_Core_Constraints/03_Database_Schema.md`
3. `readme/02_Implementation_Guides/19_Auth_and_MultiTenant_Architecture_Draft.md`

Then read existing code:
4. `backend/app/domain/models/user.py`
5. `backend/app/services/auth_service.py`
6. `backend/app/api/deps.py`
7. `backend/app/api/v1/routes/auth_routes.py`
8. `backend/app/api/v1/register_routes.py`
9. `backend/app/domain/schemas/__init__.py`
10. `backend/app/core/config.py`
11. `backend/app/api/v1/routes/exam_routes.py` (for reference on how routes are structured)

## Goal
Transform auth from "login works but no review/roles" to a full review-based registration system with admin approval flow.

## Changes Required

### 1. User Model (`backend/app/domain/models/user.py`)
Add 3 fields to existing `User` SQLModel:
```python
role: str = Field(default="user", max_length=20)       # "user" | "admin"
review_status: str = Field(default="pending", max_length=20)  # "pending" | "approved" | "rejected" | "disabled"
last_login_at: datetime | None = Field(default=None, nullable=True)
```

Add new `ReviewRecord` SQLModel in the SAME file:
```python
class ReviewRecord(SQLModel, table=True):
    __tablename__ = "review_records"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    reviewer_id: uuid.UUID = Field(foreign_key="users.id")
    action: str = Field(max_length=20)  # "approved" | "rejected"
    remark: str | None = Field(default=None, max_length=500)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Alembic Migration
Create new migration in `backend/alembic/versions/`:
- Add `role`, `review_status`, `last_login_at` columns to `users` table
- Create `review_records` table
- **CRITICAL**: Backfill ALL existing users: `role='admin'`, `review_status='approved'` (they are the original owner)
- Add index on `users.review_status`
- Add index on `review_records.user_id`

IMPORTANT: Make the migration idempotent. Check if columns/indexes/tables already exist before creating them. Previous migrations crashed on rebuild due to duplicate objects.

### 3. Auth Service (`backend/app/services/auth_service.py`)

**Modify `register()` method:**
- New users get `role="user"`, `review_status="pending"`, `is_active=False`
- Return the created User object (do NOT create tokens here)

**Modify `authenticate()` method:**
- After verifying password AND is_active, check review_status:
  - "pending" → raise HTTPException(status_code=403, detail="账号审核中，请等待管理员审核")
  - "rejected" → raise HTTPException(status_code=403, detail="账号审核未通过")
  - "disabled" → raise HTTPException(status_code=403, detail="账号已被禁用")
  - "approved" → proceed
- On success, update `user.last_login_at = datetime.utcnow()`

**Add new methods:**
```python
async def list_pending_users(self) -> list[User]
async def list_all_users(self) -> list[User]
async def review_user(self, user_id: uuid.UUID, reviewer_id: uuid.UUID, action: str, remark: str | None) -> User
```

### 4. Admin Routes (CREATE `backend/app/api/v1/routes/admin_routes.py`)
```python
GET  /users/pending          → List pending users (requires admin)
POST /users/{user_id}/review → Approve/reject a user (requires admin)
GET  /users                  → List all users (requires admin)
```

### 5. Auth Dependencies (`backend/app/api/deps.py`)
- Add `get_current_admin_user()` dependency
- Update `get_current_user()`: when AUTH_ENABLED=true, check review_status != "approved" → raise 403
- When AUTH_ENABLED=false (anonymous mode), skip review checks

### 6. Auth Routes (`backend/app/api/v1/routes/auth_routes.py`)

**register endpoint:**
- After service.register(), check review_status:
  - If "pending" → return `{"user_id", "username", "review_status": "pending", "message": "账号已创建，等待管理员审核"}` (NO tokens)
  - If "approved" (AUTH_ENABLED=false path) → return tokens as before

**/me endpoint:**
- Add `"role"`, `"review_status"`, `"last_login_at"` to response

### 7. Schemas (`backend/app/domain/schemas/__init__.py`)

Add:
```python
class AdminReviewRequest(BaseModel):
    action: str = Field(pattern="^(approved|rejected)$")
    remark: str | None = Field(default=None, max_length=500)

class AdminUserListItem(BaseModel):
    user_id: str
    username: str
    email: str | None
    role: str
    review_status: str
    is_active: bool
    created_at: str
    last_login_at: str | None

class RegisterPendingResponse(BaseModel):
    user_id: str
    username: str
    review_status: str
    message: str
```

Make `access_token` and `refresh_token` optional in `RegisterResponse` (since pending users don't get tokens).

### 8. Register Routes (`backend/app/api/v1/register_routes.py`)

**BUG FIX**: This file currently does NOT import or register `auth_routes`. Add:
```python
from app.api.v1.routes import auth_routes
app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["auth"])
```

Also add admin routes registration:
```python
from app.api.v1.routes import admin_routes
app.include_router(admin_routes.router, prefix="/api/v1/admin", tags=["admin"])
```

## Critical Rules
1. **Keep AUTH_ENABLED=false anonymous mode working** — anonymous user bypasses all review checks
2. **Follow architecture constraints** — API layer only does protocol, business logic in service layer
3. **Use FastAPI Depends pattern** for all auth
4. **DO NOT break existing API contracts** — existing endpoints must still work
5. **Migration MUST handle existing data** — existing users become admin+approved
6. **Make migration idempotent** — wrap in try/except for duplicate column/index/table errors

## After Completion
1. Run: `cd D:\AI_Project\Surprise\Interview-Practice-App && docker-compose down && docker-compose up -d --build`
2. Verify: `curl localhost:8000/health` returns 200
3. Verify: `curl localhost:8000/api/v1/auth/config` works

When completely finished, run this command to notify me:
openclaw system event --text "Done: Phase 1 backend auth complete. Models, migration, services, routes, schemas all updated. Docker rebuilt." --mode now
