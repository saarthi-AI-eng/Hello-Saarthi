"""DAO for the manual QA review audit log (saarthi_qa_review_actions)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import QAReviewAction


class QAReviewDAO:
    @staticmethod
    async def create(
        db: AsyncSession,
        content_id: str,
        source_file: str,
        reviewer_id: int,
        decision: str,
        previous_status: str,
        new_status: str,
        reason: str | None = None,
        edited: bool = False,
    ) -> QAReviewAction:
        action = QAReviewAction(
            content_id=content_id,
            source_file=source_file,
            reviewer_id=reviewer_id,
            decision=decision,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            edited=edited,
        )
        db.add(action)
        await db.flush()
        await db.refresh(action)
        return action

    @staticmethod
    async def history_for_content(db: AsyncSession, content_id: str) -> list[QAReviewAction]:
        result = await db.execute(
            select(QAReviewAction)
            .where(QAReviewAction.content_id == content_id)
            .order_by(QAReviewAction.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def recent(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[QAReviewAction]:
        result = await db.execute(
            select(QAReviewAction).order_by(QAReviewAction.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_reviewed_today(db: AsyncSession) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.count()).select_from(QAReviewAction).where(QAReviewAction.created_at >= today_start)
        )
        return result.scalar() or 0

    @staticmethod
    async def count_by_decision(db: AsyncSession, decision: str) -> int:
        result = await db.execute(
            select(func.count()).select_from(QAReviewAction).where(QAReviewAction.decision == decision)
        )
        return result.scalar() or 0
