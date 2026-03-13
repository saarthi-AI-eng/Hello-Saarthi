"""ORM model for conversation context (GET/POST /context)."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class ConversationContext(Base):
    """Stored context per conversation_id."""

    __tablename__ = "saarthi_conversation_context"

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )
