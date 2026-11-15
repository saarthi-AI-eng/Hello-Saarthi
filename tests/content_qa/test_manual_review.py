from __future__ import annotations

import json

import pytest

from scripts.schemas import write_jsonl
from src.content_qa import manual_review
from tests.content_qa.conftest import pdf_record


@pytest.fixture
def kb_config(tmp_path):
    from src.knowledge_base.config import KBConfig

    config = KBConfig(data_root=tmp_path / "SaarthiDataTest")
    config.ensure_directories()
    return config


def _pending(content_id="P1", page=1, **overrides):
    from scripts.schemas import QAStatus

    return pdf_record(content_id=content_id, page=page, qa_status=QAStatus.PENDING, **overrides)


def test_accept_sets_approved_and_records_review_metadata(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    result = manual_review.apply_manual_review(path, "P1", "accept", reviewer_id="r1", reason=None)

    assert result["previous_status"] == "pending"
    assert result["new_status"] == "approved"
    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["qa_status"] == "approved"
    assert saved["metadata"]["manual_review"]["reviewer_id"] == "r1"
    assert saved["metadata"]["manual_review"]["decision"] == "accept"


def test_reject_sets_rejected_with_reason(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    manual_review.apply_manual_review(path, "P1", "reject", reviewer_id="r1", reason="illegible scan")

    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["qa_status"] == "rejected"
    assert saved["metadata"]["manual_review"]["reason"] == "illegible scan"


def test_reprocess_sets_reprocess_requested(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    manual_review.apply_manual_review(path, "P1", "reprocess", reviewer_id="r1", reason="rescan at higher DPI")

    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["qa_status"] == "reprocess_requested"


def test_cannot_review_a_non_pending_record(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([pdf_record(content_id="P1")], path)  # default fixture is already approved-quality, but qa_status explicit:
    # overwrite to approved explicitly to simulate "already decided"
    from scripts.schemas import read_jsonl, QAStatus
    records = list(read_jsonl(path))
    records[0].qa_status = QAStatus.APPROVED
    write_jsonl(records, path)

    with pytest.raises(manual_review.ManualReviewConflict):
        manual_review.apply_manual_review(path, "P1", "accept", reviewer_id="r1")


def test_second_review_of_the_same_record_is_rejected_not_overwritten(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    manual_review.apply_manual_review(path, "P1", "accept", reviewer_id="r1")
    with pytest.raises(manual_review.ManualReviewConflict):
        manual_review.apply_manual_review(path, "P1", "reject", reviewer_id="r2")

    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["qa_status"] == "approved"  # r1's decision stands, r2's was refused


def test_unknown_content_id_raises_not_found(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    with pytest.raises(manual_review.ManualReviewNotFound):
        manual_review.apply_manual_review(path, "DOES_NOT_EXIST", "accept", reviewer_id="r1")


def test_invalid_decision_raises_value_error(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    with pytest.raises(ValueError):
        manual_review.apply_manual_review(path, "P1", "approve_please", reviewer_id="r1")


def test_other_records_in_the_same_file_are_untouched(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending("P1", page=1), _pending("P2", page=2)], path)

    manual_review.apply_manual_review(path, "P1", "accept", reviewer_id="r1")

    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["qa_status"] == "approved"
    assert rows[1]["qa_status"] == "pending"  # untouched


def test_list_pending_items_only_returns_pending(kb_config):
    from scripts.schemas import QAStatus

    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([
        _pending("P1", page=1),
        pdf_record(content_id="P2", page=2, qa_status=QAStatus.APPROVED),
        pdf_record(content_id="P3", page=3, qa_status=QAStatus.REJECTED),
    ], path)

    items = manual_review.list_pending_items(kb_config)

    assert [i["content_id"] for i in items] == ["P1"]
    assert items[0]["source_jsonl_path"] == str(path)


def test_get_record_detail_returns_full_record(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    record = manual_review.get_record_detail(path, "P1")
    assert record.content_id == "P1"
    assert record.text


def test_accept_with_edited_text_updates_text_and_preserves_original(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    original = _pending()
    write_jsonl([original], path)

    manual_review.apply_manual_review(path, "P1", "accept", reviewer_id="r1", edited_text="Corrected text.")

    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["text"] == "Corrected text."
    assert saved["metadata"]["manual_review"]["edited"] is True
    assert saved["metadata"]["manual_review"]["original_text"] == original.text


def test_edited_text_identical_to_original_is_not_flagged_as_edited(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    original = _pending()
    write_jsonl([original], path)

    result = manual_review.apply_manual_review(path, "P1", "accept", reviewer_id="r1", edited_text=original.text)

    assert result["edited"] is False
    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["metadata"]["manual_review"]["original_text"] is None


def test_edit_is_saved_even_when_rejecting(kb_config):
    path = kb_config.ocr_output_dir / "note.jsonl"
    write_jsonl([_pending()], path)

    manual_review.apply_manual_review(path, "P1", "reject", reviewer_id="r1", edited_text="Fixed but still rejected.")

    saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert saved["text"] == "Fixed but still rejected."
    assert saved["qa_status"] == "rejected"


def test_build_review_hints_surfaces_equation_second_opinion(kb_config):
    record = _pending(metadata={
        "math_equation_blocks": [
            {"normalized_text": "1+E", "second_opinion_text": "1+6", "math_quality": "POOR_EXTRACTION", "review_required": True},
            {"normalized_text": "x=1", "second_opinion_text": "x=1", "math_quality": "GOOD", "review_required": False},
        ],
    })
    hints = manual_review.build_review_hints(record)
    assert hints["equation_suggestions"] == [{"original": "1+E", "suggestion": "1+6", "quality": "POOR_EXTRACTION"}]


def test_build_review_hints_surfaces_line_confidences_when_present(kb_config):
    record = _pending(metadata={
        "ocr_lines": [{"text": "hello", "confidence": 0.95}, {"text": "wrld", "confidence": 0.3}],
    })
    hints = manual_review.build_review_hints(record)
    assert hints["line_confidences"] == [{"text": "hello", "confidence": 0.95}, {"text": "wrld", "confidence": 0.3}]


def test_build_review_hints_empty_when_no_signals(kb_config):
    record = _pending()
    hints = manual_review.build_review_hints(record)
    assert hints == {"line_confidences": [], "equation_suggestions": []}


def test_render_source_page_image_rejects_non_pdf_content(kb_config):
    from tests.content_qa.conftest import video_record

    with pytest.raises(manual_review.ManualReviewError, match="PDF"):
        manual_review.render_source_page_image(video_record())


def test_render_source_page_image_raises_not_found_for_missing_pdf(kb_config, monkeypatch, tmp_path):
    import scripts.content_common as content_common

    monkeypatch.setattr(content_common, "RAW_NOTES_DIR", tmp_path / "does_not_exist")
    record = _pending()
    record.source = "missing.pdf"

    with pytest.raises(manual_review.ManualReviewNotFound):
        manual_review.render_source_page_image(record)
