from __future__ import annotations

import pytest

import scripts.chunk_content_kb as chunk_content_kb
import scripts.normalize_content_kb as normalize_content_kb
import scripts.run_content_qa as run_content_qa
from scripts.schemas import write_jsonl
from tests.content_qa.conftest import pdf_record


@pytest.fixture
def kb_config(tmp_path):
    from src.knowledge_base.config import KBConfig

    config = KBConfig(data_root=tmp_path / "SaarthiDataTest")
    config.ensure_directories()
    return config


def test_pending_excluded_by_default_approved_included(kb_config):
    """Part 1.7's mandatory table: approved always in, pending excluded
    unless --allow-pending, rejected never in."""
    path = kb_config.ocr_output_dir / "note.jsonl"
    # Moderate tesseract confidence + fragmented text -> pending, not approved/rejected.
    pending = pdf_record(content_id="P1", page=1, metadata={
        "ocr_engine": "tesseract", "ocr_confidence": 0.65,
        "page_quality": "POOR_EXTRACTION", "review_reasons": ["FRAGMENTED_TEXT"], "math_equation_blocks": [],
    })
    approved = pdf_record(content_id="P2", page=2)
    write_jsonl([pending, approved], path)

    run_content_qa.run(kb_config)
    result = normalize_content_kb.run(kb_config)
    assert result["docs"] == 1  # only the approved one, by default

    result_allow = normalize_content_kb.run(kb_config, allow_pending=True)
    assert result_allow["docs"] == 2


def test_rejected_never_included_even_with_allow_pending(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    rejected = pdf_record(content_id="P1", page=1, text="")
    approved = pdf_record(content_id="P2", page=2)
    write_jsonl([rejected, approved], path)

    run_content_qa.run(kb_config)
    result = normalize_content_kb.run(kb_config, allow_pending=True)
    assert result["docs"] == 1


def test_reprocess_requested_excluded_even_with_allow_pending(kb_config):
    from scripts.schemas import QAStatus

    path = kb_config.ocr_output_dir / "note.jsonl"
    reprocess = pdf_record(content_id="P1", page=1, qa_status=QAStatus.REPROCESS_REQUESTED)
    approved = pdf_record(content_id="P2", page=2)
    write_jsonl([reprocess, approved], path)

    result = normalize_content_kb.run(kb_config, allow_pending=True)
    assert result["docs"] == 1  # only the approved one — reprocess_requested never included


def test_qa_score_survives_normalization_and_chunking(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([pdf_record()], path)

    run_content_qa.run(kb_config)
    normalize_content_kb.run(kb_config)
    chunk_content_kb.run(kb_config)

    import json

    normalized = [json.loads(l) for l in (kb_config.normalized_dir / "normalized_docs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert normalized[0]["qa_score"] is not None
    assert normalized[0]["qa_score"] >= 85

    chunks = [json.loads(l) for l in (kb_config.chunks_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert chunks
    assert chunks[0]["qa_score"] is not None
