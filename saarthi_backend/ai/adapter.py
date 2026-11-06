"""In-process adapter: runs src/ LangGraph and returns the assistant answer for chat."""
import asyncio
import contextvars
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
from src.utils.llm import async_openai, chat_model_name, effective_tier, reset_tier, set_tier  # noqa: E402
from src.utils import budget  # noqa: E402

logger = logging.getLogger(__name__)

_WORKFLOW = create_graph()
# Local Ollama on CPU is slow (router + expert). 120s used to fire while the
# CSV agent was still looping — routing is fixed; keep headroom for 1B/3B.
AI_REQUEST_TIMEOUT = int(os.environ.get("AI_REQUEST_TIMEOUT", "180"))


def _invoke_graph_sync(
    query: str,
    messages: list[dict],
    mind_mode: bool = False,
    planning: bool = False,
    tier: int | None = None,
    boost_terms: list[str] | None = None,
) -> dict:
    token = set_tier(tier)
    try:
        return _invoke_graph_inner(query, messages, mind_mode, planning, tier, boost_terms)
    finally:
        reset_tier(token)


def _run_graph_in_executor(loop, *args):
    """Run the graph in a worker thread *with* this request's context (model tier,
    usage collector). Returns (future, context) so callers can read context vars
    the graph set (e.g. the retrieval trace) after it finishes."""
    ctx = contextvars.copy_context()
    return loop.run_in_executor(None, ctx.run, _invoke_graph_sync, *args), ctx


def _invoke_graph_inner(query, messages, mind_mode, planning, tier, boost_terms) -> dict:
    state: AgentState = {
        "query": query,
        "messages": messages,
        "sub_queries": [],
        "current_expert": None,
        "results": {},
        "mind_mode": mind_mode,
        "planning": planning,
        "next_step": "",
        "plan": [],
        "retrieved_chunks": [],
        "critic_ok": True,
        "critic_notes": "",
        "boost_terms": list(boost_terms or []),
        "tier": tier,
    }
    return dict(_WORKFLOW.invoke(state))


def _obj_dump(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    import dataclasses
    if dataclasses.is_dataclass(obj):  # retrieve() Chunk — keeps the chunk id for traces / cache
        return dataclasses.asdict(obj)
    return {k: getattr(obj, k) for k in ("id", "source_file", "page_number", "snippet", "number", "source_agent", "sources", "references", "text", "title", "page") if hasattr(obj, k)}


def _cite_item(src, agent: str = "", number: int | None = None) -> dict:
    d = _obj_dump(src)
    return {
        "number": number if number is not None else d.get("number"),
        "agent": agent or d.get("agent") or d.get("source_agent") or "",
        "source_file": d.get("source_file") or d.get("title") or d.get("source") or "",
        "page_number": d.get("page_number") if d.get("page_number") is not None else d.get("page"),
        "snippet": (d.get("snippet") or d.get("text") or "")[:280],
        "chunk_id": d.get("id") or d.get("chunk_id"),
    }


def citations_from_chunks(chunks) -> list[dict]:
    out = []
    for i, c in enumerate(chunks or [], 1):
        item = _cite_item(c, agent=getattr(c, "content_type", "") or "", number=i)
        if item["source_file"] or item["snippet"]:
            out.append(item)
    return out


def citations_from_query(
    query: str,
    course_id: int | None = None,
    material_title: str | None = None,
    video_id: int | None = None,
) -> list[dict]:
    """Last-resort: search indexes so the Sources panel is never empty after a retrieve hit."""
    try:
        from src.tools.retrieve import retrieve
        return citations_from_chunks(
            retrieve(query, course_id=course_id, material_title=material_title, video_id=video_id, k=5)
        )
    except Exception as e:
        logger.warning("citation retrieve failed: %s", e)
        return []


def _extract_citations(final_state: dict) -> dict:
    """Extract citations and react traces from all agent results (objects or dicts)."""
    results = final_state.get("results") or {}
    citations = []
    react_steps = []

    mind_res = results.get("mind_agent")
    mind_d = _obj_dump(mind_res)
    for ref in (mind_d.get("references") or getattr(mind_res, "references", None) or []):
        citations.append(_cite_item(ref))

    for key in ("notes_agent", "books_agent", "video_agent"):
        res = results.get(key)
        if res is None:
            continue
        d = _obj_dump(res)
        for src in (d.get("sources") or getattr(res, "sources", None) or []):
            citations.append(_cite_item(src, agent=key))
        trace = results.get(f"{key}_trace") or []
        for step in trace:
            if isinstance(step, dict):
                react_steps.append({
                    "agent": key,
                    "step": step.get("step"),
                    "thought": step.get("thought", ""),
                    "tools_called": step.get("tools_called", []),
                    "observations": step.get("observations", []),
                })

    for i, c in enumerate(final_state.get("retrieved_chunks") or [], 1):
        citations.append(_cite_item(c, number=i))

    # Drop empties / duplicates
    seen = set()
    uniq = []
    for c in citations:
        key = (c.get("source_file") or "", (c.get("snippet") or "")[:80])
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        if c.get("number") is None:
            c["number"] = len(uniq) + 1
        uniq.append(c)
    return {"citations": uniq, "react_steps": react_steps}


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
    _re.compile(
        r"['\"]?\w[\w\s'\"-]{0,60}['\"]?\s+(?:was|were|is|are)\s+not\s+"
        r"(?:found|mentioned|discussed|present|available)\s+in\s+(?:the\s+)?"
        r"(?:provided\s+)?(?:knowledge base|context|excerpts?|notes?|books?)[^.]*\.",
        _re.IGNORECASE,
    ),
    # "I do not have this information in my notes"
    _re.compile(r"I\s+do\s+not\s+have\s+this\s+information\s+in\s+my\s+(?:notes|knowledge base|context)[^.]*\.", _re.IGNORECASE),
    # "No relevant information found in this knowledge base"
    _re.compile(r"No\s+relevant\s+information\s+(?:was\s+)?found\s+in\s+(?:this\s+)?(?:the\s+)?knowledge\s+base[^.]*\.", _re.IGNORECASE),
    # "Sources:" / "References:" section — strip from header to end regardless of position
    _re.compile(r'\s*(?:Sources?|References?):\s*\n.*', _re.IGNORECASE | _re.DOTALL),
    # "[Source: ...]" labels (keep [1][2] markers — they are student-facing)
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
    out = _re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()


_TUTOR_SYSTEM = (
    "You are Saarthi, a friendly AI tutor for engineering students.\n"
    "Math: every symbol or expression in LaTeX — $x(t)$ inline, $$...$$ for display; "
    "no raw Unicode math (ω, ∫); no math inside tables.\n"
    "Format: ## headings, **bold** key terms, numbered steps.\n"
    "- Teach fully: definition, formula, one example, why it matters.\n"
    "- Aim for 250-500 words on conceptual questions. Two sentences is not enough.\n"
)


def _grounded_system_for_legacy() -> str:
    """System prompt for run_document_chat / run_video_chat (prompt already holds the excerpts)."""
    from src.prompts import tutor
    return tutor.grounded_system(None)


def _record_response_usage(response, model: str) -> None:
    usage = getattr(response, "usage", None)
    tier = effective_tier()
    if usage is not None and getattr(usage, "prompt_tokens", None) is not None:
        budget.record(tier, model, usage.prompt_tokens, usage.completion_tokens or 0)
    else:
        text = (response.choices[0].message.content or "") if getattr(response, "choices", None) else ""
        budget.record(tier, model, 0, budget.estimate_tokens(text), estimated=True)


_TEACH_FULLY = (
    "- Teach fully: definition, formula, one example, why it matters.\n"
    "- Aim for 250-500 words on conceptual questions. Two sentences is not enough.\n"
)


# Spec 4.5: last n = 5 exchanges (10 messages) stay in the prompt context.
MEMORY_MESSAGES = 10
_COMPUTE_EXPERTS = ("calculator_agent", "data_analysis_agent")
from src.orchestrator.classifier import _SMALLTALK  # noqa: E402
_ABOUT_SAARTHI = _re.compile(
    r"\b(who are you|what can you|what do you do|help me with|how (should|do) i (study|prepare)|study plan|"
    r"revision plan|exam tips|how to use)\b",
    _re.I,
)


def is_hint_turn(system_extra: str) -> bool:
    return (system_extra or "").startswith("SOCRATIC MODE")


def tutor_system(system_extra: str = "") -> str:
    """Tutor system prompt; on Socratic hint turns the 'teach fully / 250-500 words'
    rules are dropped (small models otherwise ignore the hint rule and solve)."""
    base = _TUTOR_SYSTEM.replace(_TEACH_FULLY, "") if is_hint_turn(system_extra) else _TUTOR_SYSTEM
    return base + (f"\n\n{system_extra}" if system_extra else "")


def hint_user_message(query: str, reference: str) -> str:
    """User turn for a hint: the solution material is private reference, not something to rewrite."""
    return (
        f"Student's message: {query}\n\n"
        "Reference material for YOU only (use it to give a correct hint; never reveal the full "
        f"solution or the final result):\n{reference or '(none)'}\n\n"
        "Reply with ONLY the hint described in your instructions, then one question for the student."
    )


async def _direct_gpt_call(query: str, conversation_history: list[dict]) -> str:
    """Fallback: single direct GPT-4.1 call when LangGraph returns empty."""
    try:
        client = async_openai()
        messages = [{"role": "system", "content": _TUTOR_SYSTEM}]
        for m in conversation_history[-8:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": query})
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=chat_model_name(),
                messages=messages,
                temperature=0.4,
                max_tokens=3000,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        _record_response_usage(response, chat_model_name())
        return _clean_response((response.choices[0].message.content or "").strip())
    except Exception as e:
        logger.exception("Direct GPT fallback failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


def _ground_final_answer(query: str, final_state: dict, answer: str, n: int = 5) -> str:
    """Non-streaming twin of the stream's reply-mode decision (grounding rule DEC-1)."""
    from src.prompts import tutor
    from src.tools.citations import sources_suffix
    from src.tools.grounding import coverage

    chunks = list(final_state.get("retrieved_chunks") or [])[:n]
    expert = final_state.get("current_expert") or ""
    if chunks and coverage(query, chunks)[0] and answer:
        return answer + sources_suffix(answer, chunks)
    mind = (final_state.get("results") or {}).get("mind_agent")
    if mind is not None and getattr(mind, "references", None) and answer:
        return answer  # Mind mode answers carry numbered references from the RAG agents
    if expert in _COMPUTE_EXPERTS and answer:
        return answer
    if expert == "saarthi_agent" and answer and (_ABOUT_SAARTHI.search(query) or _SMALLTALK.match(query)):
        return answer
    return tutor.not_covered()


async def run_grounded_answer(
    question: str,
    chunks: list,
    conversation_history: list[dict],
    *,
    course_name: str | None = None,
    system_extra: str = "",
) -> str:
    """Course / material / video scoped answer, ONLY from the given chunks (non-streaming)."""
    from src.prompts import tutor
    from src.tools.citations import excerpts_block, sources_suffix

    excerpts = excerpts_block(chunks)
    user = tutor.hint_user(question, excerpts) if is_hint_turn(system_extra) else tutor.grounded_user(question, excerpts)
    history = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in conversation_history[-MEMORY_MESSAGES:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    try:
        response = await asyncio.wait_for(
            async_openai().chat.completions.create(
                model=chat_model_name(),
                messages=[{"role": "system", "content": tutor.grounded_system(course_name, system_extra)},
                          *history, {"role": "user", "content": user}],
                temperature=0.1,
                max_tokens=1500,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        _record_response_usage(response, chat_model_name())
        answer = _clean_response((response.choices[0].message.content or "").strip())
        return answer + sources_suffix(answer, chunks)
    except asyncio.TimeoutError:
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("Grounded answer failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


async def run_chat(
    query: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
) -> str:
    if mind_mode:
        loop = asyncio.get_running_loop()
        try:
            fut, _ = _run_graph_in_executor(loop, query, conversation_history, mind_mode, False, effective_tier())
            final_state = await asyncio.wait_for(fut, timeout=AI_REQUEST_TIMEOUT)
            return _ground_final_answer(query, final_state, _clean_response(_extract_answer(final_state)))
        except asyncio.TimeoutError:
            logger.warning("Mind mode timed out")
            return "The request took too long. Please try a shorter question."
        except Exception as e:
            logger.exception("Mind mode failed: %s", e)
            return "Something went wrong. Please try again."

    # All queries go through LangGraph — router handles intent correctly
    loop = asyncio.get_running_loop()
    try:
        fut, _ = _run_graph_in_executor(loop, query, conversation_history, False, False, effective_tier())
        final_state = await asyncio.wait_for(fut, timeout=AI_REQUEST_TIMEOUT)
        # Grounding rule: no ungrounded "direct GPT" fallback any more.
        return _ground_final_answer(query, final_state, _clean_response(_extract_answer(final_state)))
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
        client = async_openai()
        messages = [
            {
                "role": "system",
                "content": _grounded_system_for_legacy(),
            },
            *conversation_history[-MEMORY_MESSAGES:],
            {"role": "user", "content": enriched_prompt},
        ]
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=chat_model_name(),
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        _record_response_usage(response, chat_model_name())
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
        client = async_openai()
        messages = [
            {
                "role": "system",
                "content": _grounded_system_for_legacy(),
            },
            *conversation_history[-MEMORY_MESSAGES:],
            {"role": "user", "content": enriched_prompt},
        ]
        response = await asyncio.wait_for(
            async_openai().chat.completions.create(
                model=chat_model_name(),
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        _record_response_usage(response, chat_model_name())
        return _clean_response((response.choices[0].message.content or "").strip())
    except asyncio.TimeoutError:
        logger.warning("Document chat timed out")
        return "The request took too long. Please try a shorter question."
    except Exception as e:
        logger.exception("Document chat failed: %s", e)
        return "Something went wrong while generating a response. Please try again."


def _sse_data(text: str) -> str:
    return f"data: {text.replace(chr(10), chr(92) + 'n')}\n\n"


def _sse_status(stage: str, detail: str = "") -> str:
    import json as _json
    return f"event: status\ndata: {_json.dumps({'stage': stage, 'detail': detail})}\n\n"


async def _stream_llm_tokens(messages: list[dict], tier: int | None = None) -> AsyncGenerator[str, None]:
    t = effective_tier(tier)  # resolve once so client and model always match
    model = chat_model_name(tier=t)
    client = async_openai(tier=t)
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=3000,
        stream=True,
    )
    out_chars = 0
    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                out_chars += len(delta)
                yield _sse_data(delta)
    finally:
        prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)
        budget.record(t, model, prompt_chars // 4, out_chars // 4, estimated=True)


async def run_chat_stream(
    query: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
    planning: bool = False,
    *,
    tier: int | None = None,
    system_extra: str = "",
    boost_terms: list[str] | None = None,
    meta_extra: dict | None = None,
    sink: dict | None = None,
    kind: str = "",
    n: int = 3,
    course_name: str | None = None,
) -> AsyncGenerator[str, None]:
    """Status events, then real tokens from the final LLM. Cancelled on disconnect.

    Grounding rule (DEC-1): the final answer is written ONLY from the retrieved excerpts
    (top-n by tier). Without covering excerpts the student gets the NOT_COVERED reply and
    no LLM call is made — except calculator / data-analysis results and small talk.

    tier          model tier for the final answer (graph router/critic stay on Tier 1)
    system_extra  appended to the tutor system prompt (e.g. Socratic hint rules)
    boost_terms   weak topics: reorder retrieval only
    meta_extra    merged into the SSE meta event (e.g. tier / socratic stage for the UI)
    sink          filled with citations / chunk_ids / plan / critic / retrieval for caching + traces
    """
    import json as _json
    try:
        yield _sse_status("routing", "Planning which expert to use")
        loop = asyncio.get_running_loop()
        task, graph_ctx = _run_graph_in_executor(
            loop, query, conversation_history, mind_mode, planning, tier, boost_terms
        )
        while not task.done():
            await asyncio.sleep(0.25)
            yield ": keepalive\n\n"

        final_state = await asyncio.wait_for(task, timeout=AI_REQUEST_TIMEOUT)
        answer = _clean_response(_extract_answer(final_state))
        meta = _extract_citations(final_state)
        meta["plan"] = final_state.get("plan") or []
        meta["critic_ok"] = final_state.get("critic_ok")
        meta["critic_notes"] = final_state.get("critic_notes") or ""
        if meta_extra:
            meta.update(meta_extra)
        if sink is not None:
            from src.tools.retrieve import last_trace
            sink["plan"] = meta["plan"]
            sink["critic_ok"] = meta["critic_ok"]
            sink["chunk_ids"] = [
                (c.get("id") if isinstance(c, dict) else getattr(c, "id", None))
                for c in (final_state.get("retrieved_chunks") or [])
            ]
            sink["retrieval"] = graph_ctx.get(last_trace, [])
            sink["expert"] = final_state.get("current_expert")

        yield _sse_status("generating", "Writing the answer")

        from src.tools.grounding import coverage

        chunks = list(final_state.get("retrieved_chunks") or [])[: max(1, n)]
        expert = final_state.get("current_expert") or ""
        covered = coverage(query, chunks)[0] if chunks else False
        if chunks and covered:
            reply_mode = "grounded"
        elif expert in _COMPUTE_EXPERTS and answer:
            reply_mode = "compute"
        elif kind == "smalltalk" or (expert == "saarthi_agent" and _ABOUT_SAARTHI.search(query)):
            reply_mode = "general"
        else:
            reply_mode = "not_covered"
        if sink is not None:
            sink["covered"] = covered
        async for frame in _emit_reply(
            reply_mode, query, chunks, conversation_history, meta=meta, sink=sink, tier=tier,
            system_extra=system_extra, course_name=course_name, computed=answer,
            critic_ok=final_state.get("critic_ok"),
        ):
            yield frame
    except asyncio.CancelledError:
        logger.info("SSE cancelled (client disconnected)")
        raise
    except Exception as e:
        logger.exception("Streaming failed: %s", e)
        yield "data: [ERROR] Could not generate response\n\n"
        yield "data: [DONE]\n\n"


async def _emit_reply(
    reply_mode: str,
    query: str,
    chunks: list,
    conversation_history: list[dict],
    *,
    meta: dict,
    sink: dict | None = None,
    tier: int | None = None,
    system_extra: str = "",
    course_name: str | None = None,
    computed: str = "",
    critic_ok: bool | None = None,
) -> AsyncGenerator[str, None]:
    """Write the student-facing reply for one of the reply modes and emit meta + [DONE].

    grounded     answer ONLY from the labelled excerpts (hint or full), citations enforced
    compute      present a calculator / data-analysis result
    general      greetings / what-can-you-do (no course facts)
    not_covered  fixed reply, no LLM call (grounding rule DEC-1)
    """
    import json as _json
    from src.prompts import tutor
    from src.safety.guard import SAFE_REFUSAL, leaks_prompt
    from src.tools.citations import excerpts_block, is_cited, sources_suffix
    from src.tools.grounding import confidence

    history_msgs = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in conversation_history[-MEMORY_MESSAGES:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    if reply_mode == "grounded":
        excerpts = excerpts_block(chunks)
        user_msg = tutor.hint_user(query, excerpts) if is_hint_turn(system_extra) else tutor.grounded_user(query, excerpts)
        messages = [{"role": "system", "content": tutor.grounded_system(course_name, system_extra)}, *history_msgs,
                    {"role": "user", "content": user_msg}]
        meta["citations"] = citations_from_chunks(chunks)
    elif reply_mode == "compute":
        messages = [{"role": "system", "content": tutor.COMPUTE_SYSTEM},
                    {"role": "user", "content": f"Question: {query}\n\nComputed result:\n{computed}"}]
        meta["citations"] = []
    elif reply_mode == "general":
        messages = [{"role": "system", "content": tutor.GENERAL_SYSTEM}, *history_msgs,
                    {"role": "user", "content": query}]
        meta["citations"] = []
    else:
        messages = []
        meta["citations"] = []

    out: list[str] = []
    if reply_mode == "not_covered":
        text = tutor.not_covered(course_name)
        out.append(text)
        yield _sse_data(text)
    else:
        async for tok in _stream_llm_tokens(messages, tier=tier):
            out.append(tok[6:].rstrip("\n").replace("\\n", "\n"))
            yield tok
        if reply_mode == "grounded":
            suffix = sources_suffix("".join(out), chunks)
            if suffix:
                out.append(suffix)
                yield _sse_data(suffix)

    full = "".join(out)
    leaked = leaks_prompt(full)
    if leaked:  # output guard (R8): the streamed text is replaced client-side by a notice
        yield _sse_data("\n\n" + SAFE_REFUSAL)
    cited = reply_mode == "grounded" and is_cited(full, chunks)
    conf, reasons = confidence(
        covered=reply_mode != "not_covered",
        cited=cited or reply_mode != "grounded",
        critic_ok=critic_ok,
        n_chunks=len(chunks) if reply_mode == "grounded" else 1,
    )
    if leaked:
        conf, reasons = "low", reasons + ["answer quoted system instructions"]
    meta.update({"confidence": conf, "confidence_reasons": reasons, "reply_mode": reply_mode})
    if sink is not None:
        sink.update({
            "citations": meta["citations"], "reply_mode": reply_mode, "cited": cited,
            "confidence": conf, "confidence_reasons": reasons, "leaked": leaked,
            "chunk_ids": [(c.get("id") if isinstance(c, dict) else getattr(c, "id", None)) for c in chunks]
            if reply_mode == "grounded" else [],
        })
    # Meta BEFORE [DONE]. The React client used to `break` on [DONE] and
    # never paint 📚 Sources.
    yield f"event: meta\ndata: {_json.dumps(meta, default=str)}\n\n"
    yield "data: [DONE]\n\n"


async def stream_scoped_answer(
    query: str,
    grounding,
    conversation_history: list[dict],
    *,
    kind: str = "",
    tier: int | None = None,
    system_extra: str = "",
    course_name: str | None = None,
    meta_extra: dict | None = None,
    sink: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Course / material / video scoped turn: no graph, answer only from `grounding.chunks`."""
    yield _sse_status("generating", "Reading your course materials")
    if kind == "smalltalk":
        reply_mode = "general"
    elif grounding.chunks and grounding.covered:
        reply_mode = "grounded"
    else:
        reply_mode = "not_covered"
    if sink is not None:
        sink["covered"] = grounding.covered
    async for frame in _emit_reply(
        reply_mode, query, grounding.chunks, conversation_history, meta=dict(meta_extra or {}), sink=sink,
        tier=tier, system_extra=system_extra, course_name=course_name,
    ):
        yield frame
