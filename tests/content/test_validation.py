"""Timestamp ordering, duplicate content IDs, and the validation report (Phase 16 items 3, 8, 14)."""
from __future__ import annotations

from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl
from scripts.validate_content import build_report, format_text_report, validate_notes, validate_videos


def _video(content_id, source_id, start, end, text="hello") -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.VIDEO_TRANSCRIPT,
        source="lecture_01.mp4",
        source_id=source_id,
        start_time=start,
        end_time=end,
        text=text,
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={},
    )


def _note(content_id, source_id, page, confidence=None, text="notes") -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.PDF_NOTE,
        source="notes_01.pdf",
        source_id=source_id,
        page=page,
        text=text,
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={"ocr_confidence": confidence},
    )


def test_valid_video_records_pass():
    records = [_video("V1", "VID001", 0.0, 5.0), _video("V2", "VID001", 5.0, 10.0)]
    report = validate_videos(records)
    assert report["invalid"] == 0
    assert report["valid"] == 2


def test_detects_non_monotonic_timestamps():
    records = [_video("V1", "VID001", 10.0, 15.0), _video("V2", "VID001", 5.0, 8.0)]
    report = validate_videos(records)
    assert report["invalid"] == 1
    assert any("monotonically ordered" in e for e in report["errors"])


def test_detects_duplicate_content_ids():
    records = [_video("V1", "VID001", 0.0, 5.0), _video("V1", "VID001", 5.0, 10.0)]
    report = validate_videos(records)
    assert report["duplicate_ids"] == 1
    assert report["invalid"] == 1


def test_detects_missing_timestamps():
    record = ContentRecord(
        content_id="V1",
        content_type=ContentType.VIDEO_TRANSCRIPT,
        source="lecture_01.mp4",
        source_id="VID001",
        text="hello",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
    )
    report = validate_videos([record])
    assert report["missing_timestamps"] == 1
    assert report["invalid"] == 1


def test_detects_start_after_end():
    report = validate_videos([_video("V1", "VID001", 10.0, 5.0)])
    assert report["invalid"] == 1


def test_valid_note_records_pass():
    report = validate_notes([_note("N1", "NOTE001", 1, confidence=0.9)], low_confidence_threshold=0.5)
    assert report["invalid"] == 0
    assert report["valid"] == 1


def test_detects_missing_page_number():
    note = ContentRecord(
        content_id="N1",
        content_type=ContentType.PDF_NOTE,
        source="notes_01.pdf",
        source_id="NOTE001",
        text="hello",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
    )
    report = validate_notes([note], low_confidence_threshold=0.5)
    assert report["missing_page_numbers"] == 1
    assert report["invalid"] == 1


def test_detects_duplicate_page_record():
    records = [_note("N1", "NOTE001", 1), _note("N2", "NOTE001", 1)]
    report = validate_notes(records, low_confidence_threshold=0.5)
    assert report["duplicate_page_records"] == 1


def test_counts_low_confidence_without_marking_invalid():
    report = validate_notes([_note("N1", "NOTE001", 1, confidence=0.2)], low_confidence_threshold=0.5)
    assert report["low_confidence"] == 1
    assert report["invalid"] == 0  # low confidence is a QA signal, not a hard validation failure


def test_confidence_out_of_range_is_invalid():
    report = validate_notes([_note("N1", "NOTE001", 1, confidence=1.5)], low_confidence_threshold=0.5)
    assert report["invalid"] == 1


def test_null_confidence_is_acceptable():
    report = validate_notes([_note("N1", "NOTE001", 1, confidence=None)], low_confidence_threshold=0.5)
    assert report["invalid"] == 0


def test_build_report_end_to_end(tmp_path):
    input_dir = tmp_path / "cleaned"
    write_jsonl([_video("V1", "VID001", 0.0, 5.0)], input_dir / "transcripts" / "lecture_01.jsonl")
    write_jsonl([_note("N1", "NOTE001", 1, confidence=0.9)], input_dir / "ocr" / "notes_01.jsonl")

    report = build_report(input_dir, low_confidence_threshold=0.5)

    assert report["videos"]["total"] == 1
    assert report["notes"]["total"] == 1
    assert report["parse_errors"] == []

    text = format_text_report(report)
    assert "VALIDATION REPORT" in text
    assert "Total: 1" in text
    assert "Total pages: 1" in text


def test_build_report_flags_malformed_lines(tmp_path):
    input_dir = tmp_path / "cleaned" / "transcripts"
    input_dir.mkdir(parents=True)
    (input_dir / "broken.jsonl").write_text(
        '{"content_id": "ok", "content_type": "video_transcript", "source": "a", "text": "hi"}\n'
        '{"content_id": "bad", "content_type": "not_real", "source": "a", "text": "hi"}\n',
        encoding="utf-8",
    )

    report = build_report(tmp_path / "cleaned", low_confidence_threshold=0.5)

    assert len(report["parse_errors"]) == 1
