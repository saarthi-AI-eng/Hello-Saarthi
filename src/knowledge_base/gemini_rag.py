"""Answer questions from the fixed Qdrant knowledge base with only a Gemini API key.

The Qdrant collection was embedded with BAAI/bge-m3, a local model. To avoid running
that model, the chunks are embedded ONCE with Gemini and saved locally:

    py -3.13 -m scripts.build_kb_gemini_index

After that, each question costs one Gemini embedding call (to find the closest
chunks) and one Gemini chat call (to write the answer from them). Re-run the script
only when the knowledge base in Qdrant changes.

Settings (saarthi_backend/.env, saarthi_backend/.env.kb):
    GEMINI_API_KEY      Gemini key (falls back to OPENAI_API_KEY)
    KB_EMBED_MODEL      default gemini-embedding-001
    KB_CHAT_MODEL       default gemini-3.5-flash-lite
    QDRANT_BACKEND, QDRANT_CLOUD_URL, QDRANT_CLOUD_API_KEY, QDRANT_LOCAL_URL,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION   (index build only)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = _PROJECT_ROOT / "knowledge_base" / "gemini_kb" / "index.json"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_EMBED_BATCH = 90  # Gemini embeds at most 100 texts per request

ANSWER_SYSTEM = (
    "You are Saarthi, a tutor for engineering students. Answer the question using ONLY the "
    "numbered excerpts from the course notes. The excerpts are OCR text from handwritten notes, "
    "so they can be noisy: read through obvious OCR errors, but do not add facts that are not in "
    "them. Cite the excerpts you use like [1] or [2]. If the excerpts do not answer the question, "
    "say that the notes do not cover it. Write equations in LaTeX between $...$."
)


# ── Settings ────────────────────────────────────────────────────────────────

def _gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not key:
        raise RuntimeError("No Gemini API key. Set GEMINI_API_KEY in saarthi_backend/.env.")
    return key


def embed_model() -> str:
    return os.environ.get("KB_EMBED_MODEL", "gemini-embedding-001")


def chat_model() -> str:
    return os.environ.get("KB_CHAT_MODEL", "gemini-3.5-flash-lite")


def _client():
    from openai import OpenAI

    return OpenAI(api_key=_gemini_key(), base_url=GEMINI_BASE_URL, timeout=60, max_retries=2)


def _qdrant_settings() -> tuple[str, str, str]:
    backend = os.environ.get("QDRANT_BACKEND", "").strip().lower()
    if backend == "cloud":
        url, key = os.environ.get("QDRANT_CLOUD_URL", ""), os.environ.get("QDRANT_CLOUD_API_KEY", "")
    elif backend == "local":
        url, key = os.environ.get("QDRANT_LOCAL_URL", ""), ""
    else:
        url, key = os.environ.get("QDRANT_URL", ""), os.environ.get("QDRANT_API_KEY", "")
    collection = os.environ.get("QDRANT_COLLECTION", "")
    if not url or not collection:
        raise RuntimeError("Qdrant is not configured. Check saarthi_backend/.env.kb.")
    return url.rstrip("/"), key, collection


# ── One-time index build ────────────────────────────────────────────────────

def fetch_qdrant_chunks() -> list[dict]:
    """Every chunk's payload from the Qdrant collection (REST scroll, no qdrant-client needed)."""
    url, key, collection = _qdrant_settings()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["api-key"] = key
    chunks: list[dict] = []
    offset = None
    while True:
        body: dict = {"limit": 256, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        req = urllib.request.Request(
            f"{url}/collections/{collection}/points/scroll",
            data=json.dumps(body).encode(), headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())["result"]
        for p in result["points"]:
            payload = p.get("payload") or {}
            if (payload.get("text") or "").strip():
                chunks.append({"id": str(p["id"]), **payload})
        offset = result.get("next_page_offset")
        if offset is None:
            return chunks


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts in batches, waiting for the free tier's per-minute quota when it runs out."""
    import openai

    client = _client()
    out: list[list[float]] = []
    for start in range(0, len(texts), _EMBED_BATCH):
        batch = texts[start:start + _EMBED_BATCH]
        for attempt in range(6):
            try:
                resp = client.embeddings.create(model=embed_model(), input=batch)
                if len(resp.data) != len(batch):
                    raise RuntimeError(f"Gemini returned {len(resp.data)} vectors for {len(batch)} texts")
                # Gemini leaves `index` empty; results come back in input order.
                out.extend(d.embedding for d in resp.data)
                break
            except openai.RateLimitError:
                if attempt == 5:
                    raise
                logger.info("Gemini embedding quota reached; waiting a minute…")
                time.sleep(61)
    return out


def build_index() -> dict:
    """Fetch the chunks from Qdrant, embed them with Gemini and save them to INDEX_PATH."""
    chunks = fetch_qdrant_chunks()
    if not chunks:
        raise RuntimeError("The Qdrant collection has no chunks with text.")
    vectors = _embed([c["text"] for c in chunks])
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "embedding_model": embed_model(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "chunks": [{**c, "vector": v} for c, v in zip(chunks, vectors)],
    }
    INDEX_PATH.write_text(json.dumps(data), encoding="utf-8")
    _cache.clear()
    return {"chunks": len(chunks), "path": str(INDEX_PATH), "embedding_model": data["embedding_model"]}


# ── Retrieval and answer ────────────────────────────────────────────────────

_cache: dict = {}
_cache_lock = threading.Lock()


def _load():
    """(chunks, normalized vectors, model) from INDEX_PATH, loaded once."""
    import numpy as np

    with _cache_lock:
        if "chunks" not in _cache:
            if not INDEX_PATH.exists():
                raise FileNotFoundError(
                    "The knowledge base index is not built yet. Run: py -3.13 -m scripts.build_kb_gemini_index"
                )
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            chunks = data["chunks"]
            mat = np.array([c.pop("vector") for c in chunks], dtype=np.float32)
            mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
            _cache.update(chunks=chunks, matrix=mat, model=data.get("embedding_model"), built_at=data.get("built_at"))
        return _cache["chunks"], _cache["matrix"], _cache["model"]


def status() -> dict:
    try:
        chunks, _, model = _load()
        return {"ready": True, "chunks": len(chunks), "embeddingModel": model, "builtAt": _cache.get("built_at")}
    except FileNotFoundError as e:
        return {"ready": False, "chunks": 0, "message": str(e)}


def search(question: str, k: int = 5) -> list[dict]:
    """The k chunks closest to the question, best first, each with a cosine score."""
    import numpy as np

    chunks, mat, model = _load()
    resp = _client().embeddings.create(model=model or embed_model(), input=[question])
    q = np.array(resp.data[0].embedding, dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-12
    scores = mat @ q
    top = np.argsort(-scores)[:k]
    return [{**chunks[i], "score": float(scores[i])} for i in top]


def index_ready() -> bool:
    """True when the one-time index file exists."""
    return INDEX_PATH.exists()


def answer(question: str, k: int = 5, history: list[dict] | None = None) -> dict:
    """Retrieve the closest chunks and have Gemini answer from them, with numbered citations.

    `history` is earlier chat turns ({role, content}); the last few are sent so follow-ups
    ("explain more") make sense, and the previous question is added to short search queries.
    """
    history = [m for m in (history or []) if m.get("role") in ("user", "assistant") and m.get("content")][-6:]
    prev = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    query = f"{prev} {question}" if prev and len(question.split()) < 6 else question
    hits = search(query, k)
    excerpts = "\n\n".join(
        f"[{n}] ({h.get('source_file', 'notes')}, page {h.get('page') or '?'})\n{h['text']}"
        for n, h in enumerate(hits, start=1)
    )
    resp = _client().chat.completions.create(
        model=chat_model(),
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM},
            *({"role": m["role"], "content": m["content"][:2000]} for m in history),
            {"role": "user", "content": f"Excerpts:\n{excerpts}\n\nQuestion: {question}"},
        ],
    )
    return {
        "answer": resp.choices[0].message.content or "",
        "sources": [
            {
                "n": n,
                "sourceFile": h.get("source_file"),
                "page": h.get("page"),
                "topic": h.get("topic"),
                "sourceType": h.get("source_type"),
                "score": round(h["score"], 3),
                "text": h["text"],
            }
            for n, h in enumerate(hits, start=1)
        ],
    }
