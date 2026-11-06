"""Rewrite short follow-ups into a standalone search query."""
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils.llm import chat_llm

FOLLOWUP_HINTS = (
    "that", "this", "it", "more simply", "simpler", "another example",
    "explain further", "go deeper", "what about", "why", "which lecture",
    "tell me more", "continue",
)


def looks_like_followup(query: str) -> bool:
    q = query.lower().strip()
    if len(q.split()) <= 14:
        return any(h in q for h in FOLLOWUP_HINTS)
    return False


def rewrite_followup(query: str, history: list[dict], summary: str | None = None) -> str:
    if not looks_like_followup(query):
        return query
    tail = history[-10:] if history else []  # last 5 exchanges (spec 4.5)
    transcript = "\n".join(
        f"{m.get('role')}: {str(m.get('content', ''))[:400]}" for m in tail
    )
    try:
        llm = chat_llm(fast=True, temperature=0)
        out = llm.invoke([
            SystemMessage(content=(
                "Rewrite the student's latest message as a standalone question "
                "a search engine could use. Keep the topic and any formula names. "
                "Output ONLY the rewritten question."
            )),
            HumanMessage(content=(
                f"Summary: {summary or '(none)'}\n\n"
                f"Recent chat:\n{transcript}\n\n"
                f"Latest: {query}"
            )),
        ])
        rewritten = (out.content or query).strip()
        return rewritten or query
    except Exception:
        return query
