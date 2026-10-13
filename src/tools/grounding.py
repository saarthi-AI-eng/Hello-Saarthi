"""Grounding rule (DEC-1): retrieve the course excerpts for a turn and decide whether the
course materials cover the question at all; confidence signal for the UI (spec §7.1).

Coverage gate: at least one retrieved chunk must share a content term with the question
(BM25 tokens, framing words ignored). Dense search always returns *something*; this
stops "who won the world cup" from being answered out of a Fourier lecture.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.retrieval.bm25 import tokenize

_FRAMING = frozenset(
    "explain define definition meaning mean describe tell give example examples simple simply words "
    "detail details please help understand know about question answer lecture course notes".split()
)


@dataclass
class Grounding:
    chunks: list = field(default_factory=list)
    covered: bool = False
    overlap_terms: list = field(default_factory=list)


def content_terms(text: str) -> set[str]:
    return {t for t in tokenize(text) if len(t) > 2 and t not in _FRAMING}


def coverage(query: str, chunks) -> tuple[bool, list[str]]:
    """Covered when the excerpts contain at least half of the question's content terms,
    or at least three of them. One shared generic word is not enough: "orange zebra
    theorem" must not count as covered because a lecture mentions "theorem"."""
    q = content_terms(query)
    if not q:
        return bool(chunks), []
    hits: set[str] = set()
    for c in chunks:
        text = c.get("text") if isinstance(c, dict) else getattr(c, "text", "")
        hits |= q & set(tokenize(text or ""))
    return (len(hits) >= 3 or len(hits) / len(q) >= 0.5), sorted(hits)


def ground(
    query: str,
    *,
    course_id: int | None = None,
    material_title: str | None = None,
    video_id: int | None = None,
    n: int = 3,
    boost_terms: list[str] | None = None,
) -> Grounding:
    from src.tools.retrieve import retrieve

    chunks = retrieve(
        query, course_id=course_id, material_title=material_title, video_id=video_id,
        k=n, boost_terms=boost_terms,
    )[:n]
    covered, terms = coverage(query, chunks)
    return Grounding(chunks=chunks, covered=covered, overlap_terms=terms)


def confidence(*, covered: bool, cited: bool, critic_ok: bool | None, n_chunks: int) -> tuple[str, list[str]]:
    reasons = []
    if not covered or n_chunks == 0:
        reasons.append("not covered by course materials")
    if critic_ok is False:
        reasons.append("critic could not verify the answer against the excerpts")
    if covered and not cited:
        reasons.append("answer did not cite a source")
    return ("low" if reasons else "ok"), reasons
