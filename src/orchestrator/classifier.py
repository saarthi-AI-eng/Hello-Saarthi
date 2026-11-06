"""Query classifier v0 (WBS 3.2.1 / B2): decide how much model a question deserves.

    kind        smalltalk | definition | conceptual | problem | followup
    complexity  simple | complex
    tier        1 (small/local) or 2 (full/cloud) — Tier 0 (cache) is tried
                before this by the policy, independent of the class
    cacheable   whether the answer can be reused for a near-identical question

Heuristic by default ("a prompt or tiny classifier is enough to start").
CLASSIFIER_MODE=llm asks the Tier 1 model for simple/complex and falls back to
the heuristic on any error. Target: trivial questions never hit the slow path twice.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import asdict, dataclass

from src.orchestrator.followup import looks_like_followup

logger = logging.getLogger(__name__)

_SMALLTALK = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|ok|okay|good (morning|evening|night)|bye)\b[\s!.?]*$", re.I)
_DEFINITION = re.compile(
    r"^\s*(what\s+(is|are|does)|define|definition of|meaning of|full form of|what's|whats|who (is|was))\b", re.I
)
_PROBLEM = re.compile(
    r"\b(how (do|can|would|should) (i|we|you) (solve|find|compute|calculate|derive|prove|determine)|"
    r"solve|calculate|compute|evaluate|determine|derive|prove|show that|find the|find all|"
    r"work out|numerical|step[- ]by[- ]step)\b",
    re.I,
)
_COMPLEX = re.compile(
    r"\b(compare|difference between|differences|contrast|why|trade-?off|relationship between|"
    r"in detail|explain .* and |pros and cons|advantages and disadvantages|design|analy[sz]e)\b",
    re.I,
)
_MATHY = re.compile(r"(\d+\s*[a-z]*\s*[=+\-*/^]|[=^]\s*\d|\bx\(t\)|\bh\(t\)|\bx\[n\]|\bH\(s\)|\bz\^)", re.I)


@dataclass
class QueryClass:
    kind: str
    complexity: str
    tier: int
    cacheable: bool
    is_problem: bool
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


def _heuristic(query: str, history: list[dict] | None) -> QueryClass:
    q = (query or "").strip()
    words = len(q.split())
    if _SMALLTALK.match(q):
        return QueryClass("smalltalk", "simple", 1, False, False, "greeting / small talk")
    if history and looks_like_followup(q):
        complex_ = bool(_COMPLEX.search(q))
        return QueryClass("followup", "complex" if complex_ else "simple", 2 if complex_ else 1,
                          False, bool(_PROBLEM.search(q)), "depends on chat history")
    if _PROBLEM.search(q) or (_MATHY.search(q) and words > 4):
        return QueryClass("problem", "complex", 2, True, True, "problem-solving / derivation")
    if _DEFINITION.match(q) and words <= 12 and not _COMPLEX.search(q):
        return QueryClass("definition", "simple", 1, True, False, "short definition lookup")
    if _COMPLEX.search(q) or words > 25:
        return QueryClass("conceptual", "complex", 2, True, False, "multi-part / comparative explanation")
    if words <= 12:
        return QueryClass("conceptual", "simple", 1, True, False, "short conceptual question")
    return QueryClass("conceptual", "complex", 2, True, False, "long conceptual question")


def _llm_complexity(query: str) -> str | None:
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from src.utils.llm import chat_llm

        out = chat_llm(fast=True, temperature=0, max_tokens=4).invoke([
            SystemMessage(content=(
                "Classify the student's question. Reply with exactly one word: "
                "SIMPLE (vocabulary/definition/one-fact lookup) or COMPLEX "
                "(multi-step reasoning, derivation, comparison, problem solving)."
            )),
            HumanMessage(content=query[:800]),
        ])
        word = (out.content or "").strip().upper()
        if word.startswith("SIMPLE"):
            return "simple"
        if word.startswith("COMPLEX"):
            return "complex"
    except Exception as e:
        logger.info("LLM classifier unavailable (%s); using heuristic", e)
    return None


def classify(query: str, history: list[dict] | None = None) -> QueryClass:
    qc = _heuristic(query, history)
    if os.environ.get("CLASSIFIER_MODE", "heuristic").lower() == "llm" and qc.kind not in ("smalltalk", "followup"):
        verdict = _llm_complexity(query)
        if verdict and verdict != qc.complexity:
            qc.complexity = verdict
            qc.tier = 2 if verdict == "complex" else 1
            qc.reason += f" (llm: {verdict})"
    return qc
