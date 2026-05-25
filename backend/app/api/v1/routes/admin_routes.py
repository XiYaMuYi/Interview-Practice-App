"""Admin routes — user review and management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import DbSession, get_current_admin_user
from app.domain.models.user import User
from app.domain.schemas import AdminReviewRequest, AdminUserListItem
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.utils.request import get_client_ip

router = APIRouter()


@router.get("/users/pending", response_model=list[AdminUserListItem])
async def list_pending_users(
    session: DbSession,
    _admin: User = Depends(get_current_admin_user),
):
    """List all users awaiting review (admin only)."""
    service = AuthService(session)
    users = await service.list_pending_users()
    return [
        AdminUserListItem(
            user_id=str(u.id),
            username=u.username,
            email=u.email,
            role=u.role,
            review_status=u.review_status,
            is_active=u.is_active,
            created_at=u.created_at.isoformat() if u.created_at else "",
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        )
        for u in users
    ]


@router.get("/users", response_model=list[AdminUserListItem])
async def list_all_users(
    session: DbSession,
    _admin: User = Depends(get_current_admin_user),
):
    """List all users (admin only)."""
    service = AuthService(session)
    users = await service.list_all_users()
    return [
        AdminUserListItem(
            user_id=str(u.id),
            username=u.username,
            email=u.email,
            role=u.role,
            review_status=u.review_status,
            is_active=u.is_active,
            created_at=u.created_at.isoformat() if u.created_at else "",
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        )
        for u in users
    ]


@router.post("/users/{user_id}/review")
async def review_user(
    user_id: str,
    data: AdminReviewRequest,
    request: Request,
    session: DbSession,
    admin: User = Depends(get_current_admin_user),
):
    """Approve or reject a user's registration (admin only)."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    service = AuthService(session)
    user = await service.review_user(
        user_id=uid,
        reviewer_id=admin.id,
        action=data.action,
        remark=data.remark,
    )

    # Audit log (same transaction, non-blocking)
    try:
        audit_service = AuditService(session)
        await audit_service.log(
            action=f"user.{data.action}",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="user",
            target_id=user_id,
            detail=f"Admin {admin.username} {data.action} user {user.username}" + (f" (remark: {data.remark})" if data.remark else ""),
            ip_address=get_client_ip(request),
        )
    except Exception:
        pass  # Do not break review if audit logging fails

    await session.commit()

    return {
        "user_id": str(user.id),
        "username": user.username,
        "review_status": user.review_status,
        "is_active": user.is_active,
    }
