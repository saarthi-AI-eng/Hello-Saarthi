"""DAO for tutor chat conversations and messages."""

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import ChatMessage, Conversation


class ConversationDAO:
    @staticmethod
    async def create(db: AsyncSession, user_id: int, title: str = "New Chat") -> Conversation:
        c = Conversation(user_id=user_id, title=title)
        db.add(c)
        await db.flush()
        await db.refresh(c)
        return c

    @staticmethod
    async def get_by_id(db: AsyncSession, conversation_id: int, user_id: int | None = None) -> Conversation | None:
        q = select(Conversation).where(Conversation.id == conversation_id)
        if user_id is not None:
            q = q.where(Conversation.user_id == user_id)
        r = await db.execute(q)
        return r.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        q = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        r = await db.execute(q)
        return list(r.scalars().all())

    @staticmethod
    async def count_by_user(db: AsyncSession, user_id: int) -> int:
        q = select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        r = await db.execute(q)
        return r.scalar() or 0

    @staticmethod
    async def update_title(db: AsyncSession, conversation_id: int, user_id: int, title: str) -> Conversation | None:
        c = await ConversationDAO.get_by_id(db, conversation_id, user_id)
        if not c:
            return None
        c.title = title
        await db.flush()
        await db.refresh(c)
        return c

    @staticmethod
    async def delete(db: AsyncSession, conversation_id: int, user_id: int) -> bool:
        c = await ConversationDAO.get_by_id(db, conversation_id, user_id)
        if not c:
            return False
        await db.delete(c)
        await db.flush()
        return True

    @staticmethod
    async def touch(db: AsyncSession, conversation_id: int) -> None:
        """Update updated_at (e.g. after adding a message)."""
        await db.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(updated_at=datetime.now(timezone.utc))
        )
        await db.flush()


class ChatMessageDAO:
    @staticmethod
    async def create(db: AsyncSession, conversation_id: int, role: str, content: str) -> ChatMessage:
        m = ChatMessage(conversation_id=conversation_id, role=role, content=content)
        db.add(m)
        await db.flush()
        await db.refresh(m)
        return m

    @staticmethod
    async def list_by_conversation(db: AsyncSession, conversation_id: int) -> list[ChatMessage]:
        q = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        r = await db.execute(q)
        return list(r.scalars().all())
