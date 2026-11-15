from __future__ import annotations

import json

import pytest

import scripts.run_content_qa as run_content_qa
from scripts.schemas import ContentRecord, record_to_dict, write_jsonl
from src.content_qa.config import load_qa_config
from tests.content_qa.conftest import pdf_record, video_record


@pytest.fixture
def kb_config(tmp_path):
    from src.knowledge_base.config import KBConfig

    config = KBConfig(data_root=tmp_path / "SaarthiDataTest")
    config.ensure_directories()
    return config


def _write(path, records):
    write_jsonl(records, path)


def test_run_sets_qa_status_and_metadata(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    _write(path, [pdf_record()])

    summary = run_content_qa.run(kb_config)

    assert summary["counts"]["approved"] == 1
    rows = path.read_text(encoding="utf-8").splitlines()
    record = ContentRecord(**json.loads(rows[0]))
    assert record.qa_status.value == "approved"
    assert "qa" in record.metadata
    assert record.metadata["qa"]["score"] >= 85


def test_rerun_is_idempotent_and_skips_unchanged(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    _write(path, [pdf_record()])

    run_content_qa.run(kb_config)
    before = path.read_text(encoding="utf-8")
    summary = run_content_qa.run(kb_config)
    after = path.read_text(encoding="utf-8")

    assert summary["records_skipped_unchanged"] == 1
    assert summary["records_scored"] == 0
    assert before == after


def test_qa_version_bump_triggers_rescoring(kb_config):
    # Explicit, test-local version strings — independent of whatever
    # configs/content_qa.yaml's real qa_version currently is, so this test
    # doesn't silently stop testing anything the next time that file's
    # version is bumped for a real scoring-logic fix.
    path = kb_config.ocr_output_dir / "note.jsonl"
    _write(path, [pdf_record()])
    original = load_qa_config()
    original.qa_version = "test-v1"
    run_content_qa.run(kb_config, qa_config=original)

    bumped = load_qa_config()
    bumped.qa_version = "test-v2"
    summary = run_content_qa.run(kb_config, qa_config=bumped)
    assert summary["records_scored"] == 1
    assert summary["records_skipped_unchanged"] == 0


def test_content_change_triggers_rescoring(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    _write(path, [pdf_record()])
    run_content_qa.run(kb_config)

    edited = pdf_record(text="Completely different text now, after a re-OCR with better quality.")
    _write(path, [edited])
    summary = run_content_qa.run(kb_config)
    assert summary["records_scored"] == 1


def test_force_rescores_even_unchanged(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    _write(path, [pdf_record()])
    run_content_qa.run(kb_config)
    summary = run_content_qa.run(kb_config, force=True)
    assert summary["records_scored"] == 1
    assert summary["records_skipped_unchanged"] == 0


def test_does_not_override_non_automated_qa_metadata(kb_config):
    """Never silently promote/override a decision this module didn't make."""
    path = kb_config.ocr_output_dir / "note.jsonl"
    record = pdf_record()
    record.metadata["qa"] = {"method": "manual_review", "version": "n/a", "score": 50, "content_hash": "x"}
    record.qa_status = record.qa_status.__class__("approved")
    _write(path, [record])

    run_content_qa.run(kb_config)
    rows = path.read_text(encoding="utf-8").splitlines()
    saved = json.loads(rows[0])
    assert saved["metadata"]["qa"]["method"] == "manual_review"


def test_mixed_quality_pdf_pages_scored_independently(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    good = pdf_record(content_id="NOTE_001_PAGE_01", page=1)
    bad = pdf_record(content_id="NOTE_001_PAGE_02", page=2, text="")
    _write(path, [good, bad])

    summary = run_content_qa.run(kb_config)
    assert summary["counts"]["approved"] == 1
    assert summary["counts"]["rejected"] == 1


def test_video_segments_are_scored_too(kb_config):
    path = kb_config.transcripts_dir / "lecture.jsonl"
    _write(path, [video_record()])
    summary = run_content_qa.run(kb_config)
    assert summary["counts"]["approved"] == 1


def test_qa_reports_written(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    _write(path, [pdf_record()])
    run_content_qa.run(kb_config)

    assert (kb_config.qa_reports_dir / "latest_qa_report.jsonl").exists()
    csv_files = list(kb_config.qa_reports_dir.glob("qa_report_*.csv"))
    assert csv_files
