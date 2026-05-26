# Auth & Multi-Tenant Permission System - Phase 1

## Context
Project: `D:\AI_Project\Surprise\Interview-Practice-App`
Architecture doc: `readme/02_Implementation_Guides\19_Auth_and_MultiTenant_Architecture_Draft.md`

Current state:
- FastAPI + SQLModel + PostgreSQL backend
- User model exists (id, username, email, password_hash, is_active, created_at, updated_at)
- JWT auth via `backend/app/api/deps.py` (get_current_user)
- Auth service at `backend/app/services/auth_service.py`
- Auth routes at `backend/app/api/v1/routes/auth_routes.py`
- Register routes at `backend/app/api/v1/register_routes.py`
- Some tables already have user_id (questions, resumes), others don't (study_records, chat_histories, files)
- AUTH_ENABLED env var controls auth on/off (default off, anonymous user)

## Task: Phase 1 — Core Auth + Review Status + Data Ownership Foundation

Implement the following changes. Read existing code first, then modify.

### 1. User Model Enhancement
File: `backend/app/domain/models/user.py`
- Add `role` field: str, default "user", max_length=20 (values: "user", "admin")
- Add `review_status` field: str, default "pending", max_length=20 (values: "pending", "approved", "rejected", "disabled")
- Add `last_login_at` field: datetime, nullable

### 2. Alembic Migration
Create a new migration in `backend/alembic/versions/`
- Add the 3 new columns to users table
- Set ALL existing users to role='admin', review_status='approved' (they are the original user, should have full access)
- Add index on review_status for efficient pending-user queries

### 3. Auth Service — Registration Flow Change
File: `backend/app/services/auth_service.py`
- Modify `register()` method:
  - New users get role='user', review_status='pending', is_active=False by default
  - Do NOT issue access/refresh tokens for pending users (they can't login until approved)
  - Return a response indicating "pending review" status
- Modify `authenticate()` method (login):
  - After finding user by username, check review_status:
    - "pending" → raise HTTPException 403 with detail "Account pending review"
    - "rejected" → raise HTTPException 403 with detail "Account rejected"
    - "disabled" → raise HTTPException 403 with detail "Account disabled"
    - "approved" → proceed with login
  - On successful login, update last_login_at
- Add method `list_pending_users(db_session) -> list[User]`: returns all users with review_status='pending'
- Add method `review_user(db_session, user_id, reviewer_id, new_status, remark)`:
  - Update user's review_status
  - If approved, set is_active=True
  - If rejected, set is_active=False
  - Create a review record

### 4. Review Record Model
File: `backend/app/domain/models/user.py` (append to same file) or new file
- Create `ReviewRecord` SQLModel table:
  - id: UUID PK
  - user_id: UUID FK → users
  - reviewer_id: UUID FK → users
  - action: str (values: "approved", "rejected")
  - remark: str, nullable
  - reviewed_at: datetime
  - created_at: datetime

### 5. Admin Routes
File: `backend/app/api/v1/routes/admin_routes.py` (create new)
- `GET /api/v1/admin/users/pending` — List users awaiting review (requires admin role)
- `POST /api/v1/admin/users/{user_id}/review` — Review a user (approve/reject with remark, requires admin role)
- `GET /api/v1/admin/users` — List all users (requires admin role)
- Use FastAPI Depends for admin check

### 6. Auth Dependencies Enhancement
File: `backend/app/api/deps.py`
- Add `get_current_admin_user()` dependency:
  - Calls get_current_user() first
  - Then checks user.role == "admin"
  - Raises 403 if not admin
- Add `require_approved()` dependency:
  - Checks user.review_status == "approved"
  - Raises 403 if not approved
- Update `get_current_user()` to also check review_status:
  - When AUTH_ENABLED is true and user is from DB, reject if review_status != "approved"

### 7. Register admin_routes in register_routes.py
File: `backend/app/api/v1/register_routes.py`
- Import and register admin_routes router with prefix "/api/v1/admin"

### 8. Auth Routes — Add /me endpoint update
File: `backend/app/api/v1/routes/auth_routes.py`
- The `/me` endpoint should return role and review_status in response
- Add `/api/v1/auth/status` endpoint that returns current user's review_status (for checking if pending)

### 9. Register Response Adjustment
- When register is called, return a response that indicates review_status:
  - If pending: {"user_id": "...", "username": "...", "review_status": "pending", "message": "Account created, pending admin review"}
  - Do NOT return tokens for pending users

### 10. Schemas Update
File: `backend/app/domain/schemas/__init__.py`
- Update RegisterResponse to include review_status field
- Add AdminReviewRequest schema (action: str, remark: str)
- Add AdminUserListItem schema (id, username, email, role, review_status, created_at, last_login_at)
- Add ReviewStatusResponse schema

## Constraints
- Keep AUTH_ENABLED=false anonymous mode working (anonymous user bypasses review checks)
- Follow the project's architecture constraints in `readme/01_Core_Constraints\00_Architecture_Constraints_For_Agent.md`
- API layer only does protocol conversion, business logic in service layer
- Use FastAPI Depends pattern consistently
- All new endpoints should follow existing patterns in auth_routes.py
- DO NOT change any existing non-auth API contracts
- DO NOT modify exam_routes, question_routes, or other business routes in this phase
- After completing, run: docker-compose down && docker-compose up -d --build

## Files to modify
1. backend/app/domain/models/user.py
2. backend/app/services/auth_service.py
3. backend/app/api/deps.py
4. backend/app/api/v1/routes/auth_routes.py
5. backend/app/api/v1/routes/admin_routes.py (new)
6. backend/app/api/v1/register_routes.py
7. backend/app/domain/schemas/__init__.py
8. New alembic migration

## After completion
1. Rebuild Docker: cd D:\AI_Project\Surprise\Interview-Practice-App && docker-compose down && docker-compose up -d --build
2. Verify /health endpoint works
3. Run alembic upgrade head inside the container
4. Test that register creates pending user
5. Test that pending user cannot login
6. Test that admin can review users
