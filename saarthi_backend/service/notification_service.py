"""Notification feature service."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import NotificationDAO
from saarthi_backend.model import Notification


async def list_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    items = await NotificationDAO.list_by_user(
        db, user_id, unread_only=unread_only, limit=limit, offset=offset
    )
    total = await NotificationDAO.count_by_user(db, user_id, unread_only=unread_only)
    return items, total


async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> bool:
    return await NotificationDAO.mark_read(db, notification_id, user_id)
