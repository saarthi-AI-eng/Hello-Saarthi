"""Shared, content-type-agnostic primitives used by both pdf_qa.py and
video_qa.py. Nothing here is OCR/ASR-engine-specific — that calibration
lives in pdf_qa.py/video_qa.py themselves."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable, Optional


def word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def control_char_ratio(text: str) -> float:
    """Ratio of characters that are control/replacement characters — NOT
    letters, digits, punctuation, whitespace, or any symbol category. This
    deliberately does not penalize Greek letters (category Ll/Lu), math
    operators (Sm), subscripts/superscripts, or any other printable
    technical notation — only genuine garbage (U+FFFD, stray control
    bytes) counts."""
    if not text:
        return 0.0
    bad = sum(1 for ch in text if ch == "�" or unicodedata.category(ch) == "Cc")
    return bad / len(text)


_REPEATED_RUN_RE_CACHE: dict[int, re.Pattern] = {}


def longest_repeated_char_run(text: str) -> int:
    """Longest run of one non-whitespace character repeated consecutively
    (e.g. "mmmmmmmmmm" -> 10). Whitespace runs don't count — those are
    normal formatting, not a corruption signal."""
    longest = 0
    run_char: Optional[str] = None
    run_len = 0
    for ch in text:
        if ch.isspace():
            run_char, run_len = None, 0
            continue
        if ch == run_char:
            run_len += 1
        else:
            run_char, run_len = ch, 1
        longest = max(longest, run_len)
    return longest


def is_near_empty(text: str, min_word_count: int, min_char_count: int) -> bool:
    stripped = text.strip()
    return len(stripped) < min_char_count or word_count(stripped) < min_word_count


class DuplicateTracker:
    """Tracks normalized (lowercased, whitespace-collapsed) text hashes
    per source_id, so an exact repeat of another page/segment from the
    SAME source is flagged — a repeat across different sources (e.g. a
    shared disclaimer slide in two different PDFs) is not."""

    def __init__(self) -> None:
        self._seen: dict[str, set[str]] = {}

    @staticmethod
    def _normalize(text: str) -> str:
        return hashlib.sha256(re.sub(r"\s+", " ", text.strip().lower()).encode("utf-8")).hexdigest()

    def is_duplicate(self, source_id: str, text: str) -> bool:
        key = self._normalize(text)
        seen_for_source = self._seen.setdefault(source_id or "", set())
        if key in seen_for_source:
            return True
        seen_for_source.add(key)
        return False


def qa_content_hash(text: str, extra: Iterable[tuple[str, object]] = ()) -> str:
    """Hash of exactly what influences this record's QA score — text plus
    whatever upstream signals the scorer used (ocr_confidence, page_quality,
    etc. for PDFs; avg_logprob, no_speech_prob for video). Used to detect
    'did the extracted content actually change since last QA run' without
    re-scoring every record every time (Part 1.6: avoid unnecessary
    reprocessing of identical content under the same qa_version)."""
    basis = text + "|" + "|".join(f"{k}={v}" for k, v in sorted(extra, key=lambda kv: kv[0]))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def weighted_score(checks: dict[str, float], weights: dict[str, float]) -> float:
    return sum(checks[dim] * weights[dim] for dim in weights if dim in checks)


def status_from_score(score: float, approved_min: float, pending_min: float) -> str:
    if score >= approved_min:
        return "approved"
    if score >= pending_min:
        return "pending"
    return "rejected"
