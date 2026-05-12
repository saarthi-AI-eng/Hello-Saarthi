"""Chat feature service: conversations, messages, study plan."""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.ai import run_chat
from saarthi_backend.dao import ChatMessageDAO, ConversationDAO
from saarthi_backend.model import ChatMessage, Conversation
from saarthi_backend.schema.chat_schemas import (
    StudyPlanDayBlock,
    StudyPlanRequest,
    StudyPlanResponse,
)

logger = logging.getLogger(__name__)


async def create_conversation(db: AsyncSession, user_id: int, title: str = "New Chat") -> Conversation:
    return await ConversationDAO.create(db, user_id, title=title)


async def list_conversations(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> tuple[list[Conversation], int]:
    items = await ConversationDAO.list_by_user(db, user_id, limit=limit, offset=offset)
    total = await ConversationDAO.count_by_user(db, user_id)
    return items, total


async def get_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> tuple[Conversation | None, list[ChatMessage]]:
    c = await ConversationDAO.get_by_id(db, conversation_id, user_id)
    if not c:
        return None, []
    messages = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    return c, messages


async def update_conversation_title(
    db: AsyncSession, conversation_id: int, user_id: int, title: str
) -> Conversation | None:
    return await ConversationDAO.update_title(db, conversation_id, user_id, title)


async def delete_conversation(db: AsyncSession, conversation_id: int, user_id: int) -> bool:
    return await ConversationDAO.delete(db, conversation_id, user_id)


def _apply_document_context(message: str, context_material_title: str | None) -> str:
    """Prepend document context so the AI answers in the context of the viewed material."""
    if not context_material_title or not context_material_title.strip():
        return message
    return (
        f'The user is currently viewing the document "{context_material_title.strip()}". '
        f"Answer their question in that context when relevant.\n\nQuestion: {message}"
    )


async def send_message(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
    message: str,
    context_material_title: str | None = None,
) -> tuple[ChatMessage, ChatMessage] | None:
    conv = await ConversationDAO.get_by_id(db, conversation_id, user_id)
    if not conv:
        return None
    existing = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    user_msg = await ChatMessageDAO.create(db, conversation_id, "user", message)
    history = [{"role": m.role, "content": m.content} for m in existing]
    prompt_for_ai = _apply_document_context(message, context_material_title)
    history.append({"role": "user", "content": prompt_for_ai})
    assistant_content = await run_chat(prompt_for_ai, history, mind_mode=False)
    assistant_msg = await ChatMessageDAO.create(db, conversation_id, "assistant", assistant_content)
    if len(existing) == 0:
        title = (message.strip()[:200] + "…") if len(message.strip()) > 200 else message.strip()
        await ConversationDAO.update_title(db, conversation_id, user_id, title or "New Chat")
    await ConversationDAO.touch(db, conversation_id)
    return user_msg, assistant_msg


async def stateless_message(
    message: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
    context_material_title: str | None = None,
) -> str:
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in conversation_history]
    prompt_for_ai = _apply_document_context(message, context_material_title)
    history.append({"role": "user", "content": prompt_for_ai})
    return await run_chat(prompt_for_ai, history, mind_mode=mind_mode)


# ─── Study Plan Generator ─────────────────────────────────────────────────────

_STUDY_PLAN_SYSTEM = """You are an expert academic advisor for engineering students.
Generate a structured 7-day weekly study plan in valid JSON.

Rules:
- Prioritize topics where quiz scores are low (< 70%)
- Front-load urgent deadlines to earlier days
- Balance subjects — don't study same subject >2 consecutive sessions
- Each session = 90 minutes
- Include specific topics, not generic advice
- Return ONLY a JSON object with this exact structure:
{
  "weekPlan": [
    {
      "day": "Monday",
      "sessions": ["09:00–10:30 · DSP: Z-transform review (weak area)", "..."],
      "totalHours": 3.0
    }
  ],
  "summary": "one paragraph summary",
  "priorityTopics": ["topic1", "topic2", "topic3"]
}"""


async def generate_study_plan(
    db: AsyncSession,
    user_id: int,
    body: StudyPlanRequest,
) -> StudyPlanResponse:
    """Call GPT-4.1 to generate a personalized weekly study plan."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        # Build context summary
        courses_text = "\n".join(
            f"- {c.title} ({c.code}): {c.progressPercent}% complete"
            for c in body.courses
        ) or "No enrolled courses provided."

        deadlines_text = "\n".join(
            f"- {d.title} [{d.type}] for {d.course} — due {d.dueDate}"
            for d in sorted(body.deadlines, key=lambda x: x.dueDate)
        ) or "No upcoming deadlines."

        scores_text = "\n".join(
            f"- {q.quizTitle}: {q.score:.0f}% " +
            (f"(weak: {', '.join(q.weakTopics)})" if q.weakTopics else "")
            for q in body.recentQuizScores
        ) or "No recent quiz data."

        focus_text = f"\nStudent wants to focus on: {body.focusArea}" if body.focusArea else ""

        user_prompt = f"""Student profile:
Available hours per day: {body.hoursPerDay}h{focus_text}

Enrolled courses:
{courses_text}

Upcoming deadlines:
{deadlines_text}

Recent quiz performance:
{scores_text}

Generate a 7-day study plan."""

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _STUDY_PLAN_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        week_plan = [
            StudyPlanDayBlock(
                day=d["day"],
                sessions=d.get("sessions", []),
                totalHours=float(d.get("totalHours", 0)),
            )
            for d in data.get("weekPlan", [])
        ]

        return StudyPlanResponse(
            weekPlan=week_plan,
            summary=data.get("summary", ""),
            priorityTopics=data.get("priorityTopics", []),
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.exception("Study plan generation failed: %s", e)
        # Return a minimal fallback so the endpoint doesn't 500
        return StudyPlanResponse(
            weekPlan=[],
            summary="Could not generate study plan. Please try again.",
            priorityTopics=[],
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )
