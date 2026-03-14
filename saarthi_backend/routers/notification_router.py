"""Notifications (under /api/notifications)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.notification_schemas import NotificationResponse
from saarthi_backend.schema.common_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.service import notification_service
from saarthi_backend.utils.exceptions import NotFoundError

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notif_to_response(n):
    return NotificationResponse(
        id=str(n.id),
        type=n.type,
        title=n.title,
        body=n.body,
        link=n.link,
        readAt=n.read_at.isoformat() if n.read_at else None,
        createdAt=n.created_at.isoformat() if n.created_at else "",
    )


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    unread_only: bool = False,
):
    """List current user's notifications (paginated)."""
    notifications, total = await notification_service.list_notifications(
        db, user.id, unread_only=unread_only, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse(
        items=[_notif_to_response(n) for n in notifications],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark notification as read."""
    ok = await notification_service.mark_read(db, notification_id, user.id)
    if not ok:
        raise NotFoundError("Notification not found.", details=None)
    await db.commit()
    return {"success": True}
