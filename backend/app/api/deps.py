"""API-level dependencies — auth, session wiring, etc."""

import uuid

from fastapi import Depends, Header, HTTPException
from jose import jwt
from sqlalchemy import select

from app.core.config import settings
from app.domain.models.user import User
from app.infra.db.session import DbSession


ANONYMOUS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


async def get_current_user(
    authorization: str | None = Header(None),
    session: DbSession = Depends(),
) -> User:
    """FastAPI dependency that extracts and validates the current user from a Bearer token.

    Usage::

        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            ...

    When AUTH_ENABLED is False, returns a synthetic anonymous user so that
    routes can still function without real credentials.
    """
    if not settings.AUTH_ENABLED:
        return User(
            id=ANONYMOUS_USER_ID,
            username="anonymous",
            password_hash="",
            is_active=True,
        )

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
    return user


__all__ = ["DbSession", "get_current_user"]
