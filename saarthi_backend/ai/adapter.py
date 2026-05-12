"""In-process adapter: runs src/ LangGraph and returns the assistant answer for chat."""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on path so "import src" works
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.orchestrator.graph import create_graph  # noqa: E402
from src.utils.state import AgentState  # noqa: E402

logger = logging.getLogger(__name__)

# Compile the LangGraph workflow once at module load and reuse (topology is static).
_WORKFLOW = create_graph()

# Max time for a single AI request (seconds)
AI_REQUEST_TIMEOUT = 120


def _invoke_graph_sync(query: str, messages: list[dict], mind_mode: bool = False) -> dict:
    """Run the compiled graph synchronously. Called from thread pool."""
    state: AgentState = {
        "query": query,
        "messages": messages,
        "sub_queries": [],
        "current_expert": None,
        "results": {},
        "mind_mode": mind_mode,
        "next_step": "",
    }
    final_state = _WORKFLOW.invoke(state)
    return dict(final_state)


def _extract_answer(final_state: dict) -> str:
    """Get the assistant content from the final graph state."""
    results = final_state.get("results") or {}
    # Mind path: synthesized answer is in mind_agent
    mind_res = results.get("mind_agent")
    if mind_res is not None and hasattr(mind_res, "content"):
        return (mind_res.content or "").strip()
    # Single or multi-expert path — collect all agent results in priority order
    for key in (
        "notes_agent", "books_agent", "calculator_agent",
        "saarthi_agent", "video_agent", "data_analysis_agent",
    ):
        res = results.get(key)
        if res is not None and hasattr(res, "content"):
            content = (res.content or "").strip()
            if content:
                return content
    # Multi-agent: concatenate all results that have content
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
    """
    Run the src/ AI graph and return the assistant answer.
    conversation_history: list of {"role": "user"|"assistant", "content": str}.
    """
    messages = conversation_history  # graph expects list of dicts
    loop = asyncio.get_running_loop()
    try:
        final_state = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                _invoke_graph_sync,
                query,
                messages,
                mind_mode,
            ),
            timeout=AI_REQUEST_TIMEOUT,
        )
        return _extract_answer(final_state)
    except asyncio.TimeoutError:
        logger.warning("AI graph run timed out after %s seconds", AI_REQUEST_TIMEOUT)
        return "The request took too long. Please try again with a shorter question or try again later."
    except Exception as e:
        logger.exception("AI graph run failed: %s", e)
        return "Something went wrong while generating a response. Please try again later."
