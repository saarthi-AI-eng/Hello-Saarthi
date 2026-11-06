"""CER/WER/accuracy metric correctness and the per-page evaluation loop.

No test here calls a real OCR engine — evaluate_engine() is exercised
through a fake engine runner, consistent with the rest of this test suite's
mocked-OCR-boundary philosophy (see tests/content/test_notes_ingestion.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evaluate_ocr import (
    ENGINE_RUNNERS,
    compute_cer,
    compute_exact_line_accuracy,
    compute_exact_word_accuracy,
    compute_wer,
    evaluate_engine,
    load_ground_truth,
)
from scripts.ingest_notes import OCRResult


def test_compute_cer_identical_text_is_zero():
    assert compute_cer("x[n] = sin(t)", "x[n] = sin(t)") == 0.0


def test_compute_cer_counts_character_edits():
    # "cat" -> "cot": 1 substitution out of 3 reference characters
    assert compute_cer("cat", "cot") == pytest.approx(1 / 3)


def test_compute_cer_empty_reference_returns_none_not_zero():
    assert compute_cer("", "anything") is None  # never a misleadingly perfect 0.0


def test_compute_cer_collapses_whitespace_and_newlines():
    """CER must not penalize re-wrapped lines — only real character content differences."""
    assert compute_cer("line one\nline two", "line one line two") == 0.0


def test_compute_wer_is_case_insensitive():
    assert compute_wer("Hello World", "hello world") == 0.0


def test_compute_wer_counts_word_edits():
    # "the cat sat" -> "the dog sat": 1 substitution out of 3 reference words
    assert compute_wer("the cat sat", "the dog sat") == pytest.approx(1 / 3)


def test_compute_wer_empty_reference_returns_none():
    assert compute_wer("", "anything") is None


def test_compute_exact_word_accuracy_is_one_minus_wer():
    reference, hypothesis = "the cat sat", "the dog sat"
    assert compute_exact_word_accuracy(reference, hypothesis) == pytest.approx(1 - compute_wer(reference, hypothesis))


def test_compute_exact_word_accuracy_never_goes_negative():
    """A hypothesis much longer/worse than the reference could push raw (1-WER)
    below zero — accuracy must clamp at 0.0, never report a negative accuracy."""
    assert compute_exact_word_accuracy("a", "completely unrelated garbage text here") == 0.0


def test_compute_exact_line_accuracy_order_insensitive():
    reference = "first line\nsecond line\nthird line"
    hypothesis = "third line\nfirst line\nsecond line"  # reordered, but every line intact
    assert compute_exact_line_accuracy(reference, hypothesis) == 1.0


def test_compute_exact_line_accuracy_partial_match():
    reference = "line a\nline b\nline c"
    hypothesis = "line a\ngarbled line b\nline c"
    assert compute_exact_line_accuracy(reference, hypothesis) == pytest.approx(2 / 3)


def test_compute_exact_line_accuracy_empty_reference_returns_none():
    assert compute_exact_line_accuracy("", "anything") is None


def test_load_ground_truth_missing_file_returns_empty_list(tmp_path):
    assert load_ground_truth(tmp_path / "does_not_exist.jsonl") == []


def test_load_ground_truth_skips_malformed_lines(tmp_path):
    path = tmp_path / "gt.jsonl"
    path.write_text('{"source": "a.pdf", "page": 1, "text": "ok"}\nnot json\n', encoding="utf-8")

    records = load_ground_truth(path)

    assert len(records) == 1
    assert records[0]["text"] == "ok"


def test_evaluate_engine_reports_missing_source_file_without_crashing(tmp_path, monkeypatch):
    import scripts.evaluate_ocr as evaluate_ocr

    monkeypatch.setattr(evaluate_ocr, "REPO_ROOT", tmp_path)  # source path will never exist under here
    monkeypatch.setitem(ENGINE_RUNNERS, "fake", lambda image, dpi: OCRResult(text="x", confidence=0.9, engine="fake", preprocessing=None, psm=None))

    ground_truth = [{"source": "data/raw/notes/missing.pdf", "page": 1, "text": "reference text"}]
    report = evaluate_engine("fake", ground_truth, dpi=300)

    assert report["pages_evaluated"] == 0
    assert report["pages_failed"] == 1
    assert "source file not found" in report["pages"][0]["error"]


def test_evaluate_engine_computes_metrics_for_a_successful_page(tmp_path, monkeypatch):
    import scripts.evaluate_ocr as evaluate_ocr

    monkeypatch.setattr(evaluate_ocr, "REPO_ROOT", tmp_path)
    source = tmp_path / "data" / "raw" / "notes"
    source.mkdir(parents=True)
    (source / "sample.pdf").write_bytes(b"not a real pdf, never opened - render_pdf_page is mocked")

    monkeypatch.setattr(evaluate_ocr, "render_pdf_page", lambda path, idx, dpi: object())
    monkeypatch.setitem(
        ENGINE_RUNNERS, "fake",
        lambda image, dpi: OCRResult(text="the cat sat", confidence=0.9, engine="fake", preprocessing=None, psm=None),
    )

    ground_truth = [{"source": "data/raw/notes/sample.pdf", "page": 1, "text": "the dog sat", "difficulty": "clear"}]
    report = evaluate_engine("fake", ground_truth, dpi=300)

    assert report["pages_evaluated"] == 1
    assert report["pages_failed"] == 0
    assert report["mean_wer"] == pytest.approx(1 / 3, abs=1e-3)  # _mean() rounds to 4dp
    assert report["empty_page_rate"] == 0.0


def test_evaluate_engine_counts_empty_hypothesis_as_empty_page(tmp_path, monkeypatch):
    import scripts.evaluate_ocr as evaluate_ocr

    monkeypatch.setattr(evaluate_ocr, "REPO_ROOT", tmp_path)
    source = tmp_path / "data" / "raw" / "notes"
    source.mkdir(parents=True)
    (source / "sample.pdf").write_bytes(b"")

    monkeypatch.setattr(evaluate_ocr, "render_pdf_page", lambda path, idx, dpi: object())
    monkeypatch.setitem(
        ENGINE_RUNNERS, "fake",
        lambda image, dpi: OCRResult(text="", confidence=None, engine="fake", preprocessing=None, psm=None),
    )

    ground_truth = [{"source": "data/raw/notes/sample.pdf", "page": 1, "text": "some reference text"}]
    report = evaluate_engine("fake", ground_truth, dpi=300)

    assert report["pages_evaluated"] == 1
    assert report["empty_page_rate"] == 1.0
    assert report["mean_cer"] == 1.0  # all reference characters "deleted"


def test_known_engines_include_tesseract_and_paddleocr():
    assert {"tesseract", "paddleocr", "trocr"} <= set(ENGINE_RUNNERS)
