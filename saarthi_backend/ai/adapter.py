"""In-process adapter: runs src/ LangGraph and returns the assistant answer for chat."""

import asyncio
import logging
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

# Ensure project root is on path so "import src" works
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.orchestrator.graph import create_graph  # noqa: E402
from src.utils.state import AgentState  # noqa: E402

logger = logging.getLogger(__name__)

_WORKFLOW = create_graph()
AI_REQUEST_TIMEOUT = 120


def _invoke_graph_sync(query: str, messages: list[dict], mind_mode: bool = False) -> dict:
    state: AgentState = {
        "query": query,
        "messages": messages,
        "sub_queries": [],
        "current_expert": None,
        "results": {},
        "mind_mode": mind_mode,
        "next_step": "",
    }
    return dict(_WORKFLOW.invoke(state))


def _extract_answer(final_state: dict) -> str:
    results = final_state.get("results") or {}
    mind_res = results.get("mind_agent")
    if mind_res is not None and hasattr(mind_res, "content"):
        return (mind_res.content or "").strip()
    for key in ("notes_agent", "books_agent", "calculator_agent", "saarthi_agent", "video_agent", "data_analysis_agent"):
        res = results.get(key)
        if res is not None and hasattr(res, "content"):
            content = (res.content or "").strip()
            if content:
                return content
    parts = []
    for key, res in results.items():
        if key.endswith("_trace") or key == "execution_plan":
            continue
        if hasattr(res, "content") and (res.content or "").strip():
            parts.append(f"**{key}:**\n{res.content.strip()}")
    if parts:
        return "\n\n".join(parts)
    return "I couldn't generate a response. Please try again."


async def run_chat(
    query: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
) -> str:
    loop = asyncio.get_running_loop()
    try:
        final_state = await asyncio.wait_for(
            loop.run_in_executor(None, _invoke_graph_sync, query, conversation_history, mind_mode),
            timeout=AI_REQUEST_TIMEOUT,
        )
        return _extract_answer(final_state)
    except asyncio.TimeoutError:
        logger.warning("AI graph timed out after %s seconds", AI_REQUEST_TIMEOUT)
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("AI graph failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


async def run_chat_stream(
    query: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Run the LangGraph pipeline then stream the final answer token-by-token.
    Yields SSE lines: 'data: <chunk>\\n\\n'. Sends 'data: [DONE]\\n\\n' at end.
    Falls back to word-chunked delivery if OpenAI streaming fails.
    """
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        # Run the full graph first to get KB-retrieved context
        loop = asyncio.get_running_loop()
        final_state = await asyncio.wait_for(
            loop.run_in_executor(None, _invoke_graph_sync, query, conversation_history, mind_mode),
            timeout=AI_REQUEST_TIMEOUT,
        )
        kb_answer = _extract_answer(final_state)

        # Stream the answer through OpenAI with retrieved context baked in
        messages_for_stream = [
            {
                "role": "system",
                "content": (
                    "You are Saarthi, an AI tutor for engineering students. "
                    "The knowledge base has retrieved the following answer. "
                    "Present it clearly with proper Markdown formatting. "
                    "Use LaTeX for math ($...$ inline, $$...$$ display). "
                    "Preserve all source citations exactly."
                ),
            },
            *conversation_history[-6:],
            {"role": "assistant", "content": f"[Knowledge base answer]\n{kb_answer}"},
            {"role": "user", "content": f"Present this answer clearly and completely for: {query}"},
        ]

        stream = await client.chat.completions.create(
            model="gpt-4.1",
            messages=messages_for_stream,
            stream=True,
            temperature=0.2,
            max_tokens=2048,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield f"data: {delta.replace(chr(10), '\\n')}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.exception("Streaming failed, using fallback: %s", e)
        try:
            answer = await run_chat(query, conversation_history, mind_mode)
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {chunk.replace(chr(10), '\\n')}\n\n"
                await asyncio.sleep(0.012)
            yield "data: [DONE]\n\n"
        except Exception:
            yield "data: [ERROR] Could not generate response\n\n"
            yield "data: [DONE]\n\n"
