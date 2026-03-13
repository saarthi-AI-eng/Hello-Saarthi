"""Context service: get/upsert conversation context."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import ContextDAO
from saarthi_backend.model import ConversationContext
from saarthi_backend.schema.context_schemas import ContextGetResponse, ContextUpsertRequest
from saarthi_backend.utils.constants import METADATA_MAX_KEYS, SUMMARY_MAX_LENGTH
from saarthi_backend.utils.exceptions import ValidationError


def _truncate_summary(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return s[:SUMMARY_MAX_LENGTH] if len(s) > SUMMARY_MAX_LENGTH else s


def _truncate_metadata(m: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if m is None or len(m) <= METADATA_MAX_KEYS:
        return m
    keys = list(m.keys())[:METADATA_MAX_KEYS]
    return {k: m[k] for k in keys}


async def get_context(db: AsyncSession, conversation_id: str) -> Optional[ContextGetResponse]:
    """Get context by conversation_id. Returns None if not found."""
    row = await ContextDAO.get_by_conversation_id(db, conversation_id)
    if not row:
        return None
    updated_at_str = row.updated_at.isoformat() if row.updated_at else None
    return ContextGetResponse(
        conversation_id=row.conversation_id,
        summary=row.summary,
        metadata=row.metadata_,
        updated_at=updated_at_str,
    )


async def upsert_context(
    db: AsyncSession,
    req: ContextUpsertRequest,
) -> ContextGetResponse:
    """Upsert context for conversation_id."""
    summary = _truncate_summary(req.summary)
    metadata_ = _truncate_metadata(req.metadata)
    row = await ContextDAO.upsert(db, req.conversation_id, summary=summary, metadata_=metadata_)
    await db.commit()
    updated_at_str = row.updated_at.isoformat() if row.updated_at else None
    return ContextGetResponse(
        conversation_id=row.conversation_id,
        summary=row.summary,
        metadata=row.metadata_,
        updated_at=updated_at_str,
    )
