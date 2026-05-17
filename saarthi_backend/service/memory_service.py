"""
Tiered memory service for Saarthi chat.

Tier 1 — last WORKING_WINDOW turns verbatim (always in context)
Tier 2 — session summary paragraph (lazy, updated every SUMMARIZE_EVERY new turns)

Uses existing saarthi_conversation_context table:
  conversation_id  VARCHAR  (PK, stored as str(int id))
  summary          TEXT     compressed older turns
  metadata         JSONB    {"up_to_message_id": <int>}
  updated_at       TIMESTAMP
"""

import asyncio
import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

WORKING_WINDOW = 6       # recent turns kept verbatim
SUMMARIZE_EVERY = 4      # trigger re-summarization after this many new turns beyond last checkpoint
FIRST_SUMMARY_AT = 8     # trigger first-ever summary once DB has this many messages (covers the gap)
MAX_SUMMARY_TOKENS = 200 # rough word budget for the summary paragraph


async def _read_context(db: AsyncSession, conv_id: int) -> tuple[str | None, int | None]:
    """Returns (summary_text, up_to_message_id) from saarthi_conversation_context."""
    try:
        row = await db.execute(
            text("SELECT summary, metadata FROM saarthi_conversation_context WHERE conversation_id = :cid"),
            {"cid": str(conv_id)},
        )
        result = row.fetchone()
        if result is None:
            return None, None
        summary = result[0]
        metadata = result[1] or {}
        up_to = metadata.get("up_to_message_id") if isinstance(metadata, dict) else None
        return summary, up_to
    except Exception as e:
        logger.warning("memory_service: failed to read context for conv %s: %s", conv_id, e)
        return None, None


async def _write_context(db: AsyncSession, conv_id: int, summary: str, up_to_message_id: int) -> None:
    """Upsert summary into saarthi_conversation_context."""
    try:
        import json as _json
        await db.execute(
            text("""
                INSERT INTO saarthi_conversation_context (conversation_id, summary, metadata, updated_at)
                VALUES (:cid, :summary, CAST(:meta AS jsonb), now())
                ON CONFLICT (conversation_id) DO UPDATE
                  SET summary = EXCLUDED.summary,
                      metadata = EXCLUDED.metadata,
                      updated_at = now()
            """),
            {
                "cid": str(conv_id),
                "summary": summary,
                "meta": _json.dumps({"up_to_message_id": up_to_message_id}),
            },
        )
        await db.commit()
    except Exception as e:
        logger.warning("memory_service: failed to write context for conv %s: %s", conv_id, e)


async def _summarize_turns(turns: list[dict]) -> str:
    """Call GPT-4o-mini to compress a batch of old turns into one paragraph."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        transcript = "\n".join(
            f"{'Student' if m['role'] == 'user' else 'Saarthi'}: {m['content'][:400]}"
            for m in turns
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize educational chat transcripts. "
                            "Write a single dense paragraph (max 150 words) capturing: "
                            "the topics discussed, key concepts explained, any formulas or "
                            "definitions given, and questions the student asked. "
                            "Write in third person past tense. No bullet points."
                        ),
                    },
                    {"role": "user", "content": transcript},
                ],
                temperature=0,
                max_tokens=250,
            ),
            timeout=20,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("memory_service: summarization failed: %s", e)
        return ""


async def build_context(
    db: AsyncSession,
    conv_id: int,
    raw_history: list[dict],
) -> list[dict]:
    """
    Returns a trimmed context list to pass to the AI:
      [optional summary injection as system msg] + last WORKING_WINDOW messages

    raw_history is the full list sent by the frontend (role/content dicts).
    """
    if len(raw_history) <= WORKING_WINDOW:
        logger.info("memory[conv=%s]: short history (%d turns) — passthrough, no DB read", conv_id, len(raw_history))
        return raw_history

    summary, up_to = await _read_context(db, conv_id)
    recent = raw_history[-WORKING_WINDOW:]

    if summary:
        logger.info(
            "memory[conv=%s]: injecting summary (up_to_id=%s) + last %d verbatim turns (total history=%d)",
            conv_id, up_to, len(recent), len(raw_history),
        )
        context = [
            {"role": "system", "content": f"[Earlier conversation summary]: {summary}"},
            *recent,
        ]
    else:
        logger.info(
            "memory[conv=%s]: no summary yet — using last %d verbatim turns (total history=%d)",
            conv_id, len(recent), len(raw_history),
        )
        context = recent

    return context


async def maybe_update_summary_bg(
    session_factory,
    conv_id: int,
    all_messages_from_db: list,
) -> None:
    """Fire-and-forget variant that opens its own DB session (safe for asyncio.ensure_future)."""
    try:
        async with session_factory() as db:
            await maybe_update_summary(db, conv_id, all_messages_from_db)
    except Exception as e:
        logger.warning("memory_service[bg]: unhandled error for conv %s: %s", conv_id, e)


async def maybe_update_summary(
    db: AsyncSession,
    conv_id: int,
    all_messages_from_db: list,
) -> None:
    """
    Called async AFTER the response is sent — never blocks the user.

    all_messages_from_db: list of ChatMessage ORM objects ordered by created_at ASC.
    Triggers a re-summarization if >= SUMMARIZE_EVERY new messages exist beyond
    the last checkpoint.
    """
    if not all_messages_from_db:
        logger.debug("memory[conv=%s]: no messages in DB, skipping summary update", conv_id)
        return

    _, up_to_id = await _read_context(db, conv_id)
    total = len(all_messages_from_db)

    # Find index of last summarized message
    if up_to_id is not None:
        ids = [m.id for m in all_messages_from_db]
        try:
            last_idx = ids.index(up_to_id)
        except ValueError:
            last_idx = -1
    else:
        last_idx = -1

    new_msgs = all_messages_from_db[last_idx + 1:]

    # Keep WORKING_WINDOW recent turns out of summarization scope
    msgs_to_summarize = new_msgs[:-WORKING_WINDOW] if len(new_msgs) > WORKING_WINDOW else []

    logger.info(
        "memory[conv=%s]: total=%d  new_since_checkpoint=%d  summarizable=%d  threshold=%d  up_to_id=%s",
        conv_id, total, len(new_msgs), len(msgs_to_summarize), SUMMARIZE_EVERY, up_to_id,
    )

    # First-ever summary: trigger as soon as history is long enough to have msgs outside the window
    first_time = up_to_id is None
    if first_time and total >= FIRST_SUMMARY_AT:
        logger.info("memory[conv=%s]: TRIGGER first-ever summary — total=%d >= FIRST_SUMMARY_AT=%d", conv_id, total, FIRST_SUMMARY_AT)
    elif len(msgs_to_summarize) < SUMMARIZE_EVERY:
        logger.info("memory[conv=%s]: SKIP — need %d more turns before next summarization", conv_id, SUMMARIZE_EVERY - len(msgs_to_summarize))
        return

    logger.info("memory[conv=%s]: TRIGGER summarization — compressing %d turns via gpt-4o-mini", conv_id, last_idx + 1 + len(msgs_to_summarize))
    turns = [{"role": m.role, "content": m.content} for m in all_messages_from_db[:last_idx + 1 + len(msgs_to_summarize)]]
    new_summary = await _summarize_turns(turns)

    if new_summary:
        checkpoint_id = msgs_to_summarize[-1].id
        await _write_context(db, conv_id, new_summary, checkpoint_id)
        logger.info(
            "memory[conv=%s]: ✓ summary updated — checkpoint_id=%s  summary_preview='%s...'",
            conv_id, checkpoint_id, new_summary[:80],
        )
    else:
        logger.warning("memory[conv=%s]: summarization returned empty — DB not updated", conv_id)
