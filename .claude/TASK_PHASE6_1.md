# Phase 6 Task 1: AuditLog Model + Alembic Migration

Project: `D:\AI_Project\Surprise\Interview-Practice-App`

## Context
Per architecture doc (readme/02_Implementation_Guides/19_Auth_and_MultiTenant_Architecture_Draft.md §11.3), these operations MUST be audited:
- user approve / reject
- user disable / enable
- admin role change
- private data export
- sensitive data deletion

We need a dedicated `AuditLog` table. `ReviewRecord` only tracks review actions. `EventAuditLog` tracks AI events.

## Tasks

### 1. Create `backend/app/domain/models/audit.py`

New SQLModel for audit logging:

```python
"""Security audit log model for Phase 6 auditing."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


# Valid action values:
#   user.register / user.login / user.login_failed
#   user.approve / user.reject
#   user.disable / user.enable
#   user.role_change
#   access.unauthorized
#   data.export / data.delete

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_id: uuid.UUID | None = Field(default=None, nullable=True)
    actor_username: str | None = Field(default=None, max_length=100, nullable=True)
    action: str = Field(max_length=50)
    target_type: str | None = Field(default=None, max_length=50, nullable=True)
    target_id: str | None = Field(default=None, max_length=100, nullable=True)
    detail: str | None = Field(default=None, max_length=1000, nullable=True)
    ip_address: str | None = Field(default=None, max_length=45, nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Register model in `backend/app/domain/models/__init__.py`

Add: `from app.domain.models.audit import AuditLog  # noqa: F401`

### 3. Create Alembic migration

File: `backend/alembic/versions/h2i3j4k5l6m7_add_audit_logs_table.py`

Follow the EXACT idempotent pattern from `f1a2b3c4d5e6_add_auth_review_system.py`:
- Check table existence via information_schema query
- CREATE TABLE IF NOT EXISTS
- CREATE INDEX IF NOT EXISTS for 4 indexes
- Revision chain: revision="h2i3j4k5l6m7", down_revision="g1h2i3j4k5l6"

Table: `audit_logs` with all columns from the model.
Indexes: `ix_audit_logs_action`, `ix_audit_logs_actor_id`, `ix_audit_logs_created_at`, `ix_audit_logs_target` (composite on target_type+target_id).

### 4. Commit

```
git add backend/app/domain/models/audit.py backend/app/domain/models/__init__.py backend/alembic/versions/h2i3j4k5l6m7_add_audit_logs_table.py
git commit -m "feat: add AuditLog model + migration for security auditing (Phase 6)"
```

## Rules
- ONLY modify the 3 files listed above
- Do NOT restart dev server
- Migration MUST be idempotent
- Follow existing code style (SQLModel patterns)