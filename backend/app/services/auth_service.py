"""Auth service — simple token auth for single user.

AUTH_ENABLED=false by default — routes are open.
When AUTH_ENABLED=true, JWT tokens are required for protected endpoints.
"""

from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Handles login, token creation, and validation for single-user mode."""

    # Default single-user credentials (should be overridden in .env)
    DEFAULT_USERNAME = "admin"
    DEFAULT_PASSWORD = "admin"

    def __init__(self, session: AsyncSession):
        self.session = session

    def create_access_token(self, subject: str, expires_delta: timedelta | None = None) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        payload = {"sub": subject, "exp": expire}
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def create_refresh_token(self, subject: str) -> str:
        """Create a JWT refresh token (long-lived)."""
        expire = datetime.utcnow() + timedelta(days=7)
        payload = {"sub": subject, "type": "refresh", "exp": expire}
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def verify_token(self, token: str) -> str:
        """Decode and validate a JWT token. Returns the subject (user_id)."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload["sub"]
        except JWTError as e:
            raise UnauthorizedError(f"Invalid token: {e}")

    async def authenticate(self, username: str, password: str) -> str:
        """Authenticate a user. In single-user mode, checks against configured credentials.

        Returns access token on success.
        """
        valid_username = getattr(settings, "AUTH_USERNAME", self.DEFAULT_USERNAME)
        valid_password = getattr(settings, "AUTH_PASSWORD", self.DEFAULT_PASSWORD)

        if username != valid_username or password != valid_password:
            raise UnauthorizedError("Invalid username or password")

        token = self.create_access_token(subject=username)
        logger.info(f"User '{username}' logged in successfully")
        return token

    @classmethod
    def is_auth_required(cls) -> bool:
        """Check if authentication is enabled."""
        return settings.AUTH_ENABLED

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password for storage."""
        return pwd_context.hash(password)

    @classmethod
    def verify_password(cls, plain: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain, hashed)
