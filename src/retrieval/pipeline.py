"""search_index(): the hybrid search used by src.tools.retrieve for one index folder."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from src.retrieval import rerankers, store
from src.retrieval.types import Hit

logger = logging.getLogger(__name__)

RRF_K = 60
HOP_CAP = 2          # max neighbour chunks added by expand_via_graph
_POOL_MIN = 20       # candidates pulled from each leg before fusion (spec: k = 20)
_RERANK_POOL = 30    # fused candidates re-scored by the GPU legs (spec: top 30)


def _dense(idx: store.LoadedIndex, query: str, n: int) -> list[int]:
    vs = idx.vectorstore
    if vs is None:
        return []
    import numpy as np

    vec = vs._embed_query(query) if hasattr(vs, "_embed_query") else vs.embedding_function.embed_query(query)
    q = np.asarray([vec], dtype="float32")
    if q.shape[1] != vs.index.d:
        raise ValueError(f"query dim {q.shape[1]} != index dim {vs.index.d} (EMBEDDING_MODEL changed; re-index)")
    _, rows = vs.index.search(q, min(n, vs.index.ntotal))
    pos = {doc_id: i for i, doc_id in enumerate(idx.ids)}
    out = []
    for r in rows[0]:
        if r < 0:
            continue
        doc_id = str(vs.index_to_docstore_id.get(int(r)))
        if doc_id in pos:
            out.append(pos[doc_id])
    return out


def _rrf(rankings: dict[str, list[int]]) -> list[tuple[int, float, str]]:
    scores: dict[int, float] = {}
    legs: dict[int, list[str]] = {}
    for leg, ranking in rankings.items():
        for rank, i in enumerate(ranking):
            scores[i] = scores.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
            legs.setdefault(i, []).append(leg)
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(i, s, "+".join(legs[i])) for i, s in fused]


def _neighbours(idx: store.LoadedIndex, i: int) -> list[int]:
    md = idx.metadatas[i]
    owner = ("material_id", md.get("material_id")) if md.get("material_id") is not None else ("video_id", md.get("video_id"))
    ci = md.get("chunk_index")
    if owner[1] is None or ci is None:
        return []
    out = []
    for j, other in enumerate(idx.metadatas):
        if other.get(owner[0]) == owner[1] and other.get("chunk_index") in (ci - 1, ci + 1):
            out.append(j)
    return out


def search_index(
    query: str,
    index_dir: Path,
    *,
    content_type: str,
    top_k: int = 5,
    expand_via_graph: bool | None = None,
    boost_terms: list[str] | None = None,
) -> tuple[list[Hit], dict]:
    trace: dict = {"index": str(index_dir), "legs": {}}
    idx = store.load(Path(index_dir))
    if idx is None or not idx.texts:
        trace["legs"]["load"] = "empty"
        return [], trace

    # Spec 4.2: dense k = 20 and BM25 k = 20, RRF, then rerank the fused top 30.
    pool = max(top_k * 4, _POOL_MIN)
    legs = {l.strip() for l in os.environ.get("RETRIEVAL_LEGS", "dense,bm25").split(",") if l.strip()}
    rankings: dict[str, list[int]] = {}
    if "dense" in legs:
        try:
            rankings["dense"] = _dense(idx, query, pool)
            trace["legs"]["dense"] = len(rankings["dense"])
        except Exception as e:
            trace["legs"]["dense"] = f"error: {e}"
            logger.warning("Dense leg failed for %s: %s", index_dir, e)
    if "bm25" in legs:
        try:
            rankings["bm25"] = [i for i, _ in idx.bm25.top(query, pool)]
            trace["legs"]["bm25"] = len(rankings["bm25"])
        except Exception as e:
            trace["legs"]["bm25"] = f"error: {e}"

    fused = _rrf({k: v for k, v in rankings.items() if v})
    if not fused:
        return [], trace

    # Weak-topic boost: reorder only, never filter (an in-scope hit is never dropped).
    terms = [t.lower() for t in (boost_terms or []) if t and len(t) > 2]
    if terms:
        bonus = 0.5 / (RRF_K + 1)
        fused = sorted(
            ((i, s + (bonus if any(t in idx.texts[i].lower() for t in terms) else 0.0), via) for i, s, via in fused),
            key=lambda x: x[1],
            reverse=True,
        )
        trace["boost_terms"] = terms

    # Optional GPU legs reorder the fused candidate pool.
    candidates = fused[: max(pool, _RERANK_POOL)]
    texts = [idx.texts[i] for i, _, _ in candidates]
    for name, fn in (("colbert", rerankers.colbert_order), ("rerank", rerankers.cross_encoder_order)):
        order, status = fn(query, texts)
        trace["legs"][name] = status
        if order:
            candidates = [candidates[j] for j in order] + [c for k, c in enumerate(candidates) if k not in set(order)]
            candidates = [(i, s, f"{via}+{name}") for i, s, via in candidates]
            texts = [idx.texts[i] for i, _, _ in candidates]

    top = candidates[:top_k]
    if expand_via_graph is None:
        expand_via_graph = os.environ.get("RETRIEVAL_EXPAND", "").lower() in ("1", "true", "yes")
    if expand_via_graph and top:
        seen = {i for i, _, _ in top}
        added = 0
        for i, s, _ in list(top):
            for j in _neighbours(idx, i):
                if j not in seen and added < HOP_CAP:
                    top.append((j, s * 0.5, "hop"))
                    seen.add(j)
                    added += 1
        trace["hops"] = added

    hits = [
        Hit(
            source_id=idx.ids[i],
            text=idx.texts[i],
            content_type=idx.metadatas[i].get("content_type") or content_type,
            metadata=idx.metadatas[i],
            score=round(s, 6),
            via=via,
        )
        for i, s, via in top
    ]
    return hits, trace
