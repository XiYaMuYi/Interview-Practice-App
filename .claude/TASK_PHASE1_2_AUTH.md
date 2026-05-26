# Phase 1+2: Auth Review System + Data Ownership Foundation

## Context
Read these files FIRST before writing any code:
- `readme/02_Implementation_Guides/19_Auth_and_MultiTenant_Architecture_Draft.md` (architecture spec)
- `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md` (architecture constraints)
- `readme/01_Core_Constraints/03_Database_Schema.md` (database schema)

Then read existing code:
- `backend/app/domain/models/user.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/v1/routes/auth_routes.py`
- `backend/app/api/deps.py`
- `backend/app/domain/schemas/__init__.py` (Auth DTOs section)
- `backend/app/api/v1/register_routes.py`

## Current State
- User model: id, username, email, password_hash, is_active, created_at, updated_at
- No `role` or `review_status` fields on User
- Registration creates user with is_active=True and immediately returns tokens
- Login only checks is_active, no review_status check
- No admin routes for user review
- Some tables already have user_id (questions, resumes), others don't (study_records, chat_histories, files)
- `AUTH_ENABLED=false` uses synthetic anonymous user

## Goal
Phase 1+2 combined: Implement user review status + role system, AND add user_id data ownership to all private tables.

## Task Details

### 1. User Model - Add Fields
File: `backend/app/domain/models/user.py`
- Add `role: str = Field(default="user", max_length=20)` — values: "user", "admin"
- Add `review_status: str = Field(default="pending", max_length=20)` — values: "pending", "approved", "rejected", "disabled"
- Add `last_login_at: datetime | None = Field(default=None, nullable=True)`

### 2. ReviewRecord Model - New Table
File: `backend/app/domain/models/user.py` (same file, after User class)
Create SQLModel `ReviewRecord`:
- `id: uuid.UUID` (PK, default_factory=uuid4)
- `user_id: uuid.UUID` (FK to users.id)
- `reviewer_id: uuid.UUID` (FK to users.id)
- `action: str` (max_length=20, values: "approved", "rejected")
- `remark: str | None` (nullable, max_length=500)
- `reviewed_at: datetime` (default_factory=datetime.utcnow)
- `created_at: datetime` (default_factory=datetime.utcnow)

### 3. Alembic Migration
Create new migration in `backend/alembic/versions/`:
- Add columns `role`, `review_status`, `last_login_at` to `users` table
- Create `review_records` table with all columns
- **CRITICAL**: Update ALL existing users to `role='admin'` and `review_status='approved'` (the original user should have full access immediately)
- Add index on `users.review_status`
- Add index on `review_records.user_id`

### 4. Auth Service - Registration Review Flow
File: `backend/app/services/auth_service.py`

**register() changes:**
- New users default to `role="user"`, `review_status="pending"`, `is_active=False`
- Do NOT return tokens for pending users (they must wait for approval)
- Return the user object (routes layer decides response)

**authenticate() changes:**
- After finding user and verifying password, check review_status:
  - "pending" → raise HTTPException(status_code=403, detail="账号审核中，请等待管理员审核")
  - "rejected" → raise HTTPException(status_code=403, detail="账号审核未通过")
  - "disabled" → raise HTTPException(status_code=403, detail="账号已被禁用")
  - "approved" → proceed normally
- On successful login, update `last_login_at` to datetime.utcnow()

**New methods:**
- `async def list_pending_users() -> list[User]`: select all users where review_status='pending'
- `async def list_all_users() -> list[User]`: select all users
- `async def review_user(user_id: uuid.UUID, reviewer_id: uuid.UUID, action: str, remark: str | None) -> User`:
  - Find user by user_id, raise 404 if not found
  - If action == "approved": set review_status="approved", is_active=True
  - If action == "rejected": set review_status="rejected", is_active=False
  - Create ReviewRecord entry
  - Update user.updated_at
  - Return updated user

### 5. Admin Routes - New File
File: `backend/app/api/v1/routes/admin_routes.py` (CREATE NEW)

```
GET /api/v1/admin/users/pending
→ Returns list of pending users
→ Requires admin role (use get_current_admin_user dependency)

POST /api/v1/admin/users/{user_id}/review
→ Body: {"action": "approved"|"rejected", "remark": "..."}
→ Requires admin role
→ Calls auth_service.review_user()

GET /api/v1/admin/users
→ Returns list of all users (compact format)
→ Requires admin role
```

All routes must use `current_user: User = Depends(get_current_admin_user)` for auth.

### 6. Auth Dependencies - Enhance
File: `backend/app/api/deps.py`

Add new dependency `get_current_admin_user`:
- First call get_current_user() to get the authenticated user
- Check `user.role == "admin"`
- If not admin, raise HTTPException(status_code=403, detail="需要管理员权限")
- Return the user

Update `get_current_user()`:
- When AUTH_ENABLED=true, after loading user from DB, also check:
  - If user.review_status != "approved" AND user.review_status != None, raise HTTPException 403 with appropriate message
- When AUTH_ENABLED=false (anonymous mode), skip review_status check (anonymous bypass)

### 7. Auth Routes - Update Responses
File: `backend/app/api/v1/routes/auth_routes.py`

**register endpoint changes:**
- After calling service.register(), DO NOT create tokens if user.review_status == "pending"
- Return modified response: {"user_id": str, "username": str, "review_status": "pending", "message": "账号已创建，等待管理员审核"}
- For backward compat when AUTH_ENABLED=false or if review_status is already "approved", still return tokens

**login endpoint:**
- The review_status check is now in auth_service.authenticate(), so no route-level change needed
- On successful login, update last_login_at (done in service layer)

**/me endpoint changes:**
- Add "role" and "review_status" to response dict
- Add "last_login_at" to response dict

### 8. Register Admin Routes
File: `backend/app/api/v1/register_routes.py`
- Import admin_routes module
- Add: `app.include_router(admin_routes.router, prefix="/api/v1/admin", tags=["admin"])`

### 9. Schemas Update
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

class ReviewStatusResponse(BaseModel):
    review_status: str
    message: str | None
```

Update RegisterResponse to include review_status field (make access_token and refresh_token optional since pending users don't get tokens).

### 10. Data Ownership - Add user_id to remaining tables
This is Phase 2 of the architecture doc.

Create a SECOND alembic migration (or combine into the first if you prefer):
- Add `user_id` column (UUID, nullable=True) to:
  - `study_records`
  - `chat_histories`
  - `files`
- Add indexes on user_id for each table
- Set existing rows' user_id to the anonymous UUID or first admin user's ID

### 11. Service Layer - Add user_id to Create Operations
For each service that creates private data, the route handler should pass `current_user.id` as user_id:

- **study_service.py**: `create_study_record()` should accept and store user_id
- **chat_service.py**: saving chat messages should store user_id  
- **import_service.py**: file imports should store user_id
- **resume_service.py**: resume uploads already have user_id, verify it's being set

**IMPORTANT for question_service.py:**
- Questions have BOTH public (user_id=NULL) and private (user_id set) modes
- `create_question()` should accept optional user_id
- `list_questions()` should NOT filter by user_id (public question bank is shared)
- But the route layer can optionally pass user_id for "my questions" views

### 12. Route Layer - Pass user_id to services
Update route handlers that create private data to pass `current_user.id`:
- study routes: pass user_id when creating study records
- chat routes: pass user_id when saving messages
- import routes: pass user_id when importing
- resume routes: pass user_id when uploading

## CRITICAL RULES

1. **DO NOT break existing functionality**: The public question bank must remain accessible to all authenticated users
2. **Anonymous mode (AUTH_ENABLED=false) must still work**: Skip all review checks for anonymous user
3. **Follow architecture constraints**: API layer = protocol only, business logic in service layer
4. **Use FastAPI Depends pattern consistently** for auth
5. **DO NOT modify exam_routes.py** or other routes not mentioned above
6. **Migration must handle existing data**: existing users become admin+approved, existing private data gets assigned to the first admin user
7. **After all changes, rebuild Docker**: `docker-compose down && docker-compose up -d --build`
8. **Run alembic upgrade** after migration is created

## Files to Create/Modify
- CREATE: `backend/app/api/v1/routes/admin_routes.py`
- CREATE: `backend/alembic/versions/<revision>_add_auth_review_and_data_ownership.py`
- MODIFY: `backend/app/domain/models/user.py`
- MODIFY: `backend/app/services/auth_service.py`
- MODIFY: `backend/app/api/v1/routes/auth_routes.py`
- MODIFY: `backend/app/api/deps.py`
- MODIFY: `backend/app/api/v1/register_routes.py`
- MODIFY: `backend/app/domain/schemas/__init__.py`
- MODIFY: `backend/app/services/study_service.py` (add user_id param)
- MODIFY: `backend/app/services/chat_service.py` (add user_id param)
- MODIFY: `backend/app/services/import_service.py` (add user_id param)
- MODIFY: corresponding route files to pass user_id

## Verification Steps
After completing:
1. Rebuild and restart Docker containers
2. Test: GET /health returns 200
3. Test: GET /api/v1/auth/config returns auth settings
4. Test: POST /api/v1/auth/register creates user with review_status="pending"
5. Test: POST /api/v1/auth/login with pending user returns 403
6. Test: Admin can GET /api/v1/admin/users/pending
7. Test: Admin can POST /api/v1/admin/users/{id}/review with action="approved"
8. Test: Approved user can login and get tokens
