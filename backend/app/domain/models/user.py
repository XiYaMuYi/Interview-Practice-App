"""User model for authentication and review records."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, ForeignKey


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(max_length=100, unique=True, index=True)
    email: str | None = Field(default=None, max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    role: str = Field(default="user", max_length=20)          # "user" | "admin"
    review_status: str = Field(default="pending", max_length=20)  # "pending" | "approved" | "rejected" | "disabled"
    last_login_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewRecord(SQLModel, table=True):
    __tablename__ = "review_records"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    reviewer_id: uuid.UUID = Field(foreign_key="users.id")
    action: str = Field(max_length=20)  # "approved" | "rejected"
    remark: str | None = Field(default=None, max_length=500)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
