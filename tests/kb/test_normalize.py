from __future__ import annotations

import json

from scripts.normalize_content_kb import normalize_record, run
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl


def _note_record(content_id="NOTE_001_PAGE_01", text="Hello world", qa_status=QAStatus.APPROVED, metadata=None):
    return ContentRecord(
        content_id=content_id, content_type=ContentType.PDF_NOTE, course="DSP", topic="Filters",
        source="AnalogFilters.pdf", source_id="ANALOGFILTERS", page=1, text=text,
        processing_status=ProcessingStatus.PROCESSED, qa_status=qa_status, metadata=metadata or {},
    )


def test_normalize_record_preserves_core_provenance():
    record = _note_record(metadata={"page_quality": "GOOD", "ocr_confidence": 0.9})

    doc = normalize_record(record)

    assert doc.doc_id == "NOTE_001_PAGE_01"
    assert doc.source_file == "AnalogFilters.pdf"
    assert doc.source_id == "ANALOGFILTERS"
    assert doc.course == "DSP"
    assert doc.page == 1
    assert doc.ocr_quality == "GOOD"
    assert doc.ocr_confidence == 0.9
    assert doc.raw_metadata == {"page_quality": "GOOD", "ocr_confidence": 0.9}  # never dropped


def test_normalize_record_preserves_equation_blocks():
    record = _note_record(metadata={"math_equation_blocks": [{"text": "x^2", "review_required": True}]})

    doc = normalize_record(record)

    assert doc.math_equation_blocks == [{"text": "x^2", "review_required": True}]


def test_run_discovers_input_files_and_writes_normalized_docs(kb_config):
    write_jsonl([_note_record()], kb_config.ocr_output_dir / "AnalogFilters.jsonl")

    result = run(kb_config)

    assert result["files"] == 1
    assert result["docs"] == 1
    output_path = kb_config.normalized_dir / "normalized_docs.jsonl"
    assert output_path.exists()
    rows = [json.loads(l) for l in output_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["doc_id"] == "NOTE_001_PAGE_01"


def test_run_excludes_rejected_qa_status(kb_config):
    write_jsonl([_note_record(qa_status=QAStatus.REJECTED)], kb_config.ocr_output_dir / "rejected.jsonl")

    result = run(kb_config)

    assert result["docs"] == 0


def test_run_excludes_pending_by_default_but_allows_with_flag(kb_config):
    write_jsonl([_note_record(qa_status=QAStatus.PENDING)], kb_config.ocr_output_dir / "pending.jsonl")

    assert run(kb_config)["docs"] == 0
    assert run(kb_config, allow_pending=True)["docs"] == 1


def test_run_with_sample_limits_to_n_files(kb_config):
    for i in range(3):
        write_jsonl([_note_record(content_id=f"NOTE_{i}")], kb_config.ocr_output_dir / f"file_{i}.jsonl")

    result = run(kb_config, sample=2)

    assert result["files"] == 2
