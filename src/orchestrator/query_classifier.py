"""Query classifier (WBS 3.2.1, spec §4.1): every query is classified before retrieval
or any LLM call.

    Tier 0  the query matches a stored, previously answered query in the same scope
            (semantic cache, cosine >= 0.95 + lexical guard)  -> cached answer, NO LLM call
    Tier 1  simple / definitional (single concept, vocabulary, factual recall)
    Tier 2  complex / reasoning (multi-step problems, code debugging, analysis)

One query embedding is computed and shared by the Tier 0 check and the learned
Tier 1/2 model (logistic regression on [embedding ‖ cue features], trained by
eval/classifier/train_classifier.py, weights in models/tier_classifier.json).
If the embedding service or the weights are unavailable (or were trained with a
different EMBEDDING_MODEL) the rule-based classifier decides Tier 1/2.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.orchestrator.classifier import QueryClass, classify

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).with_name("models") / "tier_classifier.json"
_lock = threading.Lock()
_model: dict | None = None
_model_mtime: float | None = None


def _load_model() -> dict | None:
    global _model, _model_mtime
    try:
        mtime = MODEL_PATH.stat().st_mtime
    except OSError:
        return None
    with _lock:
        if _model is None or mtime != _model_mtime:
            try:
                m = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
                m["_w"] = np.asarray(m["coef"], dtype="float32")
                _model, _model_mtime = m, mtime
            except Exception as e:
                logger.warning("tier classifier weights unreadable: %s", e)
                return None
        return _model


@dataclass
class TierDecision:
    tier: int                       # 0, 1 or 2 (before budget / caps)
    source: str                     # cache | model | rules
    qclass: QueryClass              # rule-based kind (definition / problem / ...) for the Socratic policy
    p_complex: float | None = None  # learned probability of Tier 2
    cache_hit: object | None = None # semantic_cache.CacheHit when tier == 0
    embedding: list | None = None   # reused for the cache write-back
    embed_ms: float = 0.0
    classify_ms: float = 0.0        # classification work excluding the shared embedding
    notes: list = field(default_factory=list)


def learned_tier(query: str, embedding) -> tuple[int, float] | None:
    m = _load_model()
    if m is None or embedding is None:
        return None
    from src.utils.llm import embedding_model_name

    if m.get("embedding_model") != embedding_model_name() or len(embedding) != m.get("dim"):
        return None
    from src.orchestrator.tier_features import feature_vector

    x = feature_vector(query, embedding)
    if x.shape[0] != m["_w"].shape[0]:
        return None
    p = 1.0 / (1.0 + math.exp(-(float(x @ m["_w"]) + float(m["intercept"]))))
    return (2 if p >= float(m.get("threshold", 0.5)) else 1), p


def classify_query(
    query: str,
    history: list[dict] | None = None,
    *,
    cache_scope: str | None = None,
    qclass: QueryClass | None = None,
) -> TierDecision:
    """cache_scope=None means this turn must not be served from the cache
    (follow-up, Socratic turn, planning mode, cache disabled)."""
    qc = qclass or classify(query, history)
    if qc.kind == "smalltalk":
        return TierDecision(1, "rules", qc)

    embedding, embed_ms = None, 0.0
    t = time.perf_counter()
    try:
        from src.cache.semantic_cache import SemanticCache
        embedding, _ = SemanticCache.embed(query)
    except Exception as e:
        logger.info("classifier: embedding unavailable (%s); rules only", e)
    embed_ms = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    if cache_scope and embedding is not None:
        from src.cache.semantic_cache import get_cache
        hit, _ = get_cache().lookup(query, cache_scope, embedding=embedding)
        if hit is not None:
            return TierDecision(0, "cache", qc, cache_hit=hit, embedding=embedding,
                                embed_ms=embed_ms, classify_ms=(time.perf_counter() - t) * 1000)
    if qc.kind == "followup":
        # A follow-up's complexity lives in the history, not the text; keep the rule decision.
        return TierDecision(qc.tier, "rules", qc, embedding=embedding, embed_ms=embed_ms,
                            classify_ms=(time.perf_counter() - t) * 1000)
    learned = learned_tier(query, embedding)
    ms = (time.perf_counter() - t) * 1000
    if learned is not None:
        tier, p = learned
        return TierDecision(tier, "model", qc, p_complex=round(p, 4), embedding=embedding,
                            embed_ms=embed_ms, classify_ms=ms)
    return TierDecision(qc.tier, "rules", qc, embedding=embedding, embed_ms=embed_ms, classify_ms=ms)
