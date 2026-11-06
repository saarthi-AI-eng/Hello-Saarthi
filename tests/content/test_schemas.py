"""Canonical schema validation and JSONL round-tripping (Phase 16 item 1)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from scripts.schemas import (
    ContentRecord,
    ContentType,
    ProcessingStatus,
    QAStatus,
    read_jsonl,
    record_from_dict,
    record_to_dict,
    validate_record,
    write_jsonl,
)


def _make_record(**overrides) -> ContentRecord:
    data = dict(
        content_id="VID_001_SEG_001",
        content_type=ContentType.VIDEO_TRANSCRIPT,
        course="Signals and Systems",
        topic="Fourier Transform",
        source="lecture_05.mp4",
        source_id="VID_001",
        lecture="Lecture 05",
        page=None,
        start_time=10.0,
        end_time=20.0,
        text="hello world",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={"language": "en"},
    )
    data.update(overrides)
    return ContentRecord(**data)


def test_minimal_valid_record_parses():
    record = validate_record(
        {"content_id": "X", "content_type": "video_transcript", "source": "a.mp4", "text": "hi"}
    )
    assert record.processing_status == ProcessingStatus.DISCOVERED
    assert record.qa_status == QAStatus.PENDING
    assert record.metadata == {}


def test_unknown_content_type_rejected():
    with pytest.raises(ValidationError):
        validate_record({"content_id": "X", "content_type": "not_a_real_type", "source": "a", "text": "hi"})


def test_unknown_processing_status_rejected():
    with pytest.raises(ValidationError):
        validate_record(
            {
                "content_id": "X",
                "content_type": "video_transcript",
                "source": "a",
                "text": "hi",
                "processing_status": "bogus",
            }
        )


def test_page_must_be_positive():
    with pytest.raises(ValidationError):
        validate_record({"content_id": "X", "content_type": "pdf_note", "source": "a.pdf", "text": "hi", "page": 0})


def test_record_to_dict_and_back_roundtrips():
    record = _make_record()
    as_dict = record_to_dict(record)
    assert as_dict["content_type"] == "video_transcript"  # enum serialized as plain string
    restored = record_from_dict(as_dict)
    assert restored == record


def test_write_and_read_jsonl_roundtrip(tmp_path):
    records = [_make_record(content_id=f"VID_001_SEG_{i:03d}") for i in range(3)]
    path = tmp_path / "out.jsonl"
    count = write_jsonl(records, path)
    assert count == 3

    read_back = list(read_jsonl(path))
    assert [r.content_id for r in read_back] == [r.content_id for r in records]
    assert read_back[0] == records[0]


def test_read_jsonl_raises_with_line_number_on_malformed_record(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"content_id": "ok", "content_type": "video_transcript", "source": "a", "text": "hi"}\n'
                     '{"content_id": "bad", "content_type": "nope", "source": "a", "text": "hi"}\n',
                     encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.jsonl:2"):
        list(read_jsonl(path))


def test_read_jsonl_skip_invalid_omits_bad_lines(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"content_id": "ok", "content_type": "video_transcript", "source": "a", "text": "hi"}\n'
                     '{"content_id": "bad", "content_type": "nope", "source": "a", "text": "hi"}\n',
                     encoding="utf-8")
    records = list(read_jsonl(path, skip_invalid=True))
    assert len(records) == 1
    assert records[0].content_id == "ok"
