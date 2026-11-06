"""Transcript and OCR cleaning — deterministic artifact removal only (Phase 16 items 5, 6)."""
from __future__ import annotations

from scripts.clean_content import (
    clean_ocr_text,
    clean_ocr_records,
    clean_transcript_records,
    clean_transcript_text,
    detect_repeated_header_footer_lines,
)
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus


def _note_record(content_id, source_id, page, text) -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.PDF_NOTE,
        source="notes_012.pdf",
        source_id=source_id,
        page=page,
        text=text,
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={},
    )


def _video_record(content_id, text, start=0.0, end=1.0) -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.VIDEO_TRANSCRIPT,
        source="lecture_05.mp4",
        source_id="VID_001",
        start_time=start,
        end_time=end,
        text=text,
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={},
    )


# --- Transcript cleaning -----------------------------------------------------

def test_collapses_excessive_whitespace():
    assert clean_transcript_text("hello    world\t\tagain") == "hello world again"


def test_removes_non_speech_tags():
    assert clean_transcript_text("Welcome [Music] to the lecture") == "Welcome to the lecture"


def test_collapses_repeated_words():
    assert clean_transcript_text("this is is is the sampling theorem") == "this is the sampling theorem"


def test_normalizes_space_before_punctuation():
    assert clean_transcript_text("hello , world .") == "hello, world."


def test_preserves_math_notation_in_transcript():
    text = "the signal x[n] equals x(t) sampled, and X(jω) is its transform"
    assert clean_transcript_text(text) == text


def test_clean_transcript_records_preserves_timestamps_and_ids():
    records = [_video_record("VID_001_SEG_001", "hello   world", start=10.0, end=20.0)]
    cleaned = clean_transcript_records(records)
    assert cleaned[0].text == "hello world"
    assert cleaned[0].start_time == 10.0
    assert cleaned[0].end_time == 20.0
    assert cleaned[0].content_id == "VID_001_SEG_001"


# --- OCR cleaning -------------------------------------------------------------

def test_repairs_hyphen_broken_word():
    assert clean_ocr_text("deriv-\native works") == "derivative works"


def test_dedupes_consecutive_duplicate_lines():
    assert clean_ocr_text("line one\nline one\nline two") == "line one\nline two"


def test_preserves_paragraph_boundaries_as_single_blank_line():
    raw = "Section A text\n\n\n\nSection B text"
    assert clean_ocr_text(raw) == "Section A text\n\nSection B text"


def test_preserves_math_notation_in_ocr():
    text = "H(z) is the transfer function\n\nδ(t) is the impulse response"
    assert clean_ocr_text(text) == text


def test_detect_repeated_header_footer_lines_requires_majority_and_min_pages():
    pages = [
        "Signals and Systems — Chapter 3\ncontent page 1",
        "Signals and Systems — Chapter 3\ncontent page 2",
        "Signals and Systems — Chapter 3\ncontent page 3",
    ]
    headers = detect_repeated_header_footer_lines(pages)
    assert "Signals and Systems — Chapter 3" in headers
    assert "content page 1" not in headers


def test_detect_repeated_header_footer_lines_skips_short_document():
    pages = ["Header\ncontent 1", "Header\ncontent 2"]  # below min_page_count=3
    assert detect_repeated_header_footer_lines(pages) == set()


def test_clean_ocr_records_removes_repeated_header_across_pages():
    records = [
        _note_record("NOTE_012_PAGE_01", "NOTE_012", 1, "Header line\n\npage one content"),
        _note_record("NOTE_012_PAGE_02", "NOTE_012", 2, "Header line\n\npage two content"),
        _note_record("NOTE_012_PAGE_03", "NOTE_012", 3, "Header line\n\npage three content"),
    ]
    cleaned = clean_ocr_records(records)
    for record in cleaned:
        assert "Header line" not in record.text
    assert cleaned[0].page == 1  # page boundaries untouched
