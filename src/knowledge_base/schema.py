"""Normalized intermediate schema and chunk schema for the KB pipeline.

Two distinct shapes, both documented and versioned here (not scattered
across scripts):

1. NormalizedDoc — one per ContentRecord, after normalize_content_kb.py.
   Mostly a pass-through of ContentRecord with a documented, stable
   field set (so chunking never has to guess which ContentRecord.metadata
   keys exist for a given content_type).
2. Chunk — the final unit stored in Qdrant, produced by chunk_content_kb.py.
   CHUNK_SCHEMA_VERSION bumps whenever this shape changes, so chunks built
   under different versions are never silently mixed in one collection.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

CHUNK_SCHEMA_VERSION = "1.1"  # bumped: added qa_score (Content QA Phase 1 integration)


@dataclass
class NormalizedDoc:
    """One normalized unit of source content — one per input ContentRecord.
    Deliberately close to ContentRecord's own shape (this is a thin,
    documented view, not a rewrite) plus a few fields chunking needs
    that aren't worth re-deriving from metadata every time."""

    doc_id: str                       # == ContentRecord.content_id
    source_id: Optional[str]          # == ContentRecord.source_id
    source_type: str                  # == ContentRecord.content_type.value
    source_file: str                  # == ContentRecord.source
    course: Optional[str]
    topic: Optional[str]
    lecture: Optional[str]
    page: Optional[int]
    start_time: Optional[float]
    end_time: Optional[float]
    text: str
    qa_status: str
    qa_score: Optional[float] = None               # metadata.qa.score (src/content_qa), when present
    ocr_quality: Optional[str] = None             # metadata.page_quality, when present
    ocr_confidence: Optional[float] = None         # metadata.ocr_confidence, when present
    review_reasons: list[str] = field(default_factory=list)   # metadata.review_reasons, when present
    math_equation_blocks: list[dict] = field(default_factory=list)  # metadata.math_equation_blocks, when present
    raw_metadata: dict[str, Any] = field(default_factory=dict)  # full original ContentRecord.metadata, never discarded

    def content_hash(self) -> str:
        """Stable hash of exactly the fields that determine this doc's
        chunking/embedding output — changing unrelated metadata (e.g. a
        re-run that only updates a timestamp) must not force a rebuild."""
        basis = f"{self.doc_id}|{self.text}|{self.ocr_quality}|{self.ocr_confidence}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


@dataclass
class Chunk:
    """One chunk, ready for embedding + Qdrant upsert."""

    chunk_id: str                     # deterministic — see chunker.stable_chunk_id()
    source_id: str
    source_type: str
    source_file: str
    text: str
    course: Optional[str] = None
    unit: Optional[str] = None
    topic: Optional[str] = None
    heading: Optional[str] = None
    page: Optional[int] = None
    page_range: Optional[list[int]] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    ocr_quality: Optional[str] = None
    ocr_review_flagged: bool = False
    qa_score: Optional[float] = None               # mean of the contributing NormalizedDocs' qa_score, when present
    has_equation: bool = False
    equation_review_flagged: bool = False
    content_hash: str = ""
    chunk_schema_version: str = CHUNK_SCHEMA_VERSION
    token_count: int = 0
    doc_ids: list[str] = field(default_factory=list)   # source NormalizedDoc.doc_id(s) this chunk was built from

    def to_payload(self) -> dict[str, Any]:
        """Exactly what gets stored as the Qdrant point payload — the AI
        team reads this, not the pipeline internals."""
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_file": self.source_file,
            "text": self.text,
            "course": self.course,
            "unit": self.unit,
            "topic": self.topic,
            "heading": self.heading,
            "page": self.page,
            "page_range": self.page_range,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "ocr_quality": self.ocr_quality,
            "ocr_review_flagged": self.ocr_review_flagged,
            "qa_score": self.qa_score,
            "has_equation": self.has_equation,
            "equation_review_flagged": self.equation_review_flagged,
            "content_hash": self.content_hash,
            "chunk_schema_version": self.chunk_schema_version,
            "token_count": self.token_count,
        }
