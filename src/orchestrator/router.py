"""Route the user query to experts.

GPT-class models honour json_schema. Ollama/Gemma often return DECOMPOSE/ROUTE
text instead. We parse that and never crash the tutor on a schema miss.
"""
from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils.llm import chat_llm
from src.prompts.loader import get_prompt
from src.tools.kb_ops import get_expert_description
from src.schemas.models import RouterOutput, ExpertName, SubQuery
import logging
import os
import json
import re

logger = logging.getLogger(__name__)

_VALID = {e.value for e in ExpertName}

_DATA_HINTS = ("csv", "dataset", "spreadsheet", "pandas", "dataframe", "column analysis", "plot the")
_CALC_HINTS = ("compute", "calculate", "evaluate the integral", "numeric value")
_VIDEO_HINTS = ("timestamp", "in the lecture video", "at minute")


def _heuristic_expert(query: str) -> str | None:
    q = query.lower()
    if any(h in q for h in _DATA_HINTS):
        return "data_analysis_agent"
    if any(h in q for h in _VIDEO_HINTS):
        return "video_agent"
    # DSP / theory questions must never go to the CSV agent (Ollama often
    # emits data_analysis_agent and then the tutor times out after 2 minutes).
    if any(h in q for h in ("fourier", "laplace", "nyquist", "roc", "sampling", "transform", "euler", "de moivre", "convolution", "filter")):
        return "books_agent"
    return None


def _sanitize(query: str, expert: str) -> str:
    if expert == "data_analysis_agent" and not any(h in query.lower() for h in _DATA_HINTS):
        return "books_agent"
    # saarthi_agent has no knowledge base: a course-theory question sent there gets an
    # uncited answer ("every answer cites a real chunk", B1). Prefer the KB agent.
    if expert == "saarthi_agent" and _heuristic_expert(query) in ("books_agent", "video_agent"):
        return _heuristic_expert(query)
    if expert == "web_agent":
        from src.orchestrator.graph import web_allowed
        if not web_allowed():
            return "books_agent"
    return expert if expert in _VALID else "books_agent"


def _fallback(query: str, expert: str = "books_agent") -> RouterOutput:
    guessed = _heuristic_expert(query)
    expert = _sanitize(query, guessed or expert)
    return RouterOutput(sub_queries=[SubQuery(query=query, expert=ExpertName(expert))])


def _from_blob(query: str, blob) -> RouterOutput | None:
    if blob is None:
        return None
    if isinstance(blob, RouterOutput):
        return blob
    if hasattr(blob, "model_dump"):
        blob = blob.model_dump()
    if isinstance(blob, str):
        text = blob.strip()
        try:
            blob = json.loads(text)
        except Exception:
            experts = re.findall(
                r"(notes_agent|books_agent|calculator_agent|saarthi_agent|"
                r"video_agent|data_analysis_agent|web_agent)",
                text,
            )
            return _fallback(query, experts[0] if experts else "books_agent")
    if not isinstance(blob, dict):
        return None
    if blob.get("sub_queries"):
        try:
            return RouterOutput.model_validate(blob)
        except Exception:
            pass
    route = blob.get("ROUTE") or blob.get("route") or "books_agent"
    decomp = blob.get("DECOMPOSE") or blob.get("decompose") or [query]
    if isinstance(route, list):
        route = route[0] if route else "books_agent"
    if isinstance(decomp, str):
        decomp = [decomp]
    if isinstance(route, str) and route not in _VALID:
        m = re.search(
            r"(notes_agent|books_agent|calculator_agent|saarthi_agent|"
            r"video_agent|data_analysis_agent|web_agent)",
            route,
        )
        route = m.group(1) if m else "books_agent"
    return _fallback(decomp[0] if decomp else query, str(route))


def decompose_and_route(query: str, messages: List[Dict[str, Any]] = []) -> RouterOutput:
    # Cap output: a 1B model can loop on the JSON schema until the provider limit
    # (observed 40,960 tokens / ~4 min on CPU) before the fallback kicks in.
    llm = chat_llm(fast=True, temperature=0, max_tokens=int(os.environ.get("ROUTER_MAX_TOKENS", "400")))
    expert_info = []
    for expert in ExpertName:
        desc = get_expert_description(expert.value)
        expert_info.append(f"- {expert.value}: {desc}")

    system_prompt = get_prompt("orchestrator_system", expert_descriptions="\n".join(expert_info))
    llm_messages = [SystemMessage(content=system_prompt)]
    for msg in messages[:-1]:
        if msg["role"] == "user":
            llm_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            llm_messages.append(SystemMessage(content=f"Assistant: {msg['content']}"))
    llm_messages.append(HumanMessage(content=query))

    try:
        structured_llm = llm.with_structured_output(RouterOutput, method="json_schema", strict=True)
        parsed = _from_blob(query, structured_llm.invoke(llm_messages))
        if parsed and parsed.sub_queries:
            sq = parsed.sub_queries[0]
            raw_e = sq.expert.value if hasattr(sq.expert, "value") else str(sq.expert)
            sq.expert = ExpertName(_sanitize(query, raw_e))
            return parsed
    except Exception as e:
        logger.warning("Structured routing failed (%s); falling back", e)

    try:
        raw = llm.invoke(llm_messages)
        content = raw.content if hasattr(raw, "content") else str(raw)
        parsed = _from_blob(query, content)
        if parsed and parsed.sub_queries:
            sq = parsed.sub_queries[0]
            raw_e = sq.expert.value if hasattr(sq.expert, "value") else str(sq.expert)
            sq.expert = ExpertName(_sanitize(query, raw_e))
            return parsed
    except Exception as e:
        logger.warning("Raw routing failed (%s)", e)

    logger.warning("Using books_agent fallback for: %s", query)
    return _fallback(query)
