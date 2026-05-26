# Auth & Multi-Tenant Permission System - Development Task

## Architecture Doc
Read this FIRST: `readme/02_Implementation_Guides/19_Auth_and_MultiTenant_Architecture_Draft.md`
Also read: `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
Also read: `readme/01_Core_Constraints/03_Database_Schema.md`

## Goal
Transform the project from a single-user tool into a SaaS-style platform with:
1. Public question bank shared by all users
2. Private data isolated per logged-in user
3. Registration with admin review (pending → approved)
4. Admin review dashboard
5. Four-layer auth structure: Authentication → Authorization → Data Ownership → Access Control

## Phase 1: User Model + Review Status (MUST be done first)

### 1.1 User Model Changes
File: `backend/app/domain/models/user.py`

Add 3 new columns to the `User` SQLModel:
```python
role: str = Field(default="user", max_length=20)       # "user" | "admin"
review_status: str = Field(default="pending", max_length=20)  # "pending" | "approved" | "rejected" | "disabled"
last_login_at: datetime | None = Field(default=None, nullable=True)
```

### 1.2 ReviewRecord Model (new table)
Add a new SQLModel to `backend/app/domain/models/user.py` (same file):
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

### 1.3 Alembic Migration
Create migration: `backend/alembic/versions/<ts>_add_auth_review_system.py`

The migration must:
1. Add `role`, `review_status`, `last_login_at` columns to `users` table
2. Create `review_records` table
3. **CRITICAL**: Backfill ALL existing users: `role='admin'`, `review_status='approved'` (they are the original owner)
4. Add index on `users.review_status`
5. Add index on `review_records.user_id`

### 1.4 Auth Service Changes
File: `backend/app/services/auth_service.py`

Modify `register()` method:
- New users get `role="user"`, `review_status="pending"`, `is_active=False`
- Do NOT return tokens from this method — let the route layer decide
- Return the created User object

Modify `authenticate()` method:
- After verifying password AND is_active, add review_status check:
  - `pending` → raise `HTTPException(status_code=403, detail="账号审核中，请等待管理员审核")`
  - `rejected` → raise `HTTPException(status_code=403, detail="账号审核未通过")`
  - `disabled` → raise `HTTPException(status_code=403, detail="账号已被禁用")`
  - `approved` → proceed
- On success, update `user.last_login_at = datetime.utcnow()`

Add new methods:
```python
async def list_pending_users(self) -> list[User]:
    """Return all users with review_status='pending'."""

async def list_all_users(self) -> list[User]:
    """Return all users (compact)."""

async def review_user(self, user_id: uuid.UUID, reviewer_id: uuid.UUID, action: str, remark: str | None) -> User:
    """Approve or reject a user. Creates a ReviewRecord."""
    # action: "approved" → set review_status="approved", is_active=True
    # action: "rejected" → set review_status="rejected", is_active=False
    # Create ReviewRecord entry
    # Update user.updated_at
    # Return updated user
```

### 1.5 Admin Routes (NEW FILE)
Create: `backend/app/api/v1/routes/admin_routes.py`

```python
router = APIRouter()

@router.get("/users/pending")
async def list_pending_users(current_user: User = Depends(get_current_admin_user)):
    """List users awaiting review. Requires admin role."""

@router.post("/users/{user_id}/review")
async def review_user(user_id: UUID, body: AdminReviewRequest, current_user: User = Depends(get_current_admin_user)):
    """Approve or reject a user. Requires admin role."""

@router.get("/users")
async def list_all_users(current_user: User = Depends(get_current_admin_user)):
    """List all users. Requires admin role."""
```

### 1.6 Auth Dependencies
File: `backend/app/api/deps.py`

Add new dependency:
```python
async def get_current_admin_user(session: DbSession, authorization: str | None = Header(None)) -> User:
    """Requires auth + admin role. Raises 403 if not admin."""
    user = await get_current_user(session, authorization)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
```

Update `get_current_user()`:
- When `AUTH_ENABLED=true`, after loading user from DB, check:
  - `user.review_status != "approved"` → raise 403 with appropriate message
- When `AUTH_ENABLED=false` (anonymous mode), skip review checks (anonymous bypass)

### 1.7 Auth Route Updates
File: `backend/app/api/v1/routes/auth_routes.py`

**register endpoint:**
- After `service.register()`, check `user.review_status`:
  - If "pending" → DO NOT create tokens. Return: `{"user_id": str, "username": str, "review_status": "pending", "message": "账号已创建，等待管理员审核"}`
  - If somehow "approved" (AUTH_ENABLED=false path) → return tokens as before

**/me endpoint:**
- Add `"role"`, `"review_status"`, `"last_login_at"` to response

### 1.8 Register Admin Routes
File: `backend/app/api/v1/register_routes.py`

Add:
```python
from app.api.v1.routes import admin_routes
# ...
app.include_router(admin_routes.router, prefix="/api/v1/admin", tags=["admin"])
```

### 1.9 Schema Updates
File: `backend/app/domain/schemas/__init__.py`

Add new schemas:
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

Update `RegisterResponse`: make `access_token` and `refresh_token` optional (since pending users don't get tokens)

## Phase 2: Data Ownership - user_id on Private Tables

### 2.1 Alembic Migration (can combine with Phase 1 migration)
Add `user_id` column (UUID, nullable=True, FK to users.id) to:
- `study_records`
- `chat_histories`
- `files`

Add indexes on each `user_id` column.

For existing rows without user_id, set them to the first admin user's ID (or anonymous UUID).

### 2.2 Service Layer Changes

**study_service.py:**
- `create_study_record()`: accept optional `user_id` parameter, store it
- `get_study_records_with_count()`: filter by `user_id` when provided
- `record_review()`: accept optional `user_id` parameter
- `get_review_list()`: filter by `user_id` when provided
- `get_stats()`: filter by `user_id` when provided

**chat_service.py:**
- `create_session()`: accept optional `user_id` parameter, store it
- `get_sessions_with_count()`: filter by `user_id` when provided
- `get_history()`: filter by `user_id` + session_id
- `chat()` / `stream_chat()`: save messages with `user_id`

**import_service.py:**
- `import_text()`, `import_file()`: accept optional `user_id`, pass to question creation
- `import_text_stream()`: accept optional `user_id`

**question_service.py:**
- `create_question()`: accept optional `user_id` parameter (already exists!)
- `list_questions_with_count()`: keep existing behavior — public questions (no user_id) visible to all
  - If `user_id` filter is passed, ONLY filter questions where `user_id` matches (for "my questions" views)
  - Public questions should ALWAYS be visible regardless of user_id filter

**resume_service.py:**
- Already has `user_id` support. Verify it works correctly.

### 2.3 Route Layer - Pass current_user.id

Update route handlers to pass `current_user.id` to service methods:

**study_routes.py:**
- Import `get_current_user` from `app.api.deps`
- `create_study_record`: `current_user: User = Depends(get_current_user)` → pass `current_user.id`
- `list_study_records`: pass `current_user.id` for filtering
- `record_review`: pass `current_user.id`
- `get_review_list`: pass `current_user.id`
- `get_study_stats`: pass `current_user.id`

**chat_routes.py:**
- `create_chat_session`: pass `current_user.id`
- `list_sessions`: pass `current_user.id`
- `get_chat_history`: pass `current_user.id` (also check ownership)
- `send_message`: pass `current_user.id`
- `send_message_stream`: pass `current_user.id`

**import_routes.py:**
- `import_text`: pass `current_user.id`
- `import_file`: pass `current_user.id`
- `upload_file`: pass `current_user.id`
- `import_text_stream`: pass `current_user.id`
- `import_text_stream_async`: pass `current_user.id`

**resume_routes.py:**
- Already has `user_id` query param — replace with `current_user: User = Depends(get_current_user)`
- Use `current_user.id` instead of query param

**question_routes.py:**
- `create_question`: pass `current_user.id`
- `import_questions`: pass `current_user.id` to each question
- `list_questions`: pass `current_user.id` (as optional filter — public questions still visible)

## Phase 3: Frontend Support

### 3.1 Auth Store Updates
File: `web/src/lib/auth-context.tsx` or equivalent
- Store `role` and `review_status` from `/me` endpoint
- On login/register, handle `review_status` responses

### 3.2 Registration Flow
- After register, if `review_status === "pending"` → show "账号审核中" page instead of redirecting to main app
- If `review_status === "approved"` → proceed to main app

### 3.3 Pending Review Page
Create: `web/src/app/auth/pending/page.tsx`
- Display: "您的账号正在审核中，请等待管理员审核通过"
- Show poll/retry button to check status periodically

### 3.4 Admin Review Page
Create: `web/src/app/admin/review/page.tsx`
- Fetch `GET /api/v1/admin/users/pending`
- Display table of pending users (username, email, registered_at)
- Approve/Reject buttons for each user
- Remark text input for rejection reason
- Guard: only accessible if `role === "admin"`

### 3.5 Login Error Handling
- Distinguish between:
  - "Invalid username or password" (401)
  - "账号审核中" (403)
  - "账号审核未通过" (403)
  - "账号已被禁用" (403)

### 3.6 Route Protection
- Unauthenticated → redirect to /auth/login
- `review_status !== "approved"` → redirect to /auth/pending (except /auth/* and /admin/*)
- `role !== "admin"` → block access to /admin/* routes

## CRITICAL RULES

1. **Public question bank must remain accessible to ALL authenticated users** — do NOT filter questions by user_id by default. Questions without a user_id are PUBLIC.
2. **Anonymous mode (AUTH_ENABLED=false) must continue working** — anonymous user bypasses all review checks
3. **API layer = protocol only** — business logic in service layer
4. **Use FastAPI Depends pattern** for all auth
5. **DO NOT break existing API contracts** — existing endpoints must still work
6. **Migration must handle existing data** — existing users become admin+approved
7. **First registered user should automatically be admin+approved** (bootstrap case)

## Execution Order
1. Phase 1 first — complete and test
2. Phase 2 second — complete and test
3. Phase 3 last — frontend

After Phase 1+2:
- `cd D:\AI_Project\Surprise\Interview-Practice-App && docker-compose down && docker-compose up -d --build`
- Verify `GET /health` returns 200
- Verify `GET /api/v1/auth/config` works
- Test register creates pending user
- Test pending user cannot login
- Test admin can review users

After Phase 3:
- `cd D:\AI_Project\Surprise\Interview-Practice-App\web && npm run dev`
- Verify registration flow with pending state
- Verify admin review page works
- Verify route protection

## Files to Modify
- `backend/app/domain/models/user.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/v1/routes/auth_routes.py`
- `backend/app/api/v1/routes/admin_routes.py` (CREATE)
- `backend/app/api/deps.py`
- `backend/app/api/v1/register_routes.py`
- `backend/app/domain/schemas/__init__.py`
- `backend/app/services/study_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/import_service.py`
- `backend/app/services/question_service.py`
- `backend/app/api/v1/routes/study_routes.py`
- `backend/app/api/v1/routes/chat_routes.py`
- `backend/app/api/v1/routes/import_routes.py`
- `backend/app/api/v1/routes/resume_routes.py`
- `backend/app/api/v1/routes/question_routes.py`
- `backend/alembic/versions/` (CREATE migration)
- `web/src/lib/auth-context.tsx` or equivalent auth store
- `web/src/app/auth/pending/page.tsx` (CREATE)
- `web/src/app/admin/review/page.tsx` (CREATE)
- Web routing protection middleware
