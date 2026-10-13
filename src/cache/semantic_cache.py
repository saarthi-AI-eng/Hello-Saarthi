"""Semantic answer cache — Tier 0 (WBS 1.1.2 / 4.3, B2).

Same question => same answer, no second model call. Stores
(query embedding, answer, citations, chunk ids) and returns a cached answer
when cosine similarity >= SEMANTIC_CACHE_THRESHOLD (default 0.95) within the
same *scope*, for SEMANTIC_CACHE_TTL_DAYS (default 30).

Scope keeps corpus isolation: an answer cached inside course 3 is never served
in course 4 or in general chat. Re-indexing / deleting a course material
drops that course's entries (invalidate_course).

Embeddings come from src.utils.llm.embeddings() — the same model as the index.
Entries written with another embedding model are ignored.

Lexical guard: cosine alone is not safe for STEM questions — with nomic-embed-text,
"Is x(t)=2x(t-1) causal?" vs "... 2x(t+1) ..." scores 0.98 although the answers
differ. A hit therefore also needs the same math/number signature and no differing
content words beyond neutral framing ("define", "explain", "what is", ...).

Storage: knowledge_base/cache/semantic_cache.sqlite (stdlib sqlite3).
SEMANTIC_CACHE=0 disables it.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _PROJECT_ROOT / "knowledge_base" / "cache" / "semantic_cache.sqlite"

_NEVER_CACHE = (
    "something went wrong",
    "took too long",
    "could not generate",
    "please try again",
)


# Words that only frame a question; differing in these does not change the answer.
_NEUTRAL = frozenset(
    "what whats is are was define definition meaning mean means explain explanation describe "
    "tell me please give brief briefly short about concept term".split()
)
_MATH = re.compile(r"\d+(?:\.\d+)?|[+\-*/^=<>()\[\]{}|]")


def _content_tokens(text: str) -> set[str]:
    from src.retrieval.bm25 import tokenize
    return set(tokenize(text))


def lexically_compatible(a: str, b: str) -> bool:
    """True if two questions differ only in neutral framing words."""
    if _MATH.findall(a.replace(" ", "")) != _MATH.findall(b.replace(" ", "")):
        return False
    return (_content_tokens(a) ^ _content_tokens(b)) <= _NEUTRAL


def enabled() -> bool:
    return os.environ.get("SEMANTIC_CACHE", "1").strip().lower() not in ("0", "false", "no", "off")


def threshold() -> float:
    return float(os.environ.get("SEMANTIC_CACHE_THRESHOLD", "0.95"))


def ttl_seconds() -> float:
    return float(os.environ.get("SEMANTIC_CACHE_TTL_DAYS", "30")) * 86400


def build_scope(
    *,
    course_id: int | None = None,
    material_title: str | None = None,
    video_id: int | None = None,
    mode: str = "chat",
) -> str:
    parts = [f"course:{course_id}" if course_id is not None else "course:-"]
    if material_title:
        parts.append(f"material:{material_title.strip().lower()}")
    if video_id is not None:
        parts.append(f"video:{video_id}")
    parts.append(f"mode:{mode}")
    return "|".join(parts)


@dataclass
class CacheHit:
    answer: str
    citations: list = field(default_factory=list)
    chunk_ids: list = field(default_factory=list)
    similarity: float = 0.0
    cached_query: str = ""
    entry_id: int = 0


class SemanticCache:
    def __init__(self, path: Path | None = None):
        self.path = path or DB_PATH  # resolved at construction so DB_PATH can be redirected
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path), check_same_thread=False)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    emb_model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    citations TEXT,
                    chunk_ids TEXT,
                    answer_model TEXT,
                    tier INTEGER,
                    created_at REAL NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 0,
                    last_hit REAL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_entries_scope ON entries (scope)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS stats (day TEXT PRIMARY KEY, lookups INTEGER NOT NULL DEFAULT 0, hits INTEGER NOT NULL DEFAULT 0)"
            )
            conn.commit()
            self._conn = conn
        return self._conn

    # ── embedding helpers ────────────────────────────────────────────────────
    @staticmethod
    def embed(query: str) -> tuple[list[float], str]:
        from src.utils.llm import embedding_model_name, embeddings
        return embeddings().embed_query(query), embedding_model_name()

    # ── API ──────────────────────────────────────────────────────────────────
    def lookup(self, query: str, scope: str, embedding: list[float] | None = None) -> tuple[CacheHit | None, list[float] | None]:
        """Return (hit or None, query embedding for a later store())."""
        if not enabled() or not query.strip():
            return None, None
        import numpy as np

        try:
            if embedding is None:
                embedding, model = self.embed(query)
            else:
                from src.utils.llm import embedding_model_name
                model = embedding_model_name()
        except Exception as e:
            logger.info("Semantic cache lookup skipped (embedding failed: %s)", e)
            return None, None

        q = np.asarray(embedding, dtype="float32")
        qn = float(np.linalg.norm(q)) or 1.0
        cutoff = time.time() - ttl_seconds()
        best: tuple[float, tuple] | None = None
        with self._lock:
            db = self._db()
            rows = db.execute(
                "SELECT id, embedding, query, answer, citations, chunk_ids FROM entries "
                "WHERE scope = ? AND emb_model = ? AND dim = ? AND created_at >= ?",
                (scope, model, len(embedding), cutoff),
            ).fetchall()
            for row in rows:
                v = np.frombuffer(row[1], dtype="float32")
                sim = float(np.dot(q, v) / (qn * (float(np.linalg.norm(v)) or 1.0)))
                if sim < threshold() or not lexically_compatible(query, row[2]):
                    continue
                if best is None or sim > best[0]:
                    best = (sim, row)
            day = date.today().isoformat()
            hit = best is not None and best[0] >= threshold()
            db.execute(
                "INSERT INTO stats (day, lookups, hits) VALUES (?, 1, ?) "
                "ON CONFLICT(day) DO UPDATE SET lookups = lookups + 1, hits = hits + excluded.hits",
                (day, 1 if hit else 0),
            )
            if hit:
                db.execute("UPDATE entries SET hits = hits + 1, last_hit = ? WHERE id = ?", (time.time(), best[1][0]))
            db.commit()

        if not hit:
            return None, embedding
        sim, row = best
        return CacheHit(
            answer=row[3],
            citations=json.loads(row[4] or "[]"),
            chunk_ids=json.loads(row[5] or "[]"),
            similarity=round(sim, 4),
            cached_query=row[2],
            entry_id=row[0],
        ), embedding

    def store(
        self,
        query: str,
        scope: str,
        answer: str,
        *,
        citations: list | None = None,
        chunk_ids: list | None = None,
        answer_model: str = "",
        tier: int = 1,
        embedding: list[float] | None = None,
    ) -> bool:
        if not enabled():
            return False
        text = (answer or "").strip()
        if len(text) < 40 or any(p in text.lower()[:200] for p in _NEVER_CACHE):
            return False
        try:
            if embedding is None:
                embedding, model = self.embed(query)
            else:
                from src.utils.llm import embedding_model_name
                model = embedding_model_name()
        except Exception as e:
            logger.info("Semantic cache store skipped (embedding failed: %s)", e)
            return False
        import numpy as np

        blob = np.asarray(embedding, dtype="float32").tobytes()
        with self._lock:
            db = self._db()
            db.execute(
                "INSERT INTO entries (scope, emb_model, dim, embedding, query, answer, citations, chunk_ids, "
                "answer_model, tier, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (scope, model, len(embedding), blob, query, text, json.dumps(citations or []),
                 json.dumps(chunk_ids or []), answer_model, tier, time.time()),
            )
            db.execute("DELETE FROM entries WHERE created_at < ?", (time.time() - ttl_seconds(),))
            db.commit()
        return True

    def forget(self, scope: str | None = None, query: str | None = None, entry_id: int | None = None) -> int:
        """Feedback eviction (WBS 3.4.4): a thumbs-down removes the answer from Tier 0."""
        clauses, args = [], []
        if entry_id is not None:
            clauses.append("id = ?")
            args.append(int(entry_id))
        if scope and query:
            clauses.append("(scope = ? AND lower(trim(query)) = lower(trim(?)))")
            args += [scope, query]
        if not clauses:
            return 0
        with self._lock:
            cur = self._db().execute(f"DELETE FROM entries WHERE {' OR '.join(clauses)}", args)
            self._db().commit()
            return cur.rowcount

    def invalidate_course(self, course_id: int) -> int:
        with self._lock:
            cur = self._db().execute("DELETE FROM entries WHERE scope LIKE ?", (f"course:{course_id}|%",))
            self._db().commit()
            return cur.rowcount

    def invalidate_video(self, video_id: int) -> int:
        with self._lock:
            cur = self._db().execute("DELETE FROM entries WHERE scope LIKE ?", (f"%|video:{video_id}|%",))
            self._db().commit()
            return cur.rowcount

    def stats(self, days: int = 14) -> dict:
        with self._lock:
            db = self._db()
            rows = db.execute("SELECT day, lookups, hits FROM stats ORDER BY day DESC LIMIT ?", (days,)).fetchall()
            n = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        lookups = sum(r[1] for r in rows)
        hits = sum(r[2] for r in rows)
        return {
            "entries": n,
            "lookups": lookups,
            "hits": hits,
            "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
            "by_day": [{"day": r[0], "lookups": r[1], "hits": r[2]} for r in rows],
        }


_singleton: SemanticCache | None = None
_singleton_lock = threading.Lock()


def get_cache() -> SemanticCache:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = SemanticCache()
        return _singleton
