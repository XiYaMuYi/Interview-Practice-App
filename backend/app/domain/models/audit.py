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
