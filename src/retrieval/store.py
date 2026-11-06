"""Per-folder cache of the FAISS store + BM25 index.

Loading a FAISS folder and tokenising every chunk on each question is the slowest
part of a CPU demo. Both are cached and rebuilt only when index.faiss / index.pkl
change on disk (re-index, delete) or the embedding model changes.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from src.retrieval.bm25 import BM25

logger = logging.getLogger(__name__)


@dataclass
class LoadedIndex:
    key: tuple
    ids: list[str]
    texts: list[str]
    metadatas: list[dict]
    bm25: BM25
    vectorstore: object | None   # None when the FAISS folder can't be loaded


_lock = threading.Lock()
_cache: dict[str, LoadedIndex] = {}


def _fingerprint(index_dir: Path, model: str) -> tuple:
    parts = []
    for name in ("index.faiss", "index.pkl"):
        p = index_dir / name
        st = p.stat()
        parts.append((st.st_mtime_ns, st.st_size))
    return (model, *parts)


def load(index_dir: Path) -> LoadedIndex | None:
    if not (index_dir / "index.faiss").exists() or not (index_dir / "index.pkl").exists():
        return None
    from src.utils.llm import embedding_model_name

    try:
        key = _fingerprint(index_dir, embedding_model_name())
    except OSError:
        return None
    cache_key = str(index_dir.resolve())
    with _lock:
        hit = _cache.get(cache_key)
        if hit and hit.key == key:
            return hit

    from langchain_community.vectorstores import FAISS
    from src.utils.llm import embeddings

    vs = None
    try:
        vs = FAISS.load_local(str(index_dir), embeddings(), allow_dangerous_deserialization=True)
        items = list(vs.docstore._dict.items())
    except Exception as e:
        logger.warning("FAISS load failed for %s (%s); BM25 only", index_dir, e)
        try:
            import pickle
            with open(index_dir / "index.pkl", "rb") as f:
                docstore, _ = pickle.load(f)
            items = list(docstore._dict.items())
        except Exception as e2:
            logger.warning("Docstore unreadable for %s: %s", index_dir, e2)
            return None

    ids = [str(i) for i, _ in items]
    texts = [d.page_content or "" for _, d in items]
    metadatas = [dict(d.metadata or {}) for _, d in items]
    loaded = LoadedIndex(key=key, ids=ids, texts=texts, metadatas=metadatas, bm25=BM25(texts), vectorstore=vs)
    with _lock:
        _cache[cache_key] = loaded
    return loaded
