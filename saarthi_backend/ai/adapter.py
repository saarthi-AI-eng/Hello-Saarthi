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


import re as _re

_ARTIFACT_PATTERNS = [
    # Internal kb labels
    _re.compile(r'\[Knowledge\s+[Bb]ase\s+[Aa]nswer\]', _re.IGNORECASE),
    # "While the specific term X was not found in the provided knowledge base..."
    _re.compile(r'While the specific term[^.]*?(?:knowledge base|provided)[^.]*?\.', _re.IGNORECASE),
    # "X was not found in the knowledge base / provided excerpts / context"
    _re.compile(r"['\"]?\w[\w\s'\"-]{0,60}['\"]?\s+(?:was|were|is|are)\s+not\s+(?:found|mentioned|discussed|present|available)\s+in\s+(?:the\s+)?(?:provided\s+)?(?:knowledge base|context|excerpts?|notes?|books?)[^.]*\.", _re.IGNORECASE),
    # "I do not have this information in my notes"
    _re.compile(r"I\s+do\s+not\s+have\s+this\s+information\s+in\s+my\s+(?:notes|knowledge base|context)[^.]*\.", _re.IGNORECASE),
    # "No relevant information found in this knowledge base"
    _re.compile(r"No\s+relevant\s+information\s+(?:was\s+)?found\s+in\s+(?:this\s+)?(?:the\s+)?knowledge\s+base[^.]*\.", _re.IGNORECASE),
    # "Sources:" section — everything from Sources: to end or next heading
    _re.compile(r'^Sources?:\s*\n(?:.*\n)*?(?=\n#|\Z)', _re.MULTILINE | _re.IGNORECASE),
    # "References:" section
    _re.compile(r'^References?:\s*\n(?:.*\n)*?(?=\n#|\Z)', _re.MULTILINE | _re.IGNORECASE),
    # Inline numbered citations [1], [2], [1,2] etc.
    _re.compile(r'\[\d+(?:,\s*\d+)*\]'),
    # "[Source: ...]" labels
    _re.compile(r'\[Source:\s*[^\]]+\]', _re.IGNORECASE),
    # Trailing --- separators
    _re.compile(r'\n---+\s*$', _re.MULTILINE),
    _re.compile(r'^---+\s*\n', _re.MULTILINE),
]


def _clean_response(text: str) -> str:
    """Strip all internal pipeline artifacts before sending to the student."""
    out = text
    for pattern in _ARTIFACT_PATTERNS:
        out = pattern.sub('', out)
    # Collapse 3+ newlines to 2
    out = _re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()


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
        return _clean_response(_extract_answer(final_state))
    except asyncio.TimeoutError:
        logger.warning("AI graph timed out after %s seconds", AI_REQUEST_TIMEOUT)
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("AI graph failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


async def run_document_chat(
    enriched_prompt: str,
    conversation_history: list[dict],
) -> str:
    """Direct OpenAI call for document-grounded Q&A.

    Bypasses the LangGraph pipeline entirely so the agent knowledge bases
    (HMA corpus) never interfere with course-specific document answers.
    """
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Saarthi, a friendly AI tutor helping a student understand a course document.\n"
                    "The user's prompt contains excerpts extracted from that document.\n"
                    "Answer using ONLY those excerpts — do not draw on outside knowledge.\n\n"
                    "FORMAT RULES (follow exactly):\n"
                    "- Break your answer into 2-4 short sections, each starting with ## Section Title\n"
                    "- Each section must be 2-4 sentences max — simple, plain language, no jargon\n"
                    "- After each section add a blank line then exactly this line: CHECKPOINT\n"
                    "- Use bullet points sparingly (max 3 bullets per section)\n"
                    "- Use $...$ for inline math, $$...$$ for display math\n"
                    "- End the whole answer with: FOLLOWUPS: question1 | question2 | question3\n"
                    "  (3 short follow-up questions the student might want to ask next)\n"
                    "- Do NOT add any text after the FOLLOWUPS line"
                ),
            },
            *conversation_history[-6:],
            {"role": "user", "content": enriched_prompt},
        ]
        response = await asyncio.wait_for(
            AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "")).chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        return _clean_response((response.choices[0].message.content or "").strip())
    except asyncio.TimeoutError:
        logger.warning("Document chat timed out")
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("Document chat failed: %s", e)
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
        kb_answer = _clean_response(_extract_answer(final_state))

        # Stream the answer through OpenAI with retrieved context baked in
        messages_for_stream = [
            {
                "role": "system",
                "content": (
                    "You are Saarthi, a friendly AI tutor for students. "
                    "Present the answer below clearly using Markdown. "
                    "Use $...$ for inline math and $$...$$ for display math. "
                    "Do NOT mention knowledge bases, sources, citations, or where information came from. "
                    "Do NOT say things like 'not found in knowledge base' or 'based on the provided context'. "
                    "Just answer naturally as a tutor would."
                ),
            },
            *conversation_history[-6:],
            {"role": "assistant", "content": kb_answer},
            {"role": "user", "content": f"Present this answer clearly for: {query}"},
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
