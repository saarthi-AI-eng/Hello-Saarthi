"""Catalog generation from cleaned/processed JSONL (Phase 16 item 13)."""
from __future__ import annotations

from pathlib import Path

from scripts.build_catalog import build_catalog, print_summary
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl


def _video_record(content_id, source_id, qa=QAStatus.APPROVED) -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.VIDEO_TRANSCRIPT,
        source="lecture_01.mp4",
        source_id=source_id,
        start_time=0.0,
        end_time=5.0,
        text="hello world",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=qa,
        metadata={},
    )


def _note_record(content_id, source_id, page, qa=QAStatus.PENDING) -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.PDF_NOTE,
        source="notes_01.pdf",
        source_id=source_id,
        page=page,
        text="notes text",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=qa,
        metadata={"ocr_confidence": 0.9},
    )


def test_build_catalog_deduplicates_by_content_id_preferring_cleaned(tmp_path, monkeypatch):
    processed_dir = tmp_path / "processed" / "transcripts"
    cleaned_dir = tmp_path / "cleaned" / "transcripts"
    write_jsonl([_video_record("VID001_SEG001", "VID001")], processed_dir / "lecture_01.jsonl")
    # cleaned has the same content_id — should win.
    cleaned_record = _video_record("VID001_SEG001", "VID001")
    cleaned_record = cleaned_record.model_copy(update={"text": "cleaned text"})
    write_jsonl([cleaned_record], cleaned_dir / "lecture_01.jsonl")

    monkeypatch.setattr("scripts.build_catalog.PROCESSED_TRANSCRIPTS_DIR", processed_dir)
    monkeypatch.setattr("scripts.build_catalog.PROCESSED_OCR_DIR", tmp_path / "processed" / "ocr")
    monkeypatch.setattr("scripts.build_catalog.CLEANED_TRANSCRIPTS_DIR", cleaned_dir)
    monkeypatch.setattr("scripts.build_catalog.CLEANED_OCR_DIR", tmp_path / "cleaned" / "ocr")
    monkeypatch.setattr("scripts.build_catalog.RAW_VIDEOS_DIR", tmp_path / "raw" / "videos")
    monkeypatch.setattr("scripts.build_catalog.RAW_NOTES_DIR", tmp_path / "raw" / "notes")
    monkeypatch.setattr("scripts.build_catalog.load_indexed_content_ids", lambda *a, **k: set())

    output_path = tmp_path / "catalog" / "content_catalog.csv"
    rows = build_catalog(output_path)

    assert len(rows) == 1
    assert rows[0]["text_length"] == len("cleaned text")
    assert output_path.exists()


def test_build_catalog_includes_indexed_status(tmp_path, monkeypatch):
    cleaned_dir = tmp_path / "cleaned" / "transcripts"
    write_jsonl([_video_record("VID001_SEG001", "VID001")], cleaned_dir / "lecture_01.jsonl")

    monkeypatch.setattr("scripts.build_catalog.PROCESSED_TRANSCRIPTS_DIR", tmp_path / "processed" / "transcripts")
    monkeypatch.setattr("scripts.build_catalog.PROCESSED_OCR_DIR", tmp_path / "processed" / "ocr")
    monkeypatch.setattr("scripts.build_catalog.CLEANED_TRANSCRIPTS_DIR", cleaned_dir)
    monkeypatch.setattr("scripts.build_catalog.CLEANED_OCR_DIR", tmp_path / "cleaned" / "ocr")
    monkeypatch.setattr("scripts.build_catalog.RAW_VIDEOS_DIR", tmp_path / "raw" / "videos")
    monkeypatch.setattr("scripts.build_catalog.RAW_NOTES_DIR", tmp_path / "raw" / "notes")
    monkeypatch.setattr("scripts.build_catalog.load_indexed_content_ids", lambda *a, **k: {"VID001_SEG001"})

    rows = build_catalog(tmp_path / "catalog" / "content_catalog.csv")

    assert rows[0]["indexed"] == "yes"


def test_build_catalog_creates_discovered_rows_for_unprocessed_raw_files(tmp_path, monkeypatch):
    raw_videos = tmp_path / "raw" / "videos"
    raw_videos.mkdir(parents=True)
    (raw_videos / "lecture_99.mp4").write_bytes(b"fake video bytes")

    monkeypatch.setattr("scripts.build_catalog.PROCESSED_TRANSCRIPTS_DIR", tmp_path / "processed" / "transcripts")
    monkeypatch.setattr("scripts.build_catalog.PROCESSED_OCR_DIR", tmp_path / "processed" / "ocr")
    monkeypatch.setattr("scripts.build_catalog.CLEANED_TRANSCRIPTS_DIR", tmp_path / "cleaned" / "transcripts")
    monkeypatch.setattr("scripts.build_catalog.CLEANED_OCR_DIR", tmp_path / "cleaned" / "ocr")
    monkeypatch.setattr("scripts.build_catalog.RAW_VIDEOS_DIR", raw_videos)
    monkeypatch.setattr("scripts.build_catalog.RAW_NOTES_DIR", tmp_path / "raw" / "notes")
    monkeypatch.setattr("scripts.build_catalog.load_indexed_content_ids", lambda *a, **k: set())

    rows = build_catalog(tmp_path / "catalog" / "content_catalog.csv")

    assert len(rows) == 1
    assert rows[0]["processing_status"] == "discovered"
    assert rows[0]["source"] == "lecture_99.mp4"


def test_print_summary_counts_videos_and_notes(capsys):
    rows = [
        {
            "content_id": "VID001_SEG001",
            "content_type": "video_transcript",
            "source": "lecture_01.mp4",
            "source_id": "VID001",
            "processing_status": "processed",
            "qa_status": "approved",
            "indexed": "yes",
        },
        {
            "content_id": "NOTE001_PAGE01",
            "content_type": "pdf_note",
            "source": "notes_01.pdf",
            "source_id": "NOTE001",
            "processing_status": "processed",
            "qa_status": "pending",
            "indexed": "no",
        },
    ]
    print_summary(rows)
    out = capsys.readouterr().out
    assert "Total videos: 1" in out
    assert "Total pages: 1" in out
    assert "Indexed: 1" in out
    assert "Not indexed: 1" in out
