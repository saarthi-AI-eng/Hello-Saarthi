"""Weak topics for a student (WBS 3.2.3+): read-only input to retrieval boosting.

Sources (both owned by Software; AI only reads them):
  saarthi_topic_mastery   score < WEAK_TOPIC_THRESHOLD (default 0.6)   [migration 007]
  saarthi_quiz_attempts   attempts scored below the quiz's passing score → quiz title

The terms only *reorder* retrieved chunks (see src.retrieval.pipeline); they never
filter, so a student with no history gets exactly the old behaviour.
WEAK_TOPIC_BOOST=0 disables the lookup.
"""
from __future__ import annotations

import os
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.utils.logging import get_logger

logger = get_logger(__name__)

_NOISE = re.compile(r"\b(quiz|test|exam|week|unit|module|chapter|lecture|part|practice|mock)\b|\d+|[:#\-–—()]", re.I)


def _topic_from_title(title: str) -> str:
    return re.sub(r"\s+", " ", _NOISE.sub(" ", title or "")).strip()


async def get_weak_topics(db: AsyncSession, user_id: int, course_id: int | None = None, limit: int = 5) -> list[str]:
    if os.environ.get("WEAK_TOPIC_BOOST", "1").strip().lower() in ("0", "false", "no", "off"):
        return []
    threshold = float(os.environ.get("WEAK_TOPIC_THRESHOLD", "0.6"))
    topics: list[str] = []
    try:
        # SAVEPOINT: a missing table must not abort the request's transaction.
        async with db.begin_nested():
            rows = await db.execute(
                text(
                    "SELECT topic FROM saarthi_topic_mastery "
                    "WHERE user_id = :uid AND score < :th ORDER BY score ASC LIMIT :n"
                ),
                {"uid": user_id, "th": threshold, "n": limit},
            )
            topics.extend(r[0] for r in rows if r[0])
    except Exception as e:
        logger.debug("topic mastery unavailable: %s", e)
    try:
        async with db.begin_nested():
            course_clause = "AND q.course_id = :cid" if course_id is not None else ""
            rows = await db.execute(
                text(
                    "SELECT q.title FROM saarthi_quiz_attempts a JOIN saarthi_quizzes q ON q.id = a.quiz_id "
                    "WHERE a.user_id = :uid AND a.score IS NOT NULL AND a.score < q.passing_score "
                    f"{course_clause} ORDER BY a.started_at DESC LIMIT :n"
                ),
                {"uid": user_id, "cid": course_id, "n": limit},
            )
            topics.extend(t for t in (_topic_from_title(r[0]) for r in rows) if len(t) > 2)
    except Exception as e:
        logger.debug("quiz attempts unavailable: %s", e)
    seen: dict[str, None] = {}
    for t in topics:
        seen.setdefault(t.strip(), None)
    return list(seen)[:limit]


async def flag_weak_topic(db: AsyncSession, user_id: int, topic: str, score: float = 0.4) -> bool:
    """Socratic escalation (spec 4.4): after 3 unsuccessful attempts the topic is recorded as a
    weakness for the student's tracker (saarthi_topic_mastery, migration 007). Never raises."""
    if not topic:
        return False
    try:
        async with db.begin_nested():
            await db.execute(
                text(
                    "INSERT INTO saarthi_topic_mastery (user_id, topic, score, source, updated_at) "
                    "VALUES (:uid, :topic, :score, 'socratic', NOW()) "
                    "ON CONFLICT (user_id, topic) DO UPDATE SET "
                    "score = LEAST(saarthi_topic_mastery.score, EXCLUDED.score), source = 'socratic', updated_at = NOW()"
                ),
                {"uid": user_id, "topic": topic[:255], "score": score},
            )
        return True
    except Exception as e:
        logger.debug("weak-topic flag skipped: %s", e)
        return False
