"""Auth service — database-backed user authentication with JWT.

When AUTH_ENABLED=false (default), all routes are open and a synthetic
anonymous user is used.  When AUTH_ENABLED=true, users must register and
login with password-hashed credentials.
"""

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.domain.models.user import User, ReviewRecord

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Handles user registration, login, token creation, and validation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Password hashing ──────────────────────────────────────────────

    @classmethod
    def hash_password(cls, password: str) -> str:
        return pwd_context.hash(password)

    @classmethod
    def verify_password(cls, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # ── JWT token helpers ─────────────────────────────────────────────

    def create_access_token(self, subject: str, extra_claims: dict | None = None, expires_delta: timedelta | None = None) -> str:
        """Create a JWT access token (default 30 minutes)."""
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        payload = {"sub": subject, "exp": expire}
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def create_refresh_token(self, subject: str) -> str:
        """Create a JWT refresh token (7 days)."""
        expire = datetime.utcnow() + timedelta(days=7)
        payload = {"sub": subject, "type": "refresh", "exp": expire}
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def verify_token(self, token: str) -> str:
        """Decode and validate a JWT token. Returns the subject (username)."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload["sub"]
        except JWTError as e:
            raise UnauthorizedError(f"Invalid token: {e}")

    # ── User operations ───────────────────────────────────────────────

    async def register(self, username: str, password: str, email: str | None = None) -> User:
        """Register a new user. New users get role='user', review_status='pending', is_active=False."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise UnauthorizedError(f"Username '{username}' already exists")

        user = User(
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            is_active=False,
            role="user",
            review_status="pending",
        )
        self.session.add(user)
        await self.session.flush()
        logger.info(f"User registered: {username} (pending review)")
        return user

    async def authenticate(self, username: str, password: str) -> User:
        """Authenticate a user by username and password. Returns the User on success."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not self.verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid username or password")

        if not user.is_active:
            raise UnauthorizedError("User account is disabled")

        # Check review status
        if user.review_status == "pending":
            raise HTTPException(status_code=403, detail="账号审核中，请等待管理员审核")
        if user.review_status == "rejected":
            raise HTTPException(status_code=403, detail="账号审核未通过")
        if user.review_status == "disabled":
            raise HTTPException(status_code=403, detail="账号已被禁用")

        # Update last login time
        user.last_login_at = datetime.utcnow()

        logger.info(f"User '{username}' logged in successfully")
        return user

    async def get_user_by_username(self, username: str) -> User | None:
        """Look up a user by username."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending_users(self) -> list[User]:
        """List all users with review_status='pending'."""
        stmt = select(User).where(User.review_status == "pending").order_by(User.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_users(self) -> list[User]:
        """List all users."""
        stmt = select(User).order_by(User.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def review_user(
        self,
        user_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        action: str,
        remark: str | None = None,
    ) -> User:
        """Approve or reject a user's registration. Creates a ReviewRecord and updates user status."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")

        if action not in ("approved", "rejected"):
            raise HTTPException(status_code=400, detail="无效的操作类型")

        # Update user status
        user.review_status = action
        user.is_active = action == "approved"

        # Create review record
        record = ReviewRecord(
            user_id=user_id,
            reviewer_id=reviewer_id,
            action=action,
            remark=remark,
        )
        self.session.add(record)

        logger.info(f"User {user_id} reviewed: {action} by {reviewer_id}")
        return user

    # ── Config ────────────────────────────────────────────────────────

    @classmethod
    def is_auth_required(cls) -> bool:
        return settings.AUTH_ENABLED
