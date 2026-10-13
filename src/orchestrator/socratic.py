"""Socratic default (WBS 3.3.1, spec 4.4): hint first, full solution after 3 stuck turns.

answer_mode (chosen in the UI; the toggle itself is UX-owned):
  auto       default — problem-solving questions get hints; others answered normally
  socratic   hints for problems AND conceptual questions (not definitions / small talk)
  direct     never hint (old behaviour)

A "problem thread" starts at the latest user turn classified as a problem. Every
assistant reply after it counts as one hint. Once SOCRATIC_MAX_HINTS (default 3)
hints were given — or the student asks for the answer — the next reply is the full
solution. Hint/reveal answers are never written to the semantic cache.
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass

from src.orchestrator.classifier import QueryClass, classify
from src.prompts.socratic_pack import HINT_LEVELS, HINT_TEMPLATE, REVEAL_TEMPLATE

_REVEAL = re.compile(
    r"\b(just (tell|give|show) me|show (me )?(the )?(full |complete )?(answer|solution|working)|"
    r"give (me )?the (final )?answer|full solution|complete solution|solve it for me|what('s| is) the answer)\b",
    re.I,
)
_PROBLEM_STATEMENT = re.compile(
    r"\b(how (do|can|would|should) (i|we|you)|solve|calculate|compute|evaluate|determine|derive|prove|"
    r"show that|find (the|all)|work out)\b",
    re.I,
)
_LOOKBACK_TURNS = 10


def max_hints() -> int:
    return max(1, int(os.environ.get("SOCRATIC_MAX_HINTS", "3")))


@dataclass
class SocraticPlan:
    stage: str          # off | hint | reveal
    level: int = 0      # hint level (1..max) when stage == hint
    hints_given: int = 0
    reason: str = ""
    thread_query: str = ""   # the problem statement that opened this thread
    escalated: bool = False  # reveal after max hints => topic is flagged as a weakness (spec 4.4)

    def system_instructions(self) -> str:
        if self.stage == "hint":
            lvl = min(self.level, max(HINT_LEVELS))
            return HINT_TEMPLATE.format(
                level=self.level, max_hints=max_hints(), level_instruction=HINT_LEVELS[lvl]
            )
        if self.stage == "reveal":
            return REVEAL_TEMPLATE.format(hints_given=self.hints_given)
        return ""

    def as_dict(self) -> dict:
        return asdict(self)


def _applies(qc: QueryClass, answer_mode: str) -> bool:
    if answer_mode == "direct":
        return False
    if answer_mode == "socratic":
        return qc.kind in ("problem", "conceptual", "followup")
    return qc.is_problem


def plan_socratic(
    query: str,
    history: list[dict] | None,
    qc: QueryClass | None = None,
    answer_mode: str = "auto",
) -> SocraticPlan:
    answer_mode = (answer_mode or "auto").lower()
    if answer_mode not in ("auto", "socratic", "direct"):
        answer_mode = "auto"
    history = [m for m in (history or []) if m.get("role") in ("user", "assistant")]
    qc = qc or classify(query, history)
    if answer_mode == "direct":
        return SocraticPlan("off", reason="direct mode")

    recent = history[-_LOOKBACK_TURNS:]

    def _starts_problem(text: str) -> bool:
        # Only an explicit problem statement opens a thread; a math-looking attempt
        # ("is it x = 2t + 1?") inside a thread must not reset the hint count.
        c = classify(text)
        return _applies(c, answer_mode) and (bool(_PROBLEM_STATEMENT.search(text)) or c.kind != "problem")

    start = None
    for i in range(len(recent) - 1, -1, -1):
        m = recent[i]
        if m["role"] == "user" and _starts_problem(m.get("content", "")):
            start = i
            break

    is_new = qc.kind != "followup" and _applies(qc, answer_mode) and (
        start is None or bool(_PROBLEM_STATEMENT.search(query)) or qc.kind != "problem"
    )
    if is_new:
        if _REVEAL.search(query):
            return SocraticPlan("reveal", reason="student asked for the full solution")
        return SocraticPlan("hint", level=1, reason=f"new {qc.kind} question", thread_query=query)
    if start is None:
        return SocraticPlan("off", reason="not a problem thread")

    hints_given = sum(1 for m in recent[start + 1:] if m["role"] == "assistant")
    thread_query = recent[start].get("content", "")
    if _REVEAL.search(query):
        return SocraticPlan("reveal", hints_given=hints_given, reason="student asked for the full solution",
                            thread_query=thread_query)
    if hints_given >= max_hints():
        return SocraticPlan("reveal", hints_given=hints_given, reason=f"{hints_given} hints given",
                            thread_query=thread_query, escalated=True)
    return SocraticPlan("hint", level=hints_given + 1, hints_given=hints_given, reason="continuing problem thread",
                        thread_query=thread_query)
