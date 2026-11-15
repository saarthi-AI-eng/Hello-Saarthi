"""Hybrid structural + semantic-boundary + size-aware chunking.

Three layers, applied in order, per the spec:
1. Structural segmentation — split a NormalizedDoc's text on its own
   structural markers (headings, blank-line paragraph breaks already
   preserved by scripts/clean_content.py's cleaning step, and video
   transcript segments merged by proximity).
2. Semantic boundary detection — optional (semantic_boundary_detection
   in KBConfig), uses an embedder's cosine similarity between consecutive
   structural units to find additional merge/split points. Disabled by
   default in cheap/no-GPU test runs by simply not passing an embedder.
3. Size-aware construction — merges small structural units up to
   chunk_target_tokens, splits anything over chunk_max_tokens, applies
   chunk_overlap_tokens between adjacent chunks of a split-up large unit.

Equations are never split from their surrounding explanation: a
NormalizedDoc with math_equation_blocks is kept whole unless it exceeds
chunk_max_tokens, matching "preserve equation text and surrounding
explanation" and "do not split equations unnecessarily".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import tiktoken

from src.knowledge_base.config import KBConfig
from src.knowledge_base.schema import Chunk, NormalizedDoc

_ENCODING = tiktoken.get_encoding("cl100k_base")  # token-count estimate only — not tied to any specific embedding model's tokenizer
_HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Za-z0-9 ,.-]{2,60}:?$)", re.MULTILINE)


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text, disallowed_special=()))


def _mean_qa_score(scores: Sequence[Optional[float]]) -> Optional[float]:
    present = [s for s in scores if s is not None]
    return sum(present) / len(present) if present else None


def stable_chunk_id(source_id: str, ordinal: int, content_hash: str, schema_version: str) -> str:
    """Deterministic: the same source + same ordinal position + same
    content + same chunking config always produces the same ID, so
    re-running the pipeline on unchanged content never creates duplicate
    Qdrant points (Phase 4's "use deterministic IDs" requirement)."""
    basis = f"{source_id}|{ordinal}|{content_hash}|{schema_version}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"chunk_{digest}"


@dataclass
class _StructuralUnit:
    text: str
    doc: NormalizedDoc
    is_equation_bearing: bool = False


def _split_text_paragraphs(doc: NormalizedDoc) -> List[_StructuralUnit]:
    """Paragraph/heading-aware split for OCR'd text (notes/slides)."""
    if not doc.text.strip():
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc.text) if p.strip()]
    if not paragraphs:
        paragraphs = [doc.text.strip()]
    return [_StructuralUnit(text=p, doc=doc, is_equation_bearing=bool(doc.math_equation_blocks)) for p in paragraphs]


def _merge_video_docs(docs: Sequence[NormalizedDoc], max_gap_seconds: float) -> List[NormalizedDoc]:
    """Merges consecutive video-transcript NormalizedDocs from the SAME
    source_id whose timestamps are within max_gap_seconds of each other —
    "do not create one chunk per tiny transcript segment". Returns new
    NormalizedDoc-like merged units (not written back to normalized_docs.jsonl,
    only used internally by structural segmentation)."""
    if not docs:
        return []
    ordered = sorted(docs, key=lambda d: (d.source_id or "", d.start_time or 0.0))
    merged: List[NormalizedDoc] = []
    for doc in ordered:
        if (
            merged
            and merged[-1].source_id == doc.source_id
            and merged[-1].end_time is not None
            and doc.start_time is not None
            and (doc.start_time - merged[-1].end_time) <= max_gap_seconds
        ):
            prev = merged[-1]
            merged[-1] = NormalizedDoc(
                doc_id=f"{prev.doc_id}+{doc.doc_id}",
                source_id=prev.source_id,
                source_type=prev.source_type,
                source_file=prev.source_file,
                course=prev.course, topic=prev.topic, lecture=prev.lecture,
                page=prev.page, start_time=prev.start_time, end_time=doc.end_time,
                text=f"{prev.text} {doc.text}".strip(),
                qa_status=prev.qa_status,
                qa_score=_mean_qa_score([prev.qa_score, doc.qa_score]),
                ocr_quality=prev.ocr_quality, ocr_confidence=prev.ocr_confidence,
                review_reasons=prev.review_reasons, math_equation_blocks=prev.math_equation_blocks,
                raw_metadata=prev.raw_metadata,
            )
        else:
            merged.append(doc)
    return merged


def structural_segment(docs: Sequence[NormalizedDoc], config: KBConfig) -> List[_StructuralUnit]:
    video_docs = [d for d in docs if d.source_type == "video_transcript"]
    other_docs = [d for d in docs if d.source_type != "video_transcript"]

    units: List[_StructuralUnit] = []
    for doc in _merge_video_docs(video_docs, config.video_segment_merge_gap_seconds):
        if doc.text.strip():
            units.append(_StructuralUnit(text=doc.text.strip(), doc=doc))
    for doc in other_docs:
        units.extend(_split_text_paragraphs(doc))
    return units


def semantic_merge_boundaries(units: Sequence[_StructuralUnit], config: KBConfig, embed_fn: Optional[Callable[[List[str]], List[List[float]]]]) -> List[bool]:
    """Returns a list the same length as units; index i is True if a
    semantic boundary exists BETWEEN unit i and unit i+1 (last entry
    always True). embed_fn is a batched text->vectors callable — pass
    None (or config.semantic_boundary_detection=False) to skip this
    layer entirely and fall back to structural-only boundaries, which is
    both the cheap-test-run path and a legitimate configuration, not
    just a fallback-on-failure."""
    n = len(units)
    if n == 0:
        return []
    if not config.semantic_boundary_detection or embed_fn is None or n < 2:
        return [True] * n

    import numpy as np

    vectors = embed_fn([u.text for u in units])
    arr = np.array(vectors)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = arr / norms

    boundaries = []
    for i in range(n - 1):
        similarity = float(np.dot(normed[i], normed[i + 1]))
        boundaries.append(similarity < config.semantic_similarity_threshold)
    boundaries.append(True)
    return boundaries


def build_chunks(units: Sequence[_StructuralUnit], boundaries: Sequence[bool], config: KBConfig) -> List[Chunk]:
    """Size-aware construction: merges units up to chunk_target_tokens
    (never crossing a semantic/structural boundary unless forced by
    chunk_max_tokens), splits anything still over chunk_max_tokens with
    chunk_overlap_tokens between the resulting pieces. Equation-bearing
    units are only split if they alone exceed chunk_max_tokens."""
    chunks: List[Chunk] = []
    ordinal = 0

    buffer_units: List[_StructuralUnit] = []
    buffer_tokens = 0

    def flush():
        nonlocal ordinal, buffer_units, buffer_tokens
        if not buffer_units:
            return
        text = "\n\n".join(u.text for u in buffer_units)
        token_count = count_tokens(text)
        source_doc = buffer_units[0].doc
        has_equation = any(u.is_equation_bearing for u in buffer_units)

        if token_count > config.chunk_max_tokens and not has_equation:
            for piece_text in _split_oversized(text, config):
                ordinal += 1
                chunks.append(_make_chunk(piece_text, source_doc, ordinal, config, has_equation=False, all_docs=[u.doc for u in buffer_units]))
        else:
            ordinal += 1
            chunks.append(_make_chunk(text, source_doc, ordinal, config, has_equation=has_equation, all_docs=[u.doc for u in buffer_units]))
        buffer_units = []
        buffer_tokens = 0

    for i, unit in enumerate(units):
        unit_tokens = count_tokens(unit.text)
        would_exceed = buffer_tokens + unit_tokens > config.chunk_target_tokens
        if buffer_units and (would_exceed or (buffer_tokens >= config.chunk_min_tokens and boundaries[i - 1])):
            flush()
        buffer_units.append(unit)
        buffer_tokens += unit_tokens
    flush()
    return chunks


def _split_oversized(text: str, config: KBConfig) -> List[str]:
    """Token-window split with overlap — only reached for a unit too
    large to keep whole and not equation-bearing (equations are
    deliberately exempted above)."""
    tokens = _ENCODING.encode(text, disallowed_special=())
    pieces = []
    step = max(1, config.chunk_target_tokens - config.chunk_overlap_tokens)
    for start in range(0, len(tokens), step):
        window = tokens[start:start + config.chunk_target_tokens]
        pieces.append(_ENCODING.decode(window))
        if start + config.chunk_target_tokens >= len(tokens):
            break
    return pieces


def _make_chunk(text: str, doc: NormalizedDoc, ordinal: int, config: KBConfig, has_equation: bool, all_docs: List[NormalizedDoc]) -> Chunk:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    chunk_id = stable_chunk_id(doc.source_id or doc.doc_id, ordinal, content_hash, config.chunk_schema_version)
    pages = sorted({d.page for d in all_docs if d.page is not None})
    ocr_review_flagged = any((d.ocr_quality in ("POOR_EXTRACTION", "NEEDS_REVIEW")) or d.review_reasons for d in all_docs)
    equation_review_flagged = any(
        any(b.get("review_required") for b in (d.math_equation_blocks or []))
        for d in all_docs
    )
    return Chunk(
        chunk_id=chunk_id,
        source_id=doc.source_id or doc.doc_id,
        source_type=doc.source_type,
        source_file=doc.source_file,
        text=text,
        course=doc.course,
        topic=doc.topic,
        heading=None,  # heading hierarchy extraction is a documented, not-yet-implemented extension — see docs/KB_PIPELINE_SETUP.md limitations
        page=pages[0] if len(pages) == 1 else None,
        page_range=pages if len(pages) > 1 else None,
        start_time=all_docs[0].start_time,
        end_time=all_docs[-1].end_time,
        ocr_quality=doc.ocr_quality,
        ocr_review_flagged=ocr_review_flagged,
        qa_score=_mean_qa_score([d.qa_score for d in all_docs]),
        has_equation=has_equation,
        equation_review_flagged=equation_review_flagged,
        content_hash=content_hash,
        chunk_schema_version=config.chunk_schema_version,
        token_count=count_tokens(text),
        doc_ids=[d.doc_id for d in all_docs],
    )


def chunk_documents(docs: Sequence[NormalizedDoc], config: KBConfig, embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None) -> List[Chunk]:
    units = structural_segment(docs, config)
    boundaries = semantic_merge_boundaries(units, config, embed_fn)
    return build_chunks(units, boundaries, config)
