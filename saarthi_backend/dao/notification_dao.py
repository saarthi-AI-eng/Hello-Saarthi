"""DAO for notifications."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import Notification


class NotificationDAO:
    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.read_at.is_(None))
        q = q.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_user(
        db: AsyncSession, user_id: int, unread_only: bool = False
    ) -> int:
        q = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id
        )
        if unread_only:
            q = q.where(Notification.read_at.is_(None))
        r = await db.execute(q)
        return r.scalar() or 0

    @staticmethod
    async def get_by_id(db: AsyncSession, notification_id: int) -> Notification | None:
        result = await db.execute(select(Notification).where(Notification.id == notification_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        type: str,
        title: str,
        body: str,
        link: str | None = None,
    ) -> Notification:
        n = Notification(user_id=user_id, type=type, title=title, body=body, link=link)
        db.add(n)
        await db.flush()
        await db.refresh(n)
        return n

    @staticmethod
    async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> bool:
        n = await NotificationDAO.get_by_id(db, notification_id)
        if not n or n.user_id != user_id:
            return False
        n.read_at = datetime.now(timezone.utc)
        await db.flush()
        return True
