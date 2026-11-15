"""Manual QA review service — bridges the FastAPI backend to
src/content_qa/manual_review.py (which owns the actual JSONL read-modify-
write) and saarthi_qa_review_actions (the audit log). No direct Qdrant/
embedding access here at all — accepted content is picked up by the
existing, unmodified normalize_content_kb -> chunk -> embed -> Qdrant
pipeline the next time it runs; this service never calls into any of
that itself (Phase 3: "do not directly upsert from the QA dashboard").
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import QAReviewDAO
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.exceptions import NotFoundError, ValidationError
from scripts.schemas import ContentType
from src.content_qa import manual_review
from src.content_qa.manual_review import ManualReviewConflict, ManualReviewNotFound
from src.knowledge_base.config import KBConfig


def _kb_config() -> KBConfig:
    settings = get_settings()
    root = settings.saarthi_kb_data_root
    if not root:
        raise ValidationError(
            "SAARTHI_KB_DATA_ROOT is not configured on the backend — the QA dashboard has nothing to read. "
            "Set it the same way the KB pipeline itself does (see docs/KB_PIPELINE_SETUP.md)."
        )
    return KBConfig(data_root=Path(root))


async def dashboard_stats(db: AsyncSession) -> dict:
    config = _kb_config()
    pending = manual_review.list_pending_items(config)
    reviewed_today = await QAReviewDAO.count_reviewed_today(db)
    approved = await QAReviewDAO.count_by_decision(db, "accept")
    rejected = await QAReviewDAO.count_by_decision(db, "reject")
    return {
        "pendingReview": len(pending),
        "reviewedToday": reviewed_today,
        "approved": approved,
        "rejected": rejected,
    }


def _group_key(item: dict) -> str:
    return item["source_file"]


def pending_queue(
    limit: int = 20,
    offset: int = 0,
    content_type: Optional[str] = None,
    course: Optional[str] = None,
) -> dict:
    config = _kb_config()
    items = manual_review.list_pending_items(config)

    if content_type:
        items = [i for i in items if i["content_type"] == content_type]
    if course:
        items = [i for i in items if (i.get("course") or "").lower() == course.lower()]

    # Lowest QA score first, then oldest (qa_timestamp) next — ties (no
    # score) sort after scored items, never crash on a missing score.
    items.sort(key=lambda i: (i["qa_score"] if i["qa_score"] is not None else float("inf"), i.get("qa_timestamp") or ""))

    total = len(items)
    page_items = items[offset: offset + limit]

    groups: dict[str, list[dict]] = {}
    for item in page_items:
        groups.setdefault(_group_key(item), []).append(item)

    documents = [
        {"source_file": source_file, "content_type": rows[0]["content_type"], "items": rows}
        for source_file, rows in groups.items()
    ]

    return {"total": total, "limit": limit, "offset": offset, "documents": documents}


def content_detail(source_jsonl_path: str, content_id: str) -> dict:
    try:
        record = manual_review.get_record_detail(Path(source_jsonl_path), content_id)
    except ManualReviewNotFound as exc:
        raise NotFoundError(str(exc)) from exc
    qa_meta = (record.metadata or {}).get("qa") or {}
    hints = manual_review.build_review_hints(record)
    return {
        "contentId": record.content_id,
        "sourceFile": record.source,
        "contentType": record.content_type.value,
        "course": record.course,
        "page": record.page,
        "startTime": record.start_time,
        "endTime": record.end_time,
        "text": record.text,
        "qaStatus": record.qa_status.value,
        "qaScore": qa_meta.get("score"),
        "qaChecks": qa_meta.get("checks") or {},
        "qaIssues": qa_meta.get("issues") or [],
        "recognitionConfidence": (record.metadata or {}).get("ocr_confidence"),
        "qaVersion": qa_meta.get("version"),
        "qaTimestamp": qa_meta.get("timestamp"),
        "lineConfidences": hints["line_confidences"],
        "equationSuggestions": hints["equation_suggestions"],
        "hasSourceImage": record.content_type == ContentType.PDF_NOTE and record.page is not None,
    }


def source_image(source_jsonl_path: str, content_id: str) -> bytes:
    try:
        record = manual_review.get_record_detail(Path(source_jsonl_path), content_id)
    except ManualReviewNotFound as exc:
        raise NotFoundError(str(exc)) from exc
    try:
        return manual_review.render_source_page_image(record)
    except manual_review.ManualReviewNotFound as exc:
        raise NotFoundError(str(exc)) from exc
    except manual_review.ManualReviewError as exc:
        raise ValidationError(str(exc)) from exc


async def review_history(db: AsyncSession, content_id: str) -> list[dict]:
    rows = await QAReviewDAO.history_for_content(db, content_id)
    return [
        {
            "reviewerId": r.reviewer_id,
            "decision": r.decision,
            "previousStatus": r.previous_status,
            "newStatus": r.new_status,
            "reason": r.reason,
            "edited": r.edited,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def submit_review(
    db: AsyncSession,
    source_jsonl_path: str,
    content_id: str,
    decision: str,
    reviewer_id: int,
    reason: Optional[str] = None,
    edited_text: Optional[str] = None,
) -> dict:
    try:
        result = manual_review.apply_manual_review(
            Path(source_jsonl_path), content_id, decision, reviewer_id=str(reviewer_id), reason=reason,
            edited_text=edited_text,
        )
    except ManualReviewNotFound as exc:
        raise NotFoundError(str(exc)) from exc
    except ManualReviewConflict as exc:
        raise ValidationError(str(exc)) from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    await QAReviewDAO.create(
        db,
        content_id=content_id,
        source_file=source_jsonl_path,
        reviewer_id=reviewer_id,
        decision=decision,
        previous_status=result["previous_status"],
        new_status=result["new_status"],
        reason=reason,
        edited=result.get("edited", False),
    )
    await db.commit()
    return result
