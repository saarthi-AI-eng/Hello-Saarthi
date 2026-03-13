"""Data access for conversation context."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import ConversationContext


class ContextDAO:
    """DAO for saarthi_conversation_context table."""

    @staticmethod
    async def get_by_conversation_id(db: AsyncSession, conversation_id: str) -> Optional[ConversationContext]:
        """Get context by conversation_id."""
        result = await db.execute(
            select(ConversationContext).where(ConversationContext.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        conversation_id: str,
        summary: Optional[str] = None,
        metadata_: Optional[dict[str, Any]] = None,
    ) -> ConversationContext:
        """Insert or update context for conversation_id."""
        row = await ContextDAO.get_by_conversation_id(db, conversation_id)
        if row:
            if summary is not None:
                row.summary = summary
            if metadata_ is not None:
                row.metadata_ = metadata_
            await db.flush()
            await db.refresh(row)
            return row
        row = ConversationContext(
            conversation_id=conversation_id,
            summary=summary,
            metadata_=metadata_,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row
