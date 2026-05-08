"""Auth routes — login, token refresh."""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import DbSession
from app.domain.schemas import LoginRequest, LoginResponse, TokenRefreshRequest, TokenRefreshResponse
from app.services.auth_service import AuthService
from app.core.config import settings

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(session: DbSession, data: LoginRequest):
    """Authenticate user and return access token."""
    if not AuthService.is_auth_required():
        raise HTTPException(
            status_code=403,
            detail="Authentication is disabled. Set AUTH_ENABLED=true to enable login.",
        )

    service = AuthService(session)
    access_token = await service.authenticate(data.username, data.password)
    refresh_token = service.create_refresh_token(data.username)

    return LoginResponse(
        access_token=access_token,
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
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access_token = service.create_access_token(subject)
    return TokenRefreshResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me")
async def get_current_user(session: DbSession, authorization: str | None = Header(None)):
    """Get current authenticated user info."""
    if not AuthService.is_auth_required():
        return {"user_id": "anonymous", "username": "single-user-mode"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.split(" ", 1)[1]
    service = AuthService(session)
    user_id = service.verify_token(token)
    return {"user_id": user_id, "username": user_id}


@router.get("/config")
async def auth_config():
    """Return auth configuration for frontend."""
    return {
        "auth_enabled": AuthService.is_auth_required(),
        "public_mode": settings.PUBLIC_MODE,
    }
