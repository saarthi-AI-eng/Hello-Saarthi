"""Manual QA review audit log.

This table is the audit trail only — WHO decided WHAT, WHEN, and WHY.
The actual qa_status that the KB pipeline's normalizer reads stays in the
OCR/transcript ContentRecord JSONL files (src/content_qa/manual_review.py
applies it there, atomically). Nothing here is a second source of truth
for eligibility — it's purely a durable, queryable log of review actions,
reusing this app's existing Postgres database rather than introducing a
new one.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from saarthi_backend.model.context_model import Base


class QAReviewAction(Base):
    """One row per manual review decision (accept/reject/reprocess)."""

    __tablename__ = "saarthi_qa_review_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("saarthi_users.id", ondelete="SET NULL"), nullable=True, index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # accept | reject | reprocess
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
