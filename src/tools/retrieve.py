"""Single retrieval door used by experts and chat_service.

Uses src/retrieval/ (hybrid) when that package is on disk.
If it is missing (common on the eval laptop), falls back to dense FAISS
so the API still boots.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

try:
    from src.retrieval.pipeline import search_index as _search_index
    from src.retrieval.types import Hit as _Hit
    _HAS_ENGINE = True
except Exception as e:  # ModuleNotFoundError and broken optional deps
    _search_index = None
    _Hit = None
    _HAS_ENGINE = False
    logger.warning("src.retrieval not available (%s); using FAISS-only retrieve()", e)

_AGENT = {
    "notes": "notes_agent",
    "books": "books_agent",
    "video": "video_agent",
}


@dataclass
class Chunk:
    id: str
    text: str
    content_type: str
    source_file: str
    title: str
    page: int | None = None
    start_sec: int | None = None
    end_sec: int | None = None
    course_id: int | None = None
    video_id: int | None = None
    score: float | None = None
    via: str | None = None
    language: str | None = None


# Per-request trace of the last retrieve() call (legs used, hops, boosts) for telemetry.
last_trace: ContextVar[list] = ContextVar("retrieve_last_trace", default=[])


def _docs_to_chunks(docs, content_type: str) -> list[Chunk]:
    out = []
    for i, d in enumerate(docs):
        md = getattr(d, "metadata", None) or {}
        text = (getattr(d, "page_content", None) or "").strip()
        if not text:
            continue
        out.append(
            Chunk(
                id=str(md.get("id") or f"{content_type}-{i}"),
                text=text,
                content_type=content_type,
                source_file=str(md.get("source") or md.get("material_title") or ""),
                title=str(md.get("material_title") or md.get("video_title") or md.get("source") or ""),
                page=md.get("page") or md.get("page_number"),
                start_sec=md.get("start_sec"),
                end_sec=md.get("end_sec"),
                course_id=md.get("course_id"),
                video_id=md.get("video_id"),
                score=md.get("score"),
                via="dense",
                language=md.get("language"),
            )
        )
    return out


def _hit_to_chunk(h) -> Chunk:
    md = h.metadata or {}
    return Chunk(
        id=h.source_id,
        text=h.text,
        content_type=h.content_type,
        source_file=str(md.get("source") or md.get("material_title") or h.source_id),
        title=str(md.get("material_title") or md.get("video_title") or md.get("source") or md.get("title") or ""),
        page=md.get("page") or md.get("page_number"),
        start_sec=md.get("start_sec"),
        end_sec=md.get("end_sec"),
        course_id=md.get("course_id"),
        video_id=md.get("video_id"),
        score=h.score,
        via=h.via,
        language=md.get("language"),
    )


def _targets(
    content_types: list[str] | None,
    course_id: int | None,
    video_id: int | None,
) -> list[tuple[Path, str]]:
    if video_id is not None:
        return [(Path("knowledge_base") / "videos" / str(video_id) / "vector_store", "video")]
    if course_id is not None:
        return [(Path("knowledge_base") / "courses" / str(course_id) / "vector_store", "course_material")]
    types = content_types or ["notes", "books", "video"]
    out: list[tuple[Path, str]] = []
    for t in types:
        agent = _AGENT.get(t)
        if agent:
            out.append((Path("knowledge_base") / agent / "vector_store", t))
    if content_types is None:
        courses_root = Path("knowledge_base") / "courses"
        if courses_root.exists():
            for d in sorted(courses_root.iterdir()):
                vs = d / "vector_store"
                if vs.exists():
                    out.append((vs, "course_material"))
    return out


def _search_faiss(index_dir: Path, query: str, k: int):
    faiss_file = index_dir / "index.faiss"
    if not faiss_file.exists():
        return []
    try:
        from langchain_community.vectorstores import FAISS
        from src.utils.llm import embeddings
        vs = FAISS.load_local(
            str(index_dir),
            embeddings(),
            allow_dangerous_deserialization=True,
        )
        return vs.similarity_search(query, k=k)
    except Exception as e:
        logger.warning("FAISS load/search failed for %s: %s", index_dir, e)
        return []


def retrieve(
    query: str,
    *,
    content_types: list[str] | None = None,
    course_id: int | None = None,
    video_id: int | None = None,
    material_title: str | None = None,
    k: int = 5,
    mode: str | None = None,
    expand_via_graph: bool | None = None,
    boost_terms: list[str] | None = None,
) -> list[Chunk]:
    """boost_terms (e.g. the student's weak topics) only reorder hits; they never filter."""
    q = f"{material_title or ''} {query}".strip() if material_title else query
    expand = expand_via_graph
    if mode == "dense":
        expand = False
    # A course index holds every material of the course. When the student is viewing
    # one document we filter by title *after* the search, so pull a wider pool first;
    # otherwise other materials crowd the viewed document out of the top-k.
    filter_by_title = bool(material_title) and course_id is not None
    search_k = k * 6 if filter_by_title else k
    chunks: list[Chunk] = []
    traces: list = []
    for index_dir, ctype in _targets(content_types, course_id, video_id):
        if not index_dir.exists():
            continue
        try:
            if _HAS_ENGINE and _search_index is not None:
                hits, trace = _search_index(
                    q,
                    index_dir,
                    content_type=ctype,
                    top_k=search_k,
                    expand_via_graph=expand,
                    boost_terms=boost_terms,
                )
                traces.append(trace)
                chunks.extend(_hit_to_chunk(h) for h in hits)
            else:
                docs = _search_faiss(index_dir, q, search_k)
                chunks.extend(_docs_to_chunks(docs, ctype))
        except Exception as e:
            logger.warning("retrieve failed for %s: %s", index_dir, e)

    if filter_by_title:
        title = material_title.lower().replace(" ", "_")
        filtered = [
            c for c in chunks
            if title in (c.source_file or "").lower().replace(" ", "_")
            or title in (c.title or "").lower().replace(" ", "_")
        ]
        if filtered:
            chunks = filtered

    last_trace.set(traces)

    # Several folders (default targets) each return their own top-k: interleave by fused score.
    if len(traces) > 1:
        chunks.sort(key=lambda c: c.score or 0.0, reverse=True)

    seen: set[str] = set()
    uniq: list[Chunk] = []
    for c in chunks:
        key = c.id or (c.text or "")[:160]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq[: max(k, 5)]


def chunks_as_prompt(chunks: list[Chunk]) -> str:
    """Excerpts for a prompt, each headed by its citation label ([Title, p. N] / [Video: T, mm:ss])."""
    if not chunks:
        return ""
    from src.tools.citations import excerpts_block
    return excerpts_block(chunks)
