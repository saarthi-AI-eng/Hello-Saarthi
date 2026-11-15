"""PDF/notes page QA scoring (Part 1.2). Operates on one ContentRecord at a
time (page-level, not whole-PDF — Part 1.5) using only signals
ingest_notes.py already computes; never re-runs or second-guesses OCR
itself.

Key design point: ingest_notes.py's own classify_page_quality() tags a
page NEEDS_REVIEW purely for containing math notation (MATHEMATICAL_CONTENT)
or for having no confidence score at all (NO_CONFIDENCE_SCORE, true of
every native pdf_text_layer page) — both are soft triage flags, not quality
defects. This module strips those two out before treating review_reasons
as a quality signal, so a page of genuine, well-extracted mathematics is
never penalized merely for containing math (Part 1.2's explicit
requirement). Genuinely bad equation extraction is still penalized, via
each equation block's own math_quality/review_required (Part 1.2's
"equation extraction metadata"), which is a real per-equation OCR-quality
signal, not a content-type penalty.
"""
from __future__ import annotations

from typing import Optional

from src.content_qa.checks import (
    DuplicateTracker,
    control_char_ratio,
    is_near_empty,
    longest_repeated_char_run,
    qa_content_hash,
    status_from_score,
    weighted_score,
)
from src.content_qa.config import QAConfig
from src.content_qa.result import QAResult

QA_METHOD = "pdf_heuristic_v1"

_SOFT_REVIEW_REASONS = {"MATHEMATICAL_CONTENT", "NO_CONFIDENCE_SCORE"}


def _tesseract_confidence_score(c: float) -> float:
    """Tesseract's own 'moderate' band (0.50-0.70) can still be garbled
    handwriting (measured on this project's real ground truth — see
    ingest_notes.py's own _confidence_tier() comment) — penalized harder
    than PaddleOCR's equivalent range below."""
    c = max(0.0, min(1.0, c))
    if c >= 0.90:
        return 100.0
    if c >= 0.75:
        return 80.0 + (c - 0.75) / 0.15 * 20.0
    if c >= 0.50:
        return 30.0 + (c - 0.50) / 0.25 * 50.0
    return c / 0.50 * 30.0


def _paddleocr_confidence_score(c: float) -> float:
    """PaddleOCR's confidence is better-calibrated to actual correctness
    on this project's content (per docs/ocr-benchmark-final-report.md) —
    a nearer-linear mapping, still conservative at the low end."""
    c = max(0.0, min(1.0, c))
    if c >= 0.85:
        return 90.0 + (c - 0.85) / 0.15 * 10.0
    if c >= 0.60:
        return 50.0 + (c - 0.60) / 0.25 * 40.0
    return c / 0.60 * 50.0


_NATIVE_TEXT_GARBLE_CLEAN_RATIO = 0.10   # every real approved native-text page measured <= 0.094
_NATIVE_TEXT_GARBLE_BROKEN_RATIO = 0.20  # every garbled-encoding page measured found so far >= 0.125


def _recognition_confidence(text: str, metadata: dict, issues: list[str]) -> float:
    engine = metadata.get("ocr_engine")
    raw_conf = metadata.get("ocr_confidence")
    if engine == "pdf_text_layer":
        # Native PDF text layer is normally trustworthy (not OCR) — but a
        # PDF with a broken/missing font ToUnicode map (common on a
        # CamScanner-style date/time stamp baked into the page) extracts as
        # plausible-length but nonsensical Unicode — short, readable-looking,
        # and 100%-confident by the old logic, yet completely unusable.
        # Confirmed on this project's real data: every genuinely-fine native
        # page measured control_char_ratio <= 0.094; every garbled one
        # measured >= 0.125 — a clean, evidence-based separation, not a
        # guessed cutoff.
        ratio = control_char_ratio(text)
        if ratio <= _NATIVE_TEXT_GARBLE_CLEAN_RATIO:
            return 100.0
        issues.append(f"native_text_layer_garbled:{ratio:.3f}")
        if ratio >= _NATIVE_TEXT_GARBLE_BROKEN_RATIO:
            return 10.0
        span = _NATIVE_TEXT_GARBLE_BROKEN_RATIO - _NATIVE_TEXT_GARBLE_CLEAN_RATIO
        return 100.0 - (ratio - _NATIVE_TEXT_GARBLE_CLEAN_RATIO) / span * 90.0
    if raw_conf is None:
        issues.append("missing_confidence_signal")
        return 70.0  # neutral default — documented, not fabricated precision
    if engine == "tesseract":
        return _tesseract_confidence_score(float(raw_conf))
    if engine == "paddleocr":
        return _paddleocr_confidence_score(float(raw_conf))
    # Unknown future engine: trust the raw value linearly rather than guess a curve.
    issues.append(f"uncalibrated_engine:{engine}")
    return max(0.0, min(1.0, float(raw_conf))) * 100.0


def _effective_review_reasons(metadata: dict) -> set[str]:
    return set(metadata.get("review_reasons") or []) - _SOFT_REVIEW_REASONS


def _text_completeness(text: str, metadata: dict, config: QAConfig, issues: list[str]) -> float:
    if is_near_empty(text, config.min_word_count, config.min_char_count):
        issues.append("near_empty_extraction")
        return 10.0
    severe = _effective_review_reasons(metadata)
    if "FRAGMENTED_TEXT" in severe or "SUSPICIOUS_REPETITION" in severe:
        issues.append("fragmented_or_repetitive_text")
        return 35.0
    return 100.0


def _equation_quality_penalty(metadata: dict, issues: list[str]) -> float:
    """Returns a 0-100 'equation health' score (100 = no equations, or all
    GOOD) — a real per-equation signal, used by character_quality and
    structural_integrity, never triggered merely by math being present."""
    blocks = metadata.get("math_equation_blocks") or []
    if not blocks:
        return 100.0
    poor = sum(1 for b in blocks if b.get("math_quality") == "POOR_EXTRACTION")
    needs_review = sum(1 for b in blocks if b.get("math_quality") == "NEEDS_REVIEW")
    n = len(blocks)
    score = 100.0 - (poor / n) * 70.0 - (needs_review / n) * 30.0
    if poor:
        issues.append(f"poor_equation_extraction:{poor}/{n}")
    return max(0.0, score)


def _character_quality(text: str, metadata: dict, config: QAConfig, issues: list[str]) -> float:
    score = 100.0
    ratio = control_char_ratio(text)
    if ratio > config.max_control_char_ratio:
        issues.append(f"control_char_ratio:{ratio:.3f}")
        score -= min(60.0, ratio * 400.0)
    run = longest_repeated_char_run(text)
    if run > config.max_repeated_char_run:
        issues.append(f"repeated_char_run:{run}")
        score -= 30.0
    eq_score = _equation_quality_penalty(metadata, issues)
    if eq_score < 100.0:
        score = min(score, score * 0.7 + eq_score * 0.3)  # min() guards against ever inflating the score
    return max(0.0, score)


def _structural_integrity(metadata: dict, config: QAConfig, issues: list[str]) -> float:
    severe = _effective_review_reasons(metadata)
    if not severe:
        base = 100.0
    elif severe & {"EMPTY_OUTPUT", "NEAR_EMPTY_OUTPUT"}:
        base = 20.0
    elif severe & {"FRAGMENTED_TEXT", "SUSPICIOUS_REPETITION"}:
        issues.append(f"structural_issue:{sorted(severe)}")
        base = 40.0
    else:
        base = 70.0
    blocks = metadata.get("math_equation_blocks") or []
    if blocks:
        review_required = sum(1 for b in blocks if b.get("review_required"))
        if review_required:
            base -= min(20.0, (review_required / len(blocks)) * 20.0)
    return max(0.0, base)


def score_pdf_page(
    record,  # scripts.schemas.ContentRecord
    config: QAConfig,
    dup_tracker: Optional[DuplicateTracker] = None,
) -> QAResult:
    text = record.text or ""
    metadata = record.metadata or {}
    issues: list[str] = []

    # --- critical failures (override the weighted score entirely) ---
    if not text.strip():
        return _critical(config, "empty_extraction", text, metadata)
    if not record.source or not record.content_id:
        return _critical(config, "missing_required_metadata", text, metadata)
    if record.page is None:
        return _critical(config, "missing_page_number", text, metadata)
    ratio = control_char_ratio(text)
    if ratio >= config.max_control_char_ratio_for_rejection:
        return _critical(config, f"severe_character_corruption:{ratio:.2f}", text, metadata)

    checks = {
        "recognition_confidence": _recognition_confidence(text, metadata, issues),
        "text_completeness": _text_completeness(text, metadata, config, issues),
        "character_quality": _character_quality(text, metadata, config, issues),
        "structural_integrity": _structural_integrity(metadata, config, issues),
        "content_consistency": 100.0,
        "metadata_validity": 100.0,
    }
    if dup_tracker is not None and dup_tracker.is_duplicate(record.source_id or record.source, text):
        issues.append("duplicate_content")
        checks["content_consistency"] = config.duplicate_penalty_score

    score = weighted_score(checks, config.weights)
    status = status_from_score(score, config.approved_min, config.pending_min)
    return QAResult(
        status=status,
        score=score,
        qa_version=config.qa_version,
        qa_method=QA_METHOD,
        checks=checks,
        issues=issues,
        content_hash=_content_hash(text, metadata),
    )


def _content_hash(text: str, metadata: dict) -> str:
    return qa_content_hash(
        text,
        (
            ("ocr_confidence", metadata.get("ocr_confidence")),
            ("ocr_engine", metadata.get("ocr_engine")),
            ("page_quality", metadata.get("page_quality")),
        ),
    )


def _critical(config: QAConfig, reason: str, text: str, metadata: dict) -> QAResult:
    zero = {k: 0.0 for k in config.weights}
    return QAResult(
        status="rejected",
        score=0.0,
        qa_version=config.qa_version,
        qa_method=QA_METHOD,
        checks=zero,
        issues=[f"critical:{reason}"],
        critical_failure=reason,
        content_hash=_content_hash(text, metadata),
    )
