"""In-process adapter: runs src/ LangGraph and returns the assistant answer for chat."""

import asyncio
import logging
import os
import re as _re
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
    for key in ("notes_agent", "books_agent", "calculator_agent", "saarthi_agent", "video_agent", "data_analysis_agent", "web_agent"):
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
    # "Sources:" / "References:" section — strip from header to end regardless of position
    _re.compile(r'\s*(?:Sources?|References?):\s*\n.*', _re.IGNORECASE | _re.DOTALL),
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


_TUTOR_SYSTEM = (
    "You are Saarthi, a friendly AI tutor for engineering students.\n\n"
    "MATH FORMATTING — this is mandatory, zero exceptions:\n"
    "- Every mathematical symbol, variable, expression, or equation MUST be wrapped in LaTeX delimiters.\n"
    "- Inline (variables, short expressions): $x(t)$, $\\omega$, $X(j\\omega)$, $O(\\log n)$\n"
    "- Display (standalone equations): place on its own line between $$...$$\n"
    "  Example: $$X(j\\omega) = \\int_{-\\infty}^{\\infty} x(t)\\,e^{-j\\omega t}\\,dt$$\n"
    "- NEVER write raw Unicode math like: X(jω), ∫, ∞, β₀, α — always use LaTeX inside $.\n"
    "- NEVER put math expressions inside markdown table cells — tables break math rendering.\n\n"
    "FORMATTING:\n"
    "- Use ## for section headings, **bold** for key terms.\n"
    "- Use numbered lists for steps, bullet lists for properties.\n"
    "- Keep answers focused: 3-5 sections max, no padding.\n\n"
    "TONE:\n"
    "- Never mention 'knowledge base', 'context', 'sources', or 'provided excerpts'.\n"
    "- Never say things like 'based on the information provided' or 'I don't have this in my notes'.\n"
    "- Answer directly like a confident tutor who knows the subject."
)




async def _direct_gpt_call(query: str, conversation_history: list[dict]) -> str:
    """Fallback: single direct GPT-4.1 call when LangGraph returns empty."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        messages = [{"role": "system", "content": _TUTOR_SYSTEM}]
        for m in conversation_history[-8:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": query})
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                temperature=0.4,
                max_tokens=3000,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        return _clean_response((response.choices[0].message.content or "").strip())
    except Exception as e:
        logger.exception("Direct GPT fallback failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


async def run_chat(
    query: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
) -> str:
    # mind_mode uses the full LangGraph multi-agent pipeline
    if mind_mode:
        loop = asyncio.get_running_loop()
        try:
            final_state = await asyncio.wait_for(
                loop.run_in_executor(None, _invoke_graph_sync, query, conversation_history, mind_mode),
                timeout=AI_REQUEST_TIMEOUT,
            )
            return _clean_response(_extract_answer(final_state))
        except asyncio.TimeoutError:
            logger.warning("Mind mode timed out")
            return "The request took too long. Please try a shorter question."
        except Exception as e:
            logger.exception("Mind mode failed: %s", e)
            return "Something went wrong. Please try again."

    # All queries go through LangGraph — router handles intent correctly
    loop = asyncio.get_running_loop()
    try:
        final_state = await asyncio.wait_for(
            loop.run_in_executor(None, _invoke_graph_sync, query, conversation_history, False),
            timeout=AI_REQUEST_TIMEOUT,
        )
        answer = _clean_response(_extract_answer(final_state))
        if answer:
            return answer
        return await _direct_gpt_call(query, conversation_history)
    except asyncio.TimeoutError:
        logger.warning("AI chat timed out")
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("AI chat failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


async def run_video_chat(
    enriched_prompt: str,
    conversation_history: list[dict],
) -> str:
    """Direct OpenAI call for video-transcript-grounded Q&A.

    Clean conversational style — no checkpoints, no follow-up chips.
    Goes progressively deeper when the student asks for more.
    """
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Saarthi, an expert tutor helping a student understand a video lecture.\n"
                    "The user's prompt contains transcript excerpts from that lecture.\n"
                    "Answer using those excerpts as your primary source, but you may add supporting "
                    "context from your own knowledge to make the explanation complete.\n\n"
                    "STYLE:\n"
                    "- Be a teacher, not a summariser. Explain the *why*, not just the *what*.\n"
                    "- When the student says 'tell me more' or 'explain further', go DEEPER — "
                    "don't restate what you already said. Cover the next level of detail.\n"
                    "- Use ## headings to organise long answers into clear sections.\n"
                    "- Use $...$ for inline math, $$...$$ for display math.\n"
                    "- Bullet points for lists, numbered steps for procedures.\n"
                    "- Keep each section focused. No padding, no repetition.\n"
                    "- Do NOT add CHECKPOINT lines or FOLLOWUPS lines."
                ),
            },
            *conversation_history[-8:],
            {"role": "user", "content": enriched_prompt},
        ]
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        return _clean_response((response.choices[0].message.content or "").strip())
    except asyncio.TimeoutError:
        logger.warning("Video chat timed out")
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("Video chat failed: %s", e)
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
                max_tokens=2000,
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
    """True token-by-token streaming via OpenAI stream=True."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        # All queries go through LangGraph — router handles intent correctly
        loop = asyncio.get_running_loop()
        final_state = await asyncio.wait_for(
            loop.run_in_executor(None, _invoke_graph_sync, query, conversation_history, mind_mode),
            timeout=AI_REQUEST_TIMEOUT,
        )
        answer = _clean_response(_extract_answer(final_state))

        if answer:
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {chunk.replace(chr(10), chr(92) + 'n')}\n\n"
                await asyncio.sleep(0.008)
            yield "data: [DONE]\n\n"
            return

        # Graph returned empty — fall back to real OpenAI token streaming
        messages = [{"role": "system", "content": _TUTOR_SYSTEM}]
        for m in conversation_history[-8:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": query})

        stream = await client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.4,
            max_tokens=3000,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield f"data: {delta.replace(chr(10), chr(92) + 'n')}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.exception("Streaming failed: %s", e)
        yield "data: [ERROR] Could not generate response\n\n"
        yield "data: [DONE]\n\n"
