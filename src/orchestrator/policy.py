"""One decision per chat turn: Socratic stage → query classifier (Tier 0/1/2) → model tier.

    Tier 0  stored repeated query in the same scope (semantic cache)  — no LLM call
    Tier 1  small / local model (simple questions; students over their daily cap)
    Tier 2  full / cloud model (complex questions, when configured + within budget)

Top-n chunks put in the prompt follow the tier (spec §4.2): 3 for Tier 1, 8 for Tier 2.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from src.cache.semantic_cache import build_scope, enabled as cache_enabled
from src.orchestrator.classifier import QueryClass, classify
from src.orchestrator.query_classifier import TierDecision, classify_query
from src.orchestrator.socratic import SocraticPlan, plan_socratic
from src.utils import budget
from src.utils.llm import effective_tier, tier2_configured


def top_n(tier: int) -> int:
    if tier >= 2:
        return int(os.environ.get("TOP_N_TIER2", "8"))
    return int(os.environ.get("TOP_N_TIER1", "3"))


@dataclass
class TurnPolicy:
    qclass: QueryClass
    socratic: SocraticPlan
    decision: TierDecision
    tier: int                 # served tier: 0 cache, 1, 2
    tier_reason: str
    cache_scope: str | None   # None => do not read or write the cache this turn
    cap: dict

    @property
    def cache_hit(self):
        return self.decision.cache_hit

    @property
    def embedding(self):
        return self.decision.embedding

    @property
    def top_n(self) -> int:
        return top_n(self.tier)

    def trace(self) -> dict:
        return {
            "class": {"kind": self.qclass.kind, "complexity": self.qclass.complexity},
            "classifier": {
                "requested_tier": self.decision.tier, "source": self.decision.source,
                "p_complex": self.decision.p_complex,
                "classify_ms": round(self.decision.classify_ms, 2), "embed_ms": round(self.decision.embed_ms, 1),
            },
            "socratic": {"stage": self.socratic.stage, "level": self.socratic.level},
            "tier": self.tier,
            "tier_reason": self.tier_reason,
            "cacheable": self.cache_scope is not None,
            "cap": self.cap,
        }


def plan_turn(
    query: str,
    history: list[dict] | None,
    *,
    course_id: int | None = None,
    material_title: str | None = None,
    video_id: int | None = None,
    mode: str = "chat",
    answer_mode: str = "direct",
    user_key: str | None = None,
    role: str | None = None,
) -> TurnPolicy:
    """Blocking (embeds the query once) — call from a worker thread in async code."""
    qc = classify(query, history)
    soc = plan_socratic(query, history, qc, answer_mode)

    cacheable = cache_enabled() and qc.cacheable and soc.stage == "off" and mode != "planning"
    scope = build_scope(course_id=course_id, material_title=material_title, video_id=video_id, mode=mode) if cacheable else None

    decision = classify_query(query, history, cache_scope=scope, qclass=qc)
    cap = budget.user_cap_status(user_key, role)

    if decision.tier == 0:
        return TurnPolicy(qc, soc, decision, 0, "repeated query (semantic cache)", scope, cap)

    wanted = decision.tier
    if wanted == 2 and cap["over"] and (role or "student") == "student":
        return TurnPolicy(qc, soc, decision, 1, f"daily cap reached ({cap['used']}/{cap['cap']} tokens): Tier 1 only", scope, cap)
    tier = effective_tier(wanted)
    if wanted == 2 and tier == 1:
        reason = "complex, Tier 2 not configured" if not tier2_configured() else f"complex, {budget.cloud_allowed()[1]}"
    else:
        reason = f"{'complex' if wanted == 2 else 'simple'} question ({decision.source})"
    return TurnPolicy(qc, soc, decision, tier, reason, scope, cap)
