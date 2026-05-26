"""API dependencies for auth, sessions, and user context."""

import uuid

from fastapi import Depends, Header, HTTPException
from jose import jwt
from sqlalchemy import select

from app.core.config import settings
from app.domain.models.user import User
from app.infra.data_isolation import UserContext
from app.infra.db.session import DbSession


ANONYMOUS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _anonymous_user() -> User:
    return User(
        id=ANONYMOUS_USER_ID,
        username="anonymous",
        password_hash="",
        is_active=True,
        role="admin",
        review_status="approved",
    )


async def get_current_user(
    session: DbSession,
    authorization: str | None = Header(None),
) -> User:
    """Validate a bearer token and return the current user.

    When auth is disabled, return a synthetic anonymous user.
    """
    if not settings.AUTH_ENABLED:
        return _anonymous_user()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type: refresh token used as access token")
        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=401, detail="Token missing subject")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    stmt = select(User).where(User.username == subject)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail=f"User '{subject}' not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    if user.review_status != "approved":
        raise HTTPException(status_code=403, detail="Account has not been approved yet")
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user


async def get_user_context(
    current_user: User | None = Depends(get_current_user),
) -> UserContext:
    """Return a strict user context for protected routes."""
    if current_user is None or current_user.id == ANONYMOUS_USER_ID:
        return UserContext(user_id=None, is_anonymous=True)
    return UserContext(
        user_id=str(current_user.id),
        is_anonymous=False,
        is_admin=current_user.role == "admin",
    )


__all__ = [
    "ANONYMOUS_USER_ID",
    "DbSession",
    "UserContext",
    "get_current_admin_user",
    "get_current_user",
    "get_user_context",
]
