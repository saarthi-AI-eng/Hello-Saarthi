from __future__ import annotations

from src.content_qa.checks import DuplicateTracker
from src.content_qa.pdf_qa import score_pdf_page
from tests.content_qa.conftest import pdf_record


def test_high_quality_page_is_approved(qa_config):
    record = pdf_record()
    result = score_pdf_page(record, qa_config)
    assert result.status == "approved"
    assert result.score >= qa_config.approved_min
    assert result.critical_failure is None


def test_moderate_tesseract_confidence_is_pending_or_rejected_not_approved(qa_config):
    # Project's own documented finding: Tesseract 0.50-0.70 band can still
    # be garbled handwriting — must not score as confidently as a
    # comparable PaddleOCR confidence.
    record = pdf_record(metadata={
        "ocr_engine": "tesseract",
        "ocr_confidence": 0.55,
        "page_quality": "NEEDS_REVIEW",
        "review_reasons": ["FRAGMENTED_TEXT"],
        "math_equation_blocks": [],
    })
    result = score_pdf_page(record, qa_config)
    assert result.status != "approved"


def test_empty_page_is_rejected_as_critical_failure(qa_config):
    record = pdf_record(text="   ")
    result = score_pdf_page(record, qa_config)
    assert result.status == "rejected"
    assert result.critical_failure == "empty_extraction"
    assert result.score == 0.0


def test_severely_corrupted_text_is_rejected(qa_config):
    record = pdf_record(text="�" * 50 + "a few real words")
    result = score_pdf_page(record, qa_config)
    assert result.status == "rejected"
    assert result.critical_failure is not None


def test_missing_page_number_is_rejected(qa_config):
    record = pdf_record(page=None)
    result = score_pdf_page(record, qa_config)
    assert result.status == "rejected"
    assert result.critical_failure == "missing_page_number"


def test_math_content_alone_is_not_penalized(qa_config):
    """Part 1.2: legitimate mathematical notation must not lower the score
    merely for being flagged MATHEMATICAL_CONTENT by upstream OCR."""
    plain = pdf_record()
    math_page = pdf_record(
        content_id="NOTE_001_PAGE_02",
        text="The transfer function H(s) = 1 / (1 + s/omega_c) describes a first-order low-pass filter.",
        metadata={
            "ocr_engine": "paddleocr",
            "ocr_confidence": 0.95,
            "page_quality": "NEEDS_REVIEW",
            "review_reasons": ["MATHEMATICAL_CONTENT"],
            "math_equation_blocks": [{"math_quality": "GOOD", "review_required": False}],
        },
    )
    plain_result = score_pdf_page(plain, qa_config)
    math_result = score_pdf_page(math_page, qa_config)
    assert math_result.status == "approved"
    assert math_result.score == plain_result.score


def test_poorly_extracted_equation_lowers_character_quality(qa_config):
    record = pdf_record(
        metadata={
            "ocr_engine": "paddleocr",
            "ocr_confidence": 0.9,
            "page_quality": "NEEDS_REVIEW",
            "review_reasons": ["MATHEMATICAL_CONTENT"],
            "math_equation_blocks": [{"math_quality": "POOR_EXTRACTION", "review_required": True}],
        }
    )
    result = score_pdf_page(record, qa_config)
    assert result.checks["character_quality"] < 100.0


def test_good_pages_retained_when_other_pages_in_same_source_fail(qa_config):
    """Part 1.5: page-level, not file-level — a bad page must not drag a
    good page in the same source down."""
    good = pdf_record(content_id="NOTE_001_PAGE_01", page=1)
    bad = pdf_record(content_id="NOTE_001_PAGE_02", page=2, text="")
    good_result = score_pdf_page(good, qa_config)
    bad_result = score_pdf_page(bad, qa_config)
    assert good_result.status == "approved"
    assert bad_result.status == "rejected"


def test_duplicate_page_within_same_source_is_flagged(qa_config):
    tracker = DuplicateTracker()
    first = pdf_record(content_id="NOTE_001_PAGE_01", page=1)
    second = pdf_record(content_id="NOTE_001_PAGE_02", page=2, text=first.text)
    r1 = score_pdf_page(first, qa_config, tracker)
    r2 = score_pdf_page(second, qa_config, tracker)
    assert "duplicate_content" not in r1.issues
    assert "duplicate_content" in r2.issues
    assert r2.checks["content_consistency"] < 100.0


def test_clean_native_text_layer_still_scores_full_confidence(qa_config):
    record = pdf_record(metadata={
        "ocr_engine": "pdf_text_layer", "ocr_confidence": None,
        "page_quality": "GOOD", "review_reasons": [], "math_equation_blocks": [],
    })
    result = score_pdf_page(record, qa_config)
    assert result.checks["recognition_confidence"] == 100.0
    assert result.status == "approved"


def test_garbled_native_text_layer_is_not_blindly_trusted(qa_config):
    """Real bug found on this project's actual data: a PDF with a broken
    font ToUnicode map (a CamScanner-style date/time stamp) extracts as
    plausible-length but nonsensical Unicode via the native text layer —
    previously scored recognition_confidence=100 unconditionally. Real
    example, confirmed control_char_ratio=0.204 on an actually-garbled
    page; every genuinely-fine native page measured <=0.094."""
    garbled_text = ":ĂŶ\x03Ϭϱ͕\x03ϮϬϮϭ͕\x03D\x18\x04\x03>ĞĐ\ndƵĞƐĚĂǇ͕\x03:ĂŶƵĂƌǇ\x03ϱ͕\x03ϮϬϮϭ Ϯ͗ϱϯ\x03WD"
    record = pdf_record(
        text=garbled_text,
        # Exactly the real record's own upstream classification —
        # ingest_notes.py's classify_page_quality() already flagged this
        # (its own, coarser near-empty threshold) before QA ever sees it.
        metadata={
            "ocr_engine": "pdf_text_layer", "ocr_confidence": None,
            "page_quality": "POOR_EXTRACTION", "review_reasons": ["NEAR_EMPTY_OUTPUT", "NO_CONFIDENCE_SCORE"],
            "math_equation_blocks": [],
        },
    )
    result = score_pdf_page(record, qa_config)
    assert result.checks["recognition_confidence"] < 100.0
    assert "native_text_layer_garbled" in ";".join(result.issues)
    assert result.status == "rejected"


def test_scoring_is_deterministic(qa_config):
    record = pdf_record()
    r1 = score_pdf_page(record, qa_config)
    r2 = score_pdf_page(record, qa_config)
    assert r1.score == r2.score
    assert r1.status == r2.status
    assert r1.content_hash == r2.content_hash
