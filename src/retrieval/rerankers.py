"""Optional GPU legs (WBS 3.1.1–3.1.2). Both are OFF unless enabled AND installed:

  RETRIEVAL_COLBERT=1   needs `ragatouille` (+ torch). Model: COLBERT_MODEL
  RETRIEVAL_RERANK=1    needs `sentence-transformers`. Model: RERANK_MODEL

They only reorder a candidate list already restricted to one index folder, so
they cannot change corpus isolation. Missing packages => leg reports "skipped".
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_models: dict[str, object] = {}
_unavailable: set[str] = set()


def _enabled(flag: str) -> bool:
    return os.environ.get(flag, "").strip().lower() in ("1", "true", "yes", "on")


def _get(name: str, factory):
    with _lock:
        if name in _unavailable:
            return None
        if name in _models:
            return _models[name]
    try:
        model = factory()
    except Exception as e:  # ImportError, no GPU, download failure
        logger.warning("Retrieval leg '%s' unavailable: %s", name, e)
        with _lock:
            _unavailable.add(name)
        return None
    with _lock:
        _models[name] = model
    return model


def colbert_order(query: str, texts: list[str]) -> tuple[list[int] | None, str]:
    """Indices of `texts` in ColBERT relevance order, or None if the leg is off."""
    if not _enabled("RETRIEVAL_COLBERT"):
        return None, "off"

    def _load():
        from ragatouille import RAGPretrainedModel
        return RAGPretrainedModel.from_pretrained(os.environ.get("COLBERT_MODEL", "colbert-ir/colbertv2.0"))

    model = _get("colbert", _load)
    if model is None:
        return None, "skipped (ragatouille/torch not available)"
    try:
        ranked = model.rerank(query=query, documents=texts, k=len(texts))
        pos = {t: i for i, t in enumerate(texts)}
        return [pos[r["content"]] for r in ranked if r.get("content") in pos], "ok"
    except Exception as e:
        logger.warning("ColBERT rerank failed: %s", e)
        return None, f"error: {e}"


def cross_encoder_order(query: str, texts: list[str]) -> tuple[list[int] | None, str]:
    if not _enabled("RETRIEVAL_RERANK"):
        return None, "off"

    def _load():
        from sentence_transformers import CrossEncoder
        return CrossEncoder(os.environ.get("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))

    model = _get("rerank", _load)
    if model is None:
        return None, "skipped (sentence-transformers not available)"
    try:
        scores = model.predict([(query, t) for t in texts])
        return sorted(range(len(texts)), key=lambda i: float(scores[i]), reverse=True), "ok"
    except Exception as e:
        logger.warning("Cross-encoder rerank failed: %s", e)
        return None, f"error: {e}"
