"""Auth routes — register, login, token refresh, user info."""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import DbSession, get_current_user
from app.domain.models.user import User
from app.domain.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from app.services.auth_service import AuthService
from app.core.config import settings

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register(session: DbSession, data: RegisterRequest):
    """Register a new user account."""
    if not AuthService.is_auth_required():
        raise HTTPException(
            status_code=403,
            detail="Authentication is disabled. Set AUTH_ENABLED=true to enable registration.",
        )

    service = AuthService(session)
    user = await service.register(
        username=data.username,
        password=data.password,
        email=data.email,
    )
    await session.commit()

    access_token = service.create_access_token(subject=user.username)
    refresh_token = service.create_refresh_token(subject=user.username)

    return RegisterResponse(
        user_id=str(user.id),
        username=user.username,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=LoginResponse)
async def login(session: DbSession, data: LoginRequest):
    """Authenticate user and return access token."""
    if not AuthService.is_auth_required():
        raise HTTPException(
            status_code=403,
            detail="Authentication is disabled. Set AUTH_ENABLED=true to enable login.",
        )

    service = AuthService(session)
    user = await service.authenticate(data.username, data.password)
    access_token = service.create_access_token(subject=user.username)
    refresh_token = service.create_refresh_token(subject=user.username)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(session: DbSession, data: TokenRefreshRequest):
    """Refresh an access token using a refresh token."""
    if not AuthService.is_auth_required():
        raise HTTPException(status_code=403, detail="Authentication is disabled.")

    service = AuthService(session)
    subject = service.verify_token(data.refresh_token)

    # Verify this is a refresh token (check type claim)
    try:
        from jose import jwt
        payload = jwt.decode(data.refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Not a refresh token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify user still exists and is active
    user = await service.get_user_by_username(subject)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User no longer exists or is disabled")

    new_access_token = service.create_access_token(subject)
    return TokenRefreshResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@router.get("/config")
async def auth_config():
    """Return auth configuration for frontend."""
    return {
        "auth_enabled": AuthService.is_auth_required(),
        "public_mode": settings.PUBLIC_MODE,
    }
