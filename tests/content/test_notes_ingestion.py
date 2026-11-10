"""OCR confidence handling and PDF native-text-layer detection (Phase 16 item 7).

Never requires a real Tesseract binary or the pytesseract package — OCR is
exercised through a fake module injected into sys.modules.
"""
from __future__ import annotations

import sys

import pytest
from PIL import Image

from scripts.ingest_notes import (
    _derive_note_id,
    _resolve_tesseract_cmd,
    extract_pdf_native_text,
    get_pdf_page_count,
    ocr_image,
    process_pdf,
    resolve_metadata,
)


def _make_simple_pdf(text: str) -> bytes:
    """Minimal valid single-page PDF with an extractable text layer (no reportlab needed)."""
    content_stream = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET"
    content_len = len(content_stream)
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font "
        "/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        f"4 0 obj\n<< /Length {content_len} >>\nstream\n"
        f"{content_stream}\nendstream\nendobj\n"
        "xref\n0 5\n"
        "0000000000 65535 f \n"
        "0000000009 00000 n \n"
        "0000000058 00000 n \n"
        "0000000115 00000 n \n"
        "0000000266 00000 n \n"
        "trailer\n<< /Size 5 /Root 1 0 R >>\n"
        "startxref\n0\n%%EOF"
    )
    return pdf.encode("latin-1")


class _FakeOutput:
    DICT = "dict"


class _FakeTesseractNotFoundError(Exception):
    pass


class _FakeInnerPytesseractModule:
    """Stands in for the `pytesseract.pytesseract` submodule (holds tesseract_cmd)."""

    def __init__(self, tesseract_cmd="tesseract"):
        self.tesseract_cmd = tesseract_cmd


class _FakePytesseractModule:
    Output = _FakeOutput
    TesseractNotFoundError = _FakeTesseractNotFoundError

    def __init__(self, text="x[n] = sin(t)", confs=("95", "-1", "80"), tesseract_cmd="tesseract", raise_not_found=False):
        self._text = text
        self._confs = confs
        self._raise_not_found = raise_not_found
        self.pytesseract = _FakeInnerPytesseractModule(tesseract_cmd)

    def image_to_string(self, image, config=None):
        if self._raise_not_found:
            raise self.TesseractNotFoundError()
        return self._text

    def image_to_data(self, image, config=None, output_type=None):
        return {"conf": list(self._confs)}


@pytest.fixture
def fake_pytesseract(monkeypatch):
    fake = _FakePytesseractModule()
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    return fake


def test_derive_note_id_from_filename():
    assert _derive_note_id("Notes 012!!") == "NOTES_012"


def test_resolve_metadata_never_invents_course_or_topic(tmp_path):
    note_path = tmp_path / "notes_012.pdf"
    note_path.write_bytes(b"")

    meta = resolve_metadata(note_path, cli_course=None, cli_topic=None, cli_note_id=None)

    assert meta["course"] is None
    assert meta["topic"] is None
    assert meta["note_id"] == "NOTES_012"


def test_ocr_image_raises_clear_error_when_pytesseract_missing(monkeypatch):
    # pytesseract is an optional dependency. Simulate it not being installed
    # regardless of the real test-machine state, by blocking only that one
    # import name (everything else still imports normally).
    monkeypatch.delitem(sys.modules, "pytesseract", raising=False)
    real_import = __import__

    def _blocked_import(name, *args, **kwargs):
        if name == "pytesseract":
            raise ImportError("No module named 'pytesseract' (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked_import)

    with pytest.raises(RuntimeError, match="pytesseract is not installed"):
        ocr_image(Image.new("RGB", (10, 10), color="white"), preprocess=False)


def test_ocr_image_wraps_tesseract_binary_not_found_clearly(monkeypatch):
    # pytesseract *is* importable here, but the tesseract binary itself is
    # missing/unresolvable — this is the failure mode you actually hit
    # ("pytesseract is installed, but tesseract is not installed or not in
    # PATH"). It must be caught and wrapped with actionable guidance, not
    # leak pytesseract's raw exception.
    fake = _FakePytesseractModule(raise_not_found=True)
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("scripts.ingest_notes._TESSERACT_WINDOWS_CANDIDATES", [])
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    with pytest.raises(RuntimeError, match="TESSERACT_CMD"):
        ocr_image(Image.new("RGB", (10, 10), color="white"), preprocess=False)


def test_resolve_tesseract_cmd_env_var_always_wins(monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", r"D:\custom\tesseract.exe")
    fake = _FakePytesseractModule()

    _resolve_tesseract_cmd(fake)

    assert fake.pytesseract.tesseract_cmd == r"D:\custom\tesseract.exe"


def test_resolve_tesseract_cmd_leaves_working_path_alone(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: r"C:\somewhere\tesseract.exe")
    fake = _FakePytesseractModule()

    _resolve_tesseract_cmd(fake)

    assert fake.pytesseract.tesseract_cmd == "tesseract"  # untouched — already resolvable


def test_resolve_tesseract_cmd_falls_back_to_known_windows_install_location(monkeypatch, tmp_path):
    fake_exe = tmp_path / "tesseract.exe"
    fake_exe.write_bytes(b"")

    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setattr("scripts.ingest_notes._TESSERACT_WINDOWS_CANDIDATES", [str(fake_exe)])
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    fake = _FakePytesseractModule()

    _resolve_tesseract_cmd(fake)

    assert fake.pytesseract.tesseract_cmd == str(fake_exe)


def test_resolve_tesseract_cmd_checks_localappdata_install_location(monkeypatch, tmp_path):
    install_dir = tmp_path / "Programs" / "Tesseract-OCR"
    install_dir.mkdir(parents=True)
    fake_exe = install_dir / "tesseract.exe"
    fake_exe.write_bytes(b"")

    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setattr("scripts.ingest_notes._TESSERACT_WINDOWS_CANDIDATES", [])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    fake = _FakePytesseractModule()

    _resolve_tesseract_cmd(fake)

    assert fake.pytesseract.tesseract_cmd == str(fake_exe)


def test_ocr_image_computes_aggregate_confidence(fake_pytesseract):
    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.text == "x[n] = sin(t)"  # math notation untouched
    # mean of valid (non-negative) confidences [95, 80] / 100 = 0.875
    assert result.confidence == pytest.approx(0.875)
    assert result.engine == "tesseract"
    assert result.preprocessing == "original"
    assert result.psm in (6, 4, 11)


def test_ocr_image_confidence_is_none_when_no_valid_scores(monkeypatch):
    fake = _FakePytesseractModule(confs=("-1", "-1"))
    monkeypatch.setitem(sys.modules, "pytesseract", fake)

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.confidence is None  # never invented


def _psm_marker(psm: int) -> str:
    """Config strings now carry --oem/-l/-c flags too; match on the psm token specifically."""
    return f"--psm {psm}"


def test_ocr_image_tries_multiple_psm_modes_and_picks_best_confidence(monkeypatch):
    """A variant/mode that yields higher confidence should win, even if tried later."""
    from scripts.ingest_notes import _OCR_PSM_MODES

    calls = []

    class _VaryingFake(_FakePytesseractModule):
        def image_to_string(self, image, config=None):
            calls.append(config)
            if _psm_marker(_OCR_PSM_MODES[-1]) in (config or ""):
                return "the best attempt"
            return "a worse attempt"

        def image_to_data(self, image, config=None, output_type=None):
            if _psm_marker(_OCR_PSM_MODES[-1]) in (config or ""):
                return {"conf": ["99", "98"]}
            return {"conf": ["20", "10"]}

    fake = _VaryingFake()
    monkeypatch.setitem(sys.modules, "pytesseract", fake)

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.text == "the best attempt"
    assert result.confidence == pytest.approx(0.985)
    assert result.psm == _OCR_PSM_MODES[-1]
    assert len(calls) == len(_OCR_PSM_MODES)  # every psm mode was actually tried (single "original" variant, preprocess=False)


def test_ocr_image_config_includes_oem_and_preserve_spacing_no_whitelist(monkeypatch):
    """Requirement: LSTM engine mode + preserved inter-word spacing, and NEVER a
    character whitelist (which could silently strip math symbols like π, ω, ∑)."""
    captured_configs = []

    class _CapturingFake(_FakePytesseractModule):
        def image_to_string(self, image, config=None):
            captured_configs.append(config)
            return self._text

    fake = _CapturingFake()
    monkeypatch.setitem(sys.modules, "pytesseract", fake)

    ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert captured_configs  # at least one attempt ran
    for config in captured_configs:
        assert "--oem 1" in config
        assert "preserve_interword_spaces=1" in config
        assert "tessedit_char_whitelist" not in config


def test_ocr_image_never_prefers_confident_but_empty_attempt_over_real_text(monkeypatch):
    """Regression test: Tesseract can report a high confidence score for an
    attempt whose recognized text collapses to empty after cleanup (stray
    symbols/whitespace). That must never beat a different attempt that
    actually recovered real (if messy, lower-confidence) text — this was
    the bug that produced empty pages with ocr_confidence=0.95."""
    from scripts.ingest_notes import _OCR_PSM_MODES

    class _EmptyButConfidentFake(_FakePytesseractModule):
        def image_to_string(self, image, config=None):
            if _psm_marker(_OCR_PSM_MODES[0]) in (config or ""):
                return "   \n\n  "  # collapses to empty after _light_clean
            return "messy but real text"

        def image_to_data(self, image, config=None, output_type=None):
            if _psm_marker(_OCR_PSM_MODES[0]) in (config or ""):
                return {"conf": ["95", "95"]}  # deceptively high confidence for junk
            return {"conf": ["30", "25"]}  # lower confidence, but real text

    fake = _EmptyButConfidentFake()
    monkeypatch.setitem(sys.modules, "pytesseract", fake)

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.text == "messy but real text"
    assert result.confidence == pytest.approx(0.275)


def test_pdf_native_text_layer_used_without_ocr(tmp_path):
    pdf_path = tmp_path / "notes_012.pdf"
    pdf_path.write_bytes(_make_simple_pdf("Sampling theorem states that"))

    assert get_pdf_page_count(pdf_path) == 1
    text = extract_pdf_native_text(pdf_path, 0)
    assert "Sampling" in text


def test_process_pdf_never_skips_a_page_even_when_ocr_is_empty(tmp_path, monkeypatch):
    """Regression test: a page whose OCR comes back empty must still appear in the
    output JSONL, flagged low_confidence — never silently dropped (this was the bug
    behind FFT-Notes-images-3.pdf losing pages 1 and 3)."""
    import scripts.ingest_notes as ingest_notes

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"")  # never actually opened — get_pdf_page_count/render_pdf_page are mocked below

    monkeypatch.setattr(ingest_notes, "get_pdf_page_count", lambda path: 2)
    monkeypatch.setattr(ingest_notes, "extract_pdf_native_text", lambda path, idx: "")  # both pages are scanned
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())

    def _fake_ocr_image(image, preprocess=True):
        from scripts.ingest_notes import OCRResult

        return OCRResult(text="", confidence=None, engine="tesseract", preprocessing="grayscale_clahe", psm=6)

    monkeypatch.setattr(ingest_notes, "ocr_image", _fake_ocr_image)

    meta = {"note_id": "FFT_NOTES", "course": "DSP", "topic": None}
    records = ingest_notes.process_pdf(pdf_path, meta, only_page=None, dpi=350, preprocess=True)

    assert len(records) == 2  # both pages present, not skipped
    assert [r.page for r in records] == [1, 2]
    assert all(r.text == "" for r in records)
    assert all(r.metadata["low_confidence"] is True for r in records)


# --- page-level checkpointing (--resume) ------------------------------------

def test_process_pdf_with_checkpoint_writes_each_page_incrementally(tmp_path, monkeypatch):
    """Each page is appended to checkpoint_path as it completes, not only
    returned/written in bulk at the end — so a crash after page 1 still
    leaves page 1 on disk."""
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult
    from scripts.schemas import read_jsonl

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"")
    checkpoint_path = tmp_path / "out.jsonl"

    monkeypatch.setattr(ingest_notes, "get_pdf_page_count", lambda path: 3)
    monkeypatch.setattr(ingest_notes, "extract_pdf_native_text", lambda path, idx: "")
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())

    seen_pages = []

    def _fake_ocr_image(image, preprocess=True):
        return OCRResult(text=f"page text {len(seen_pages)}", confidence=0.9, engine="tesseract", preprocessing=None, psm=6)

    monkeypatch.setattr(ingest_notes, "ocr_image", _fake_ocr_image)

    meta = {"note_id": "N", "course": None, "topic": None}
    ingest_notes.process_pdf(pdf_path, meta, only_page=None, dpi=350, preprocess=True, checkpoint_path=checkpoint_path)

    on_disk = list(read_jsonl(checkpoint_path))
    assert len(on_disk) == 3
    assert [r.page for r in on_disk] == [1, 2, 3]


def test_process_pdf_resumes_from_existing_checkpoint_without_reprocessing(tmp_path, monkeypatch):
    """A page already present in checkpoint_path (from a prior, interrupted
    run) is reused, not reprocessed — the core of --resume."""
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult
    from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"")
    checkpoint_path = tmp_path / "out.jsonl"

    # Simulate a prior run that completed page 1 only.
    write_jsonl(
        [
            ContentRecord(
                content_id="N_PAGE_01", content_type=ContentType.PDF_NOTE, course=None, topic=None,
                source="scanned.pdf", source_id="N", page=1, text="already done page 1",
                processing_status=ProcessingStatus.PROCESSED, qa_status=QAStatus.PENDING,
                metadata={"ocr_engine": "tesseract"},
            )
        ],
        checkpoint_path,
    )

    monkeypatch.setattr(ingest_notes, "get_pdf_page_count", lambda path: 2)
    monkeypatch.setattr(ingest_notes, "extract_pdf_native_text", lambda path, idx: "")
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())

    reprocessed_pages = []

    def _fake_ocr_image(image, preprocess=True):
        reprocessed_pages.append(image)
        return OCRResult(text="freshly processed page 2", confidence=0.9, engine="tesseract", preprocessing=None, psm=6)

    monkeypatch.setattr(ingest_notes, "ocr_image", _fake_ocr_image)

    meta = {"note_id": "N", "course": None, "topic": None}
    records = ingest_notes.process_pdf(pdf_path, meta, only_page=None, dpi=350, preprocess=True, checkpoint_path=checkpoint_path)

    assert len(records) == 2
    assert records[0].text == "already done page 1"  # reused, not reprocessed
    assert records[1].text == "freshly processed page 2"
    assert len(reprocessed_pages) == 1  # only page 2 actually went through OCR


def test_process_note_file_resume_flag_enables_checkpointing(tmp_path, monkeypatch):
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"")
    output_dir = tmp_path / "out"

    monkeypatch.setattr(ingest_notes, "get_pdf_page_count", lambda path: 1)
    monkeypatch.setattr(ingest_notes, "extract_pdf_native_text", lambda path, idx: "")
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda image, preprocess=True: OCRResult(text="x", confidence=0.9, engine="tesseract", preprocessing=None, psm=6),
    )

    captured_checkpoint = {}
    real_process_pdf = ingest_notes.process_pdf

    def _spy_process_pdf(*args, **kwargs):
        captured_checkpoint["checkpoint_path"] = kwargs.get("checkpoint_path")
        return real_process_pdf(*args, **kwargs)

    monkeypatch.setattr(ingest_notes, "process_pdf", _spy_process_pdf)

    ingest_notes.process_note_file(pdf_path, output_dir, None, 350, True, None, None, None, resume=True)

    assert captured_checkpoint["checkpoint_path"] == output_dir / "scanned.jsonl"


def test_process_note_file_default_does_not_checkpoint(tmp_path, monkeypatch):
    """resume defaults to False — existing non-checkpointed behavior unchanged."""
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"")
    output_dir = tmp_path / "out"

    monkeypatch.setattr(ingest_notes, "get_pdf_page_count", lambda path: 1)
    monkeypatch.setattr(ingest_notes, "extract_pdf_native_text", lambda path, idx: "")
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda image, preprocess=True: OCRResult(text="x", confidence=0.9, engine="tesseract", preprocessing=None, psm=6),
    )

    captured_checkpoint = {}
    real_process_pdf = ingest_notes.process_pdf

    def _spy_process_pdf(*args, **kwargs):
        captured_checkpoint["checkpoint_path"] = kwargs.get("checkpoint_path")
        return real_process_pdf(*args, **kwargs)

    monkeypatch.setattr(ingest_notes, "process_pdf", _spy_process_pdf)

    ingest_notes.process_note_file(pdf_path, output_dir, None, 350, True, None, None, None)

    assert captured_checkpoint["checkpoint_path"] is None


def test_process_pdf_native_text_page_has_null_confidence(tmp_path):
    pdf_path = tmp_path / "notes_012.pdf"
    pdf_path.write_bytes(_make_simple_pdf("Sampling theorem states that x[n] converges"))
    meta = {"note_id": "NOTES_012", "course": "Signals and Systems", "topic": "Sampling"}

    records = process_pdf(pdf_path, meta, only_page=None, dpi=150, preprocess=False)

    assert len(records) == 1
    assert records[0].content_id == "NOTES_012_PAGE_01"
    assert records[0].page == 1
    assert records[0].metadata["ocr_engine"] == "pdf_text_layer"
    assert records[0].metadata["ocr_method"] == "pdf_text_layer"
    assert records[0].metadata["ocr_confidence"] is None  # not OCR — never fabricate a number
    assert records[0].metadata["confidence_tier"] == "native"
    assert records[0].metadata["preprocessing"] is None
    assert records[0].metadata["psm"] is None


# --- scanner-app watermark detection -----------------------------------------
# Regression tests for a real, measured bug found in this project's own
# expanded raw-data set: 3 CamScanner-scanned PDFs (~39 pages) stamp
# "Scanned with CamScanner" into every page's native text layer, which is
# >= _MIN_NATIVE_TEXT_CHARS — the native-text-layer shortcut would have
# stored that watermark as the page's entire content and never run OCR,
# silently losing all the real handwritten notes.

def test_strip_known_watermarks_removes_camscanner_stamp():
    from scripts.ingest_notes import _strip_known_watermarks

    assert _strip_known_watermarks("Scanned with CamScanner\n") == ""


def test_strip_known_watermarks_preserves_real_text_around_a_watermark():
    from scripts.ingest_notes import _strip_known_watermarks

    assert _strip_known_watermarks("Scanned with CamScanner\nreal content here") == "real content here"


def test_strip_known_watermarks_leaves_ordinary_text_untouched():
    from scripts.ingest_notes import _strip_known_watermarks

    assert _strip_known_watermarks("Sampling theorem states that x[n] converges") == "Sampling theorem states that x[n] converges"


def test_process_pdf_camscanner_watermark_only_page_triggers_ocr_not_native_shortcut(tmp_path, monkeypatch):
    """The exact real bug: a page whose only 'native text' is a CamScanner
    watermark must be OCR'd, not treated as having real native text."""
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(_make_simple_pdf("Scanned with CamScanner"))  # exactly what real CamScanner PDFs contain

    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())
    ocr_was_called = []

    def _fake_ocr_image(image, preprocess=True):
        ocr_was_called.append(True)
        return OCRResult(text="actual handwritten notes recovered by OCR", confidence=0.9, engine="tesseract", preprocessing=None, psm=6)

    monkeypatch.setattr(ingest_notes, "ocr_image", _fake_ocr_image)

    meta = {"note_id": "N", "course": None, "topic": None}
    records = ingest_notes.process_pdf(pdf_path, meta, only_page=None, dpi=150, preprocess=False)

    assert ocr_was_called  # OCR actually ran — not skipped by the watermark-fooled native-text shortcut
    assert records[0].metadata["ocr_engine"] == "tesseract"  # not "pdf_text_layer"
    assert records[0].text == "actual handwritten notes recovered by OCR"


# --- confidence tiers (requirement: >=0.70 high, 0.50-0.70 moderate, <0.50 low) ---

def test_confidence_tier_thresholds():
    from scripts.ingest_notes import _confidence_tier

    assert _confidence_tier("some text", 0.70) == "high"
    assert _confidence_tier("some text", 0.95) == "high"
    assert _confidence_tier("some text", 0.50) == "moderate"
    assert _confidence_tier("some text", 0.69) == "moderate"
    assert _confidence_tier("some text", 0.49) == "low"
    assert _confidence_tier("some text", 0.0) == "low"
    assert _confidence_tier("some text", None) == "low"  # unverifiable — never assumed acceptable
    assert _confidence_tier("", 0.95) == "low"  # empty text is always low regardless of reported confidence


def test_process_pdf_moderate_confidence_page_is_not_flagged_low(tmp_path, monkeypatch):
    """A 0.55-confidence page is 'moderate', usable — must NOT be lumped in with low_confidence."""
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"")

    monkeypatch.setattr(ingest_notes, "get_pdf_page_count", lambda path: 1)
    monkeypatch.setattr(ingest_notes, "extract_pdf_native_text", lambda path, idx: "")
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda path, idx, dpi: object())
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda image, preprocess=True: OCRResult(text="decent text", confidence=0.55, engine="tesseract", preprocessing="grayscale_clahe", psm=6),
    )

    records = ingest_notes.process_pdf(pdf_path, {"note_id": "N", "course": None, "topic": None}, only_page=None, dpi=350, preprocess=True)

    assert records[0].metadata["confidence_tier"] == "moderate"
    assert records[0].metadata["low_confidence"] is False


# --- preprocessing variants -------------------------------------------------

def test_preprocess_image_variants_includes_untouched_original():
    from scripts.ingest_notes import preprocess_image_variants

    image = Image.new("RGB", (100, 100), color="white")
    variants = preprocess_image_variants(image)

    assert "original" in variants
    assert variants["original"] is image  # literally untouched, not even copied/reconverted
    assert {"grayscale_clahe", "adaptive_threshold", "otsu_threshold", "sharpened"} <= set(variants.keys())


def test_preprocess_image_variants_produce_distinct_images():
    from scripts.ingest_notes import preprocess_image_variants

    image = Image.new("RGB", (100, 100), color="white")
    variants = preprocess_image_variants(image)

    # Each named variant should be its own image object (not aliases of each other).
    ids = {name: id(img) for name, img in variants.items()}
    assert len(set(ids.values())) == len(ids)


# --- region/band detection ---------------------------------------------------

def test_detect_text_bands_finds_separated_bands():
    import numpy as np

    from scripts.ingest_notes import _detect_text_bands

    gray = np.full((200, 100), 255, dtype=np.uint8)  # blank white page
    gray[20:40, 10:90] = 0   # band 1: dark ink
    gray[120:150, 10:90] = 0  # band 2: dark ink, well separated

    bands = _detect_text_bands(gray)

    assert len(bands) == 2
    (y0a, y1a), (y0b, y1b) = bands
    assert y0a < 40 and y1a > 20  # band 1 covers the ink with padding
    assert y0b < 150 and y1b > 120  # band 2 covers the ink with padding
    assert y1a < y0b  # bands don't overlap


def test_detect_text_bands_blank_page_has_no_bands():
    import numpy as np

    from scripts.ingest_notes import _detect_text_bands

    gray = np.full((200, 100), 255, dtype=np.uint8)
    assert _detect_text_bands(gray) == []


def test_ocr_regions_joins_text_and_length_weights_confidence(monkeypatch):
    from scripts.ingest_notes import _ocr_regions

    class _RegionFake(_FakePytesseractModule):
        def image_to_string(self, image, config=None):
            # crop height distinguishes which band this is (short band vs. long band)
            return "short" if image.height == 50 else "a much longer piece of text"

        def image_to_data(self, image, config=None, output_type=None):
            return {"conf": ["90"]} if image.height == 50 else {"conf": ["40"]}

    fake = _RegionFake()
    image = Image.new("RGB", (100, 200), color="white")
    bands = [(0, 50), (100, 180)]  # distinct heights (50 vs 80) so the fake can tell them apart

    text, confidence = _ocr_regions(fake, _FakeOutput, image, bands, psm=6)

    assert "short" in text and "a much longer piece of text" in text
    # length-weighted toward the longer (lower-confidence) region, not a plain 50/50 average
    assert confidence < 0.65


# --- handwriting OCR fallback gating -----------------------------------------

def test_handwriting_fallback_not_attempted_when_env_var_unset(monkeypatch, fake_pytesseract):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.delenv("SAARTHI_HANDWRITING_OCR", raising=False)

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("run_handwriting_ocr must not be called when SAARTHI_HANDWRITING_OCR is unset")

    monkeypatch.setattr(ingest_notes, "run_handwriting_ocr", _should_not_be_called)

    # force a low-confidence Tesseract result so the *only* thing preventing
    # a fallback attempt is the missing env var
    fake_pytesseract._confs = ("10", "10")
    ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)  # must not raise


def test_handwriting_fallback_not_attempted_when_tesseract_confidence_is_high(monkeypatch, fake_pytesseract):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setenv("SAARTHI_HANDWRITING_OCR", "trocr")

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("run_handwriting_ocr must not be called when Tesseract's result is already high-confidence")

    monkeypatch.setattr(ingest_notes, "run_handwriting_ocr", _should_not_be_called)

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)  # fake_pytesseract -> 0.875 confidence

    assert result.confidence == pytest.approx(0.875)


def test_handwriting_fallback_wins_when_it_scores_better(monkeypatch, fake_pytesseract):
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult

    monkeypatch.setenv("SAARTHI_HANDWRITING_OCR", "trocr")
    fake_pytesseract._confs = ("10", "10")  # force Tesseract's result into the "low" tier

    monkeypatch.setattr(
        ingest_notes, "run_handwriting_ocr",
        lambda image, backend, regions=None: OCRResult(
            text="a much better handwriting-model reading", confidence=0.80, engine="trocr", preprocessing=None, psm=None
        ),
    )

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.engine == "trocr"
    assert result.text == "a much better handwriting-model reading"


def test_handwriting_fallback_failure_keeps_tesseract_result(monkeypatch, fake_pytesseract):
    """If the fallback backend/dependency is unavailable, ocr_image must still
    return Tesseract's (low-confidence) result rather than raising."""
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setenv("SAARTHI_HANDWRITING_OCR", "trocr")
    fake_pytesseract._confs = ("10", "10")

    def _raise_missing_dependency(*args, **kwargs):
        raise RuntimeError("transformers/torch not installed")

    monkeypatch.setattr(ingest_notes, "run_handwriting_ocr", _raise_missing_dependency)

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.engine == "tesseract"
    assert result.text == "x[n] = sin(t)"  # Tesseract's own (low-confidence) result, not lost


def test_run_handwriting_ocr_rejects_unknown_backend():
    from scripts.ingest_notes import run_handwriting_ocr

    with pytest.raises(RuntimeError, match="Unknown SAARTHI_HANDWRITING_OCR backend"):
        run_handwriting_ocr(Image.new("RGB", (20, 20)), "not_a_real_backend")


# --- run_light_tesseract (single-attempt fallback, see recognition_router.py) ---

def test_run_light_tesseract_single_attempt_only(monkeypatch, fake_pytesseract):
    from scripts.ingest_notes import run_light_tesseract

    calls = []
    real_image_to_string = fake_pytesseract.image_to_string

    def _counting_image_to_string(image, config=None):
        calls.append(config)
        return real_image_to_string(image, config=config)

    monkeypatch.setattr(fake_pytesseract, "image_to_string", _counting_image_to_string)

    result = run_light_tesseract(Image.new("RGB", (20, 20), color="white"))

    assert len(calls) == 1  # not the 15-20 calls ocr_image()'s full sweep would make
    assert "--psm 6" in calls[0]
    assert result.text == "x[n] = sin(t)"
    assert result.psm == 6
    assert result.preprocessing is None


def test_run_light_tesseract_raises_clear_error_when_pytesseract_missing(monkeypatch):
    from scripts.ingest_notes import run_light_tesseract

    monkeypatch.delitem(sys.modules, "pytesseract", raising=False)
    real_import = __import__

    def _blocked_import(name, *args, **kwargs):
        if name == "pytesseract":
            raise ImportError("No module named 'pytesseract' (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked_import)

    with pytest.raises(RuntimeError, match="pytesseract is not installed"):
        run_light_tesseract(Image.new("RGB", (20, 20), color="white"))


# --- PaddleOCR backend --------------------------------------------------------

def test_run_handwriting_ocr_paddleocr_raises_clear_error_when_missing(monkeypatch):
    """paddleocr/paddlepaddle are optional (not in requirements-content-pipeline.txt —
    see the comment above _get_paddleocr_instance). Simulate them not being
    installed regardless of the real test machine state."""
    from scripts.ingest_notes import run_handwriting_ocr

    monkeypatch.delitem(sys.modules, "paddleocr", raising=False)
    real_import = __import__

    def _blocked_import(name, *args, **kwargs):
        if name == "paddleocr":
            raise ImportError("No module named 'paddleocr' (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked_import)

    with pytest.raises(RuntimeError, match="SAARTHI_HANDWRITING_OCR=paddleocr requires"):
        run_handwriting_ocr(Image.new("RGB", (20, 20), color="white"), "paddleocr")


class _FakePaddleOCRPageResult(dict):
    """Stands in for paddlex.inference.pipelines.ocr.result.OCRResult (dict-like)."""


class _FakePaddleOCRInstance:
    def __init__(self, texts, scores, boxes):
        self._texts = texts
        self._scores = scores
        self._boxes = boxes

    def predict(self, array):
        return [_FakePaddleOCRPageResult(rec_texts=self._texts, rec_scores=self._scores, rec_boxes=self._boxes)]


def test_paddleocr_ocr_image_parses_lines_text_and_confidence(monkeypatch):
    import numpy as np

    import scripts.ingest_notes as ingest_notes

    fake = _FakePaddleOCRInstance(
        texts=["x[n] = sin(t)", "", "second line"],
        scores=[0.9, 0.5, 0.7],
        boxes=np.array([[0, 0, 10, 10], [0, 0, 0, 0], [0, 20, 10, 30]]),
    )
    monkeypatch.setattr(ingest_notes, "_get_paddleocr_instance", lambda lang: fake)

    text, confidence, lines = ingest_notes._paddleocr_ocr_image(Image.new("RGB", (20, 20), color="white"))

    assert text == "x[n] = sin(t)\nsecond line"  # empty line dropped from joined text, math notation untouched
    assert confidence == pytest.approx((0.9 + 0.5 + 0.7) / 3)  # mean of ALL line scores, including the empty line's
    assert len(lines) == 2  # empty line dropped from the per-line list too
    assert lines[0] == {"text": "x[n] = sin(t)", "confidence": 0.9, "bbox": [0, 0, 10, 10]}
    assert lines[1]["text"] == "second line"


def test_paddleocr_ocr_image_no_detections_returns_empty(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    fake = _FakePaddleOCRInstance(texts=[], scores=[], boxes=None)
    monkeypatch.setattr(ingest_notes, "_get_paddleocr_instance", lambda lang: fake)

    text, confidence, lines = ingest_notes._paddleocr_ocr_image(Image.new("RGB", (20, 20), color="white"))

    assert text == ""
    assert confidence is None  # never invented
    assert lines == []


def test_run_handwriting_ocr_paddleocr_builds_ocr_result(monkeypatch):
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import run_handwriting_ocr

    monkeypatch.setitem(sys.modules, "paddleocr", object())  # import check only needs to succeed
    monkeypatch.setattr(
        ingest_notes, "_paddleocr_ocr_image",
        lambda image: ("recognized text", 0.82, [{"text": "recognized text", "confidence": 0.82, "bbox": [0, 0, 1, 1]}]),
    )

    result = run_handwriting_ocr(Image.new("RGB", (20, 20), color="white"), "paddleocr")

    assert result.engine == "paddleocr"
    assert result.text == "recognized text"
    assert result.confidence == 0.82
    assert result.preprocessing is None
    assert result.psm is None
    assert result.lines == [{"text": "recognized text", "confidence": 0.82, "bbox": [0, 0, 1, 1]}]


def test_handwriting_fallback_accepts_paddleocr_backend(monkeypatch, fake_pytesseract):
    """End-to-end through ocr_image(): SAARTHI_HANDWRITING_OCR=paddleocr is gated
    and ranked exactly like the trocr backend (see test_handwriting_fallback_wins_when_it_scores_better)."""
    import scripts.ingest_notes as ingest_notes
    from scripts.ingest_notes import OCRResult

    monkeypatch.setenv("SAARTHI_HANDWRITING_OCR", "paddleocr")
    fake_pytesseract._confs = ("10", "10")  # force Tesseract's result into the "low" tier

    monkeypatch.setattr(
        ingest_notes, "run_handwriting_ocr",
        lambda image, backend, regions=None: OCRResult(
            text="a much better paddleocr reading", confidence=0.80, engine="paddleocr", preprocessing=None, psm=None
        ),
    )

    result = ocr_image(Image.new("RGB", (20, 20), color="white"), preprocess=False)

    assert result.engine == "paddleocr"
    assert result.text == "a much better paddleocr reading"


def test_ocr_page_metadata_includes_ocr_lines_for_paddleocr():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(
        text="hello", confidence=0.9, engine="paddleocr", preprocessing=None, psm=None,
        lines=[{"text": "hello", "confidence": 0.9, "bbox": [0, 0, 5, 5]}],
    )

    _, metadata = _ocr_page_metadata(result, dpi=None)

    assert metadata["ocr_lines"] == [{"text": "hello", "confidence": 0.9, "bbox": [0, 0, 5, 5]}]


def test_ocr_page_metadata_ocr_lines_is_none_for_tesseract():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(text="hello", confidence=0.9, engine="tesseract", preprocessing="original", psm=6)

    _, metadata = _ocr_page_metadata(result, dpi=350)

    assert metadata["ocr_lines"] is None


# ---------------------------------------------------------------------------
# Page-quality classification (independent of engine confidence) — AnalogFilters.pdf
# comparison task: engine confidence was measured to NOT predict correctness
# on this project's real handwritten math pages.
# ---------------------------------------------------------------------------

def test_classify_page_quality_empty_text_is_poor_extraction():
    from scripts.ingest_notes import classify_page_quality

    label, reasons = classify_page_quality("", confidence=0.95)

    assert label == "POOR_EXTRACTION"
    assert "EMPTY_OUTPUT" in reasons


def test_classify_page_quality_near_empty_text_is_poor_extraction_even_with_high_confidence():
    from scripts.ingest_notes import classify_page_quality

    # Real case: AnalogFilters.pdf pages 10/11 — "pol eD" / "" after watermark
    # stripping, but the engine reported confidence 0.86-0.94.
    label, reasons = classify_page_quality("pol eD", confidence=0.94)

    assert label == "POOR_EXTRACTION"
    assert "NEAR_EMPTY_OUTPUT" in reasons


def test_classify_page_quality_detects_suspicious_repetition():
    from scripts.ingest_notes import classify_page_quality

    label, reasons = classify_page_quality("ab" * 30, confidence=0.9)

    assert label == "POOR_EXTRACTION"
    assert "SUSPICIOUS_REPETITION" in reasons


def test_classify_page_quality_detects_fragmented_garbage_text():
    from scripts.ingest_notes import classify_page_quality

    # Real case: AnalogFilters.pdf page 15 — short enough to also trip
    # NEAR_EMPTY_OUTPUT, but genuinely fragmented/non-wordlike either way.
    label, reasons = classify_page_quality("Serf\n\nsHeaee ee Rh PEE,", confidence=0.7362)

    assert label == "POOR_EXTRACTION"
    assert reasons  # flagged for some real reason, not silently passed as GOOD


def test_classify_page_quality_flags_mathematical_content_for_review_not_as_poor():
    from scripts.ingest_notes import classify_page_quality

    text = (
        "Recall the Butterworth lowpass filter magnitude squared response for order N "
        "with cutoff frequency and pass band edge frequency. The relation is "
        "H(omega)^2 = 1 / (1 + epsilon^2 * (omega/omega_p)^2N) for the standard case."
    )
    label, reasons = classify_page_quality(text, confidence=0.9)

    assert "MATHEMATICAL_CONTENT" in reasons
    assert label == "NEEDS_REVIEW"


def test_classify_page_quality_good_plain_text_with_no_issues():
    from scripts.ingest_notes import classify_page_quality

    text = "This is a perfectly ordinary paragraph of recognizable English prose about filters."
    label, reasons = classify_page_quality(text, confidence=0.9)

    assert label == "GOOD"
    assert reasons == []


def test_classify_page_quality_missing_confidence_flags_but_does_not_force_poor():
    from scripts.ingest_notes import classify_page_quality

    text = "This is a perfectly ordinary paragraph of recognizable English prose about filters."
    label, reasons = classify_page_quality(text, confidence=None)

    assert "NO_CONFIDENCE_SCORE" in reasons
    assert label == "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Watermark removal from OCR'd text (not just the native PDF text layer) +
# original-OCR-text preservation.
# ---------------------------------------------------------------------------

def test_ocr_page_metadata_strips_watermark_from_ocr_text():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(
        text="pol eD\n\nScanned with CamScanner", confidence=0.86, engine="tesseract", preprocessing="original", psm=6,
    )

    text, metadata = _ocr_page_metadata(result, dpi=350)

    assert "CamScanner" not in text
    assert "pol eD" in text


def test_ocr_page_metadata_preserves_raw_pre_clean_text_separately():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    raw = "pol eD\n\nScanned with CamScanner"
    result = OCRResult(text=raw, confidence=0.86, engine="tesseract", preprocessing="original", psm=6)

    _, metadata = _ocr_page_metadata(result, dpi=350)

    assert metadata["ocr_text_raw"] == raw


def test_ocr_page_metadata_near_empty_page_gets_visual_content_reference():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(text="pol eD", confidence=0.94, engine="tesseract", preprocessing="original", psm=6)

    _, metadata = _ocr_page_metadata(result, dpi=350)

    assert metadata["visual_content_reference"] is not None
    assert "refer to original PDF" in metadata["visual_content_reference"]


def test_ocr_page_metadata_good_page_has_no_visual_content_reference():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(
        text="This is a perfectly ordinary paragraph of recognizable prose.",
        confidence=0.9, engine="tesseract", preprocessing="original", psm=6,
    )

    _, metadata = _ocr_page_metadata(result, dpi=350)

    assert metadata["visual_content_reference"] is None


def test_ocr_page_metadata_includes_empty_region_lists_by_default():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(text="hello world", confidence=0.9, engine="tesseract", preprocessing="original", psm=6)

    _, metadata = _ocr_page_metadata(result, dpi=350)

    assert metadata["math_regions"] == []
    assert metadata["visual_regions"] == []


# ---------------------------------------------------------------------------
# Opt-in region analysis (SAARTHI_REGION_ANALYSIS=1) — additive only, never
# required, never overwrites the page's primary OCR text.
# ---------------------------------------------------------------------------

def test_region_analysis_disabled_by_default_in_process_pdf(monkeypatch, tmp_path):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.delenv("SAARTHI_REGION_ANALYSIS", raising=False)

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("_analyze_page_regions must not run unless SAARTHI_REGION_ANALYSIS is set")

    monkeypatch.setattr(ingest_notes, "_analyze_page_regions", _should_not_be_called)
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda *a, **k: Image.new("RGB", (20, 20), "white"))
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda *a, **k: ingest_notes.OCRResult(text="some text", confidence=0.9, engine="tesseract", preprocessing=None, psm=6),
    )

    pdf_bytes = _make_simple_pdf("")
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(pdf_bytes)

    records = process_pdf(pdf_path, {"note_id": "X", "course": None, "topic": None}, only_page=1, dpi=300, preprocess=False)
    assert records[0].metadata["math_regions"] == []


def test_region_analysis_failure_degrades_gracefully(monkeypatch, tmp_path):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setenv("SAARTHI_REGION_ANALYSIS", "1")

    def _boom(*args, **kwargs):
        raise RuntimeError("region analysis exploded")

    monkeypatch.setattr(ingest_notes, "_analyze_page_regions", _boom)
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda *a, **k: Image.new("RGB", (20, 20), "white"))
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda *a, **k: ingest_notes.OCRResult(text="some text", confidence=0.9, engine="tesseract", preprocessing=None, psm=6),
    )

    pdf_bytes = _make_simple_pdf("")
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # Must not raise — a broken opt-in analysis must never break the primary page result.
    records = process_pdf(pdf_path, {"note_id": "X", "course": None, "topic": None}, only_page=1, dpi=300, preprocess=False)
    assert records[0].text == "some text"
    assert records[0].metadata["math_regions"] == []
    assert records[0].metadata["visual_regions"] == []


def test_region_analysis_skipped_for_good_quality_pages_even_when_enabled(monkeypatch, tmp_path):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setenv("SAARTHI_REGION_ANALYSIS", "1")

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("_analyze_page_regions must be skipped for a GOOD-quality page")

    monkeypatch.setattr(ingest_notes, "_analyze_page_regions", _should_not_be_called)
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda *a, **k: Image.new("RGB", (20, 20), "white"))
    good_text = "This is a perfectly ordinary paragraph of recognizable English prose about electronic filters and their design."
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda *a, **k: ingest_notes.OCRResult(text=good_text, confidence=0.9, engine="tesseract", preprocessing=None, psm=6),
    )

    pdf_bytes = _make_simple_pdf("")
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(pdf_bytes)

    records = process_pdf(pdf_path, {"note_id": "X", "course": None, "topic": None}, only_page=1, dpi=300, preprocess=False)
    assert records[0].metadata["page_quality"] == "GOOD"
    assert records[0].metadata["math_regions"] == []


# ---------------------------------------------------------------------------
# Conservative spelling correction.
# ---------------------------------------------------------------------------

def test_spelling_correction_applies_high_confidence_fixes():
    from scripts.ingest_notes import apply_spelling_corrections

    text = "Analog filters cheractristic with Butterwoith design at low freqeuency."
    corrected, corrections = apply_spelling_corrections(text)

    assert "characteristic" in corrected
    assert "Butterworth" in corrected  # capitalization preserved
    assert "frequency" in corrected
    assert all(c["applied"] for c in corrections)


def test_spelling_correction_flags_ambiguous_candidate_without_applying_it():
    from scripts.ingest_notes import apply_spelling_corrections

    text = "Reifoim the Conversion from H(s) to H(z)."
    corrected, corrections = apply_spelling_corrections(text)

    # Genuinely ambiguous (could be "Perform" or "Reform") — reported, not silently applied.
    assert "Reifoim" in corrected
    assert any(c["original"] == "Reifoim" and not c["applied"] for c in corrections)


def test_spelling_correction_never_touches_unknown_tokens_including_variable_names():
    from scripts.ingest_notes import apply_spelling_corrections

    text = "H(s) and H(z), with Tn and Rc as variable names, and wp as a parameter."
    corrected, corrections = apply_spelling_corrections(text)

    assert corrected == text
    assert corrections == []


def test_ocr_page_metadata_preserves_three_text_tiers():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    raw = "Analog filters cheractristic.\n\nScanned with CamScanner"
    result = OCRResult(text=raw, confidence=0.9, engine="tesseract", preprocessing="original", psm=6)

    text, metadata = _ocr_page_metadata(result, dpi=350)

    assert metadata["ocr_text_raw"] == raw  # untouched original
    assert "CamScanner" not in metadata["text_uncorrected"]
    assert "cheractristic" in metadata["text_uncorrected"]  # watermark gone, spelling not yet fixed
    assert "characteristic" in text  # final text: watermark gone AND spelling fixed


def test_ocr_page_metadata_strips_watermark_from_ocr_lines():
    from scripts.ingest_notes import OCRResult, _ocr_page_metadata

    result = OCRResult(
        text="hello", confidence=0.9, engine="paddleocr", preprocessing=None, psm=None,
        lines=[
            {"text": "hello", "confidence": 0.9, "bbox": [0, 0, 5, 5]},
            {"text": "Scanned with CamScanner", "confidence": 0.95, "bbox": [0, 10, 50, 15]},
        ],
    )

    _, metadata = _ocr_page_metadata(result, dpi=None)

    assert metadata["ocr_lines"][0]["text"] == "hello"
    assert metadata["ocr_lines"][1]["text"] == ""


# ---------------------------------------------------------------------------
# Region bounding-box correctness — a region whose bbox covers most of the
# page is a full-page candidate, not a localized crop worth a duplicate OCR
# call (AnalogFilters.pdf pages 8, 9, 13, 17 — _detect_text_bands returning
# one giant band on dense handwriting with no blank-row gaps).
# ---------------------------------------------------------------------------

class _FakeRegion:
    def __init__(self, bbox, region_type):
        self.bbox = bbox
        self.region_type = region_type


class _FakeRegionResult:
    def __init__(self, final_text, final_confidence, primary_engine="paddleocr", fallback_invoked=False):
        self.final_text = final_text
        self.final_confidence = final_confidence
        self.primary_engine = primary_engine
        self.fallback_invoked = fallback_invoked


def test_analyze_page_regions_skips_full_page_bbox_without_a_duplicate_ocr_call(monkeypatch):
    import scripts.ingest_notes as ingest_notes
    import scripts.layout_detector as layout_detector
    import scripts.recognition_router as recognition_router

    page_image = Image.new("L", (100, 100), "white")
    full_page_region = _FakeRegion(bbox=(0, 0, 100, 100), region_type="unknown")  # 100% of the page

    monkeypatch.setattr(layout_detector, "detect_regions", lambda image, page_number: ([full_page_region], page_image))

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("recognize_region must not run on a full-page-sized region — it duplicates the primary OCR pass")

    monkeypatch.setattr(recognition_router, "recognize_region", _should_not_be_called)

    math_regions, visual_regions, full_page_candidates = ingest_notes._analyze_page_regions(page_image, 1)

    assert math_regions == []
    assert visual_regions == []
    assert len(full_page_candidates) == 1
    assert full_page_candidates[0]["bbox"] == [0, 0, 100, 100]


def test_analyze_page_regions_keeps_localized_math_region_and_strips_its_watermark(monkeypatch):
    import scripts.ingest_notes as ingest_notes
    import scripts.layout_detector as layout_detector
    import scripts.recognition_router as recognition_router

    page_image = Image.new("L", (100, 100), "white")
    small_region = _FakeRegion(bbox=(10, 10, 30, 30), region_type="mathematical_expression")  # 4% of the page

    monkeypatch.setattr(layout_detector, "detect_regions", lambda image, page_number: ([small_region], page_image))
    monkeypatch.setattr(layout_detector, "refine_region_with_text", lambda *a, **k: None)
    monkeypatch.setattr(
        recognition_router, "recognize_region",
        lambda region, crop: _FakeRegionResult("x^2 + 1\nScanned with CamScanner", 0.8),
    )

    math_regions, visual_regions, full_page_candidates = ingest_notes._analyze_page_regions(page_image, 1)

    assert full_page_candidates == []
    assert len(math_regions) == 1
    assert math_regions[0]["bbox"] == [10, 10, 30, 30]
    assert "CamScanner" not in math_regions[0]["text"]
    assert "x^2 + 1" in math_regions[0]["text"]
    assert math_regions[0]["review_required"] is True


def test_analyze_page_regions_diagram_region_never_gets_recognize_region_called(monkeypatch):
    import scripts.ingest_notes as ingest_notes
    import scripts.layout_detector as layout_detector
    import scripts.recognition_router as recognition_router

    page_image = Image.new("L", (100, 100), "white")
    diagram_region = _FakeRegion(bbox=(5, 5, 20, 20), region_type="diagram")  # small, but a diagram

    monkeypatch.setattr(layout_detector, "detect_regions", lambda image, page_number: ([diagram_region], page_image))

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("diagram/table regions are never guessed via OCR — review-only")

    monkeypatch.setattr(recognition_router, "recognize_region", _should_not_be_called)

    math_regions, visual_regions, full_page_candidates = ingest_notes._analyze_page_regions(page_image, 1)

    assert math_regions == []
    assert len(visual_regions) == 1
    assert visual_regions[0]["region_type"] == "diagram"
    assert visual_regions[0]["review_required"] is True


# ---------------------------------------------------------------------------
# Page-quality classification — generalized checks (not specific to
# AnalogFilters.pdf), per the task's "do not overfit thresholds" instruction.
# ---------------------------------------------------------------------------

def test_classify_page_quality_math_heavy_but_coherent_page_is_needs_review_not_poor():
    from scripts.ingest_notes import classify_page_quality

    text = (
        "The Chebyshev filter response is defined by the equation "
        "H(omega)^2 = 1 / (1 + epsilon^2 * T_N(omega/omega_p)^2) where T_N is "
        "the Nth order Chebyshev polynomial and epsilon relates to the ripple."
    )
    label, reasons = classify_page_quality(text, confidence=0.85)

    assert "MATHEMATICAL_CONTENT" in reasons
    assert label == "NEEDS_REVIEW"


def test_classify_page_quality_single_garbled_formula_line_flags_otherwise_good_page():
    from scripts.ingest_notes import classify_page_quality

    # Mirrors the real AnalogFilters.pdf page 1 case: a long, mostly-correct
    # prose page with one badly garbled formula line buried inside it.
    text = (
        "Analog filters characteristic.\n"
        "Recall the design steps for a digital filter from an analog prototype.\n"
        "Preserving as much of the characteristics as possible throughout.\n"
        "Lowpass Butterworth.\n"
        "1HC2)^2=\n"
        "1+E\n"
        "N is the order of the filter and omega_c is the cutoff frequency."
    )
    label, reasons = classify_page_quality(text, confidence=0.9)

    assert "MATHEMATICAL_CONTENT" in reasons
    assert label == "NEEDS_REVIEW"


def test_classify_page_quality_not_poor_merely_for_long_high_confidence_text():
    from scripts.ingest_notes import classify_page_quality

    text = "A long, perfectly ordinary paragraph of recognizable English prose. " * 5
    label, reasons = classify_page_quality(text, confidence=0.99)

    assert label == "GOOD"


# ---------------------------------------------------------------------------
# Math-specific OCR improvement: context-aware normalization, equation-block
# grouping from existing OCR line bboxes, and math-quality classification.
# ---------------------------------------------------------------------------

def test_normalize_math_text_auto_applies_when_followed_by_bracket():
    from scripts.ingest_notes import normalize_math_text

    normalized, corrections = normalize_math_text("N=10g[1182-1]")

    assert normalized == "N=log[1182-1]"
    assert corrections == [{"original": "10g", "suggested": "log", "confidence": 0.9, "applied": True}]


def test_normalize_math_text_flags_low_confidence_without_applying():
    from scripts.ingest_notes import normalize_math_text

    normalized, corrections = normalize_math_text("loy (g/t)")

    assert "loy" in normalized  # left untouched
    assert corrections and all(not c["applied"] for c in corrections)


def test_normalize_math_text_never_touches_unrelated_tokens():
    from scripts.ingest_notes import normalize_math_text

    text = "H(s) and omega_p and Rc are unrelated variable names."
    normalized, corrections = normalize_math_text(text)

    assert normalized == text
    assert corrections == []


def test_group_math_lines_returns_empty_for_no_candidates():
    from scripts.ingest_notes import _group_math_lines_from_ocr_lines

    lines = [{"text": "This is ordinary prose with no equations at all.", "confidence": 0.9, "bbox": [0, 0, 500, 50]}]
    assert _group_math_lines_from_ocr_lines(lines) == []
    assert _group_math_lines_from_ocr_lines(None) == []
    assert _group_math_lines_from_ocr_lines([]) == []


def test_group_math_lines_groups_adjacent_lines_into_one_block():
    from scripts.ingest_notes import _group_math_lines_from_ocr_lines

    lines = [
        {"text": "N=10g[1182-1]", "confidence": 0.8, "bbox": [100, 100, 500, 150]},
        {"text": "= log (109-1)", "confidence": 0.7, "bbox": [100, 160, 500, 210]},  # gap=10px, same block
    ]
    blocks = _group_math_lines_from_ocr_lines(lines)

    assert len(blocks) == 1
    assert blocks[0]["bbox"] == (100, 100, 500, 210)
    assert "N=10g[1182-1]" in blocks[0]["text"]
    assert "log (109-1)" in blocks[0]["text"]


def test_group_math_lines_splits_distant_lines_into_separate_blocks():
    from scripts.ingest_notes import _group_math_lines_from_ocr_lines

    lines = [
        {"text": "N=10g[1182-1]", "confidence": 0.8, "bbox": [100, 100, 500, 150]},
        {"text": "= log (109-1)", "confidence": 0.7, "bbox": [100, 2000, 500, 2050]},  # far below, separate block
    ]
    blocks = _group_math_lines_from_ocr_lines(lines)

    assert len(blocks) == 2


def test_classify_math_block_quality_not_detected_when_both_empty():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality("", "")

    assert label == "NOT_DETECTED"
    assert "NO_TEXT_RECOGNIZED" in reasons


def test_classify_math_block_quality_flags_hypothesis_disagreement():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality(
        "a long and otherwise perfectly readable equation line written here",
        "a completely different and unrelated second opinion text entirely",
    )

    assert "HYPOTHESIS_DISAGREEMENT" in reasons
    assert label == "NEEDS_REVIEW"


def test_classify_math_block_quality_agreeing_hypotheses_stay_good():
    from scripts.ingest_notes import _classify_math_block_quality

    text = "a long and otherwise perfectly readable equation line written here"
    label, reasons = _classify_math_block_quality(text, text)

    assert label == "GOOD"


# ---------------------------------------------------------------------------
# Refinement: distinguishing empty/incomplete hypotheses from genuine
# disagreement (docs/analogfilters-latest-math-ocr-evaluation.md §7 finding:
# a 90% raw-disagreement rate was uninformative because it conflated these).
# ---------------------------------------------------------------------------

def test_classify_math_block_quality_second_opinion_empty_is_not_disagreement():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality("a perfectly fine primary equation line here", "")

    assert "SECOND_OPINION_EMPTY" in reasons
    assert "HYPOTHESIS_DISAGREEMENT" not in reasons
    assert label == "GOOD"  # informational only — does not by itself demote an otherwise-clean block


def test_classify_math_block_quality_primary_empty_is_severe():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality("", "the second opinion actually found real content here")

    assert "PRIMARY_EMPTY" in reasons
    assert label == "POOR_EXTRACTION"  # the primary is what reaches the page — this is the concerning direction


def test_classify_math_block_quality_both_empty_is_not_detected():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality("", "")

    assert label == "NOT_DETECTED"
    assert reasons == ["NO_TEXT_RECOGNIZED"]


def test_classify_math_block_quality_second_opinion_incomplete_vs_primary():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality(
        "a long and otherwise perfectly readable full equation line here", "short bit",
    )

    assert "SECOND_OPINION_INCOMPLETE" in reasons
    assert "HYPOTHESIS_DISAGREEMENT" not in reasons
    assert label == "NEEDS_REVIEW"


def test_classify_math_block_quality_primary_incomplete_vs_second_opinion():
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality(
        "short bit", "a long and otherwise perfectly readable full equation line here",
    )

    assert "PRIMARY_INCOMPLETE" in reasons
    assert "HYPOTHESIS_DISAGREEMENT" not in reasons
    assert label == "NEEDS_REVIEW"


def test_classify_math_block_quality_never_prefers_longer_hypothesis_as_correct():
    """Incompleteness is reported, never resolved by silently picking one side."""
    from scripts.ingest_notes import _classify_math_block_quality

    label, reasons = _classify_math_block_quality(
        "short bit", "a long and otherwise perfectly readable full equation line here",
    )
    # The function returns only a label + reasons — there is no "winning text" output at all.
    assert isinstance(label, str) and isinstance(reasons, list)


# ---------------------------------------------------------------------------
# Equation grouping safety: max block height / line count, to stop a long
# uninterrupted run of math-dense lines from merging separate derivation
# steps (docs/analogfilters-latest-math-ocr-evaluation.md §4 finding: page
# 14's 11-line, 1894px block covering what used to be 3-4 separate bands).
# ---------------------------------------------------------------------------

def test_group_math_lines_splits_on_max_line_count(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setattr(ingest_notes, "_MATH_BLOCK_MAX_LINES", 3)
    lines = [
        {"text": f"N={i}0g[{i}]", "confidence": 0.8, "bbox": [100, 100 + i * 60, 500, 150 + i * 60]}
        for i in range(6)  # 6 math-dense lines, each close enough to the next to normally merge
    ]
    blocks = ingest_notes._group_math_lines_from_ocr_lines(lines)

    assert len(blocks) >= 2
    assert all(len(b["text"].split("\n")) <= 3 for b in blocks)


def test_group_math_lines_splits_on_max_height(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setattr(ingest_notes, "_MATH_BLOCK_MAX_HEIGHT_PX", 200)
    lines = [
        {"text": "N=10g[1]", "confidence": 0.8, "bbox": [100, 100, 500, 150]},
        {"text": "N=10g[2]", "confidence": 0.8, "bbox": [100, 170, 500, 220]},
        {"text": "N=10g[3]", "confidence": 0.8, "bbox": [100, 240, 500, 320]},  # pushes total height (320-100=220) over 200
    ]
    blocks = ingest_notes._group_math_lines_from_ocr_lines(lines)

    assert len(blocks) >= 2


def test_group_math_lines_does_not_split_a_short_continuous_equation():
    """A normal few-line formula must not be needlessly split."""
    from scripts.ingest_notes import _group_math_lines_from_ocr_lines

    lines = [
        {"text": "N=10g[1182-1]", "confidence": 0.8, "bbox": [100, 100, 500, 150]},
        {"text": "= log (109-1)", "confidence": 0.7, "bbox": [100, 160, 500, 210]},
        {"text": "= 6.64.", "confidence": 0.7, "bbox": [100, 220, 500, 270]},
    ]
    blocks = _group_math_lines_from_ocr_lines(lines)

    assert len(blocks) == 1
    assert len(blocks[0]["text"].split("\n")) == 3


def test_group_math_lines_preserves_original_top_to_bottom_order():
    from scripts.ingest_notes import _group_math_lines_from_ocr_lines

    lines = [
        {"text": "N=10g[2]", "confidence": 0.8, "bbox": [100, 300, 500, 350]},
        {"text": "N=10g[1]", "confidence": 0.8, "bbox": [100, 100, 500, 150]},
    ]
    blocks = _group_math_lines_from_ocr_lines(lines)

    assert len(blocks) == 1
    assert blocks[0]["text"].split("\n") == ["N=10g[1]", "N=10g[2]"]


# ---------------------------------------------------------------------------
# Reusable bounding-box safety validation (shared between
# _analyze_page_regions and _analyze_math_equation_blocks).
# ---------------------------------------------------------------------------

def test_validate_equation_bbox_accepts_a_normal_localized_region():
    from scripts.ingest_notes import validate_equation_bbox

    is_valid, reasons = validate_equation_bbox((10, 10, 100, 100), 1000, 1000)

    assert is_valid is True
    assert reasons == []


def test_validate_equation_bbox_flags_suspiciously_large_region():
    from scripts.ingest_notes import validate_equation_bbox

    is_valid, reasons = validate_equation_bbox((0, 0, 900, 900), 1000, 1000)

    assert is_valid is True  # structurally fine — flagged, not rejected
    assert "SUSPICIOUSLY_LARGE_BBOX" in reasons


def test_validate_equation_bbox_rejects_out_of_bounds_coordinates():
    from scripts.ingest_notes import validate_equation_bbox

    is_valid, reasons = validate_equation_bbox((10, 10, 2000, 100), 1000, 1000)

    assert is_valid is False
    assert "OUT_OF_BOUNDS" in reasons


def test_validate_equation_bbox_rejects_degenerate_coordinates():
    from scripts.ingest_notes import validate_equation_bbox

    is_valid, reasons = validate_equation_bbox((100, 100, 100, 200), 1000, 1000)  # x0 == x1

    assert is_valid is False
    assert "OUT_OF_BOUNDS" in reasons


def test_analyze_math_equation_blocks_flags_suspiciously_large_block_without_discarding_it(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setattr(ingest_notes, "_paddleocr_ocr_image", lambda image: ("log(x) + 1", 0.9, []))
    monkeypatch.setattr(ingest_notes, "_MATH_BLOCK_CROP_PADDING_PX", 0)

    # A block spanning almost the whole 100x100 image.
    lines = [{"text": "10g(x) + 1", "confidence": 0.8, "bbox": [2, 2, 98, 98]}]
    result = ingest_notes._analyze_math_equation_blocks(Image.new("L", (100, 100), "white"), lines)

    assert len(result) == 1
    assert "SUSPICIOUSLY_LARGE_BBOX" in result[0]["math_quality_reasons"]
    assert result[0]["ocr_text_raw"] == "10g(x) + 1"  # OCR output preserved, never discarded
    assert result[0]["math_quality"] == "NEEDS_REVIEW"  # bumped from what would otherwise be GOOD


def test_analyze_math_equation_blocks_returns_empty_without_math_lines(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("no OCR call should happen when there are no math-candidate lines")

    monkeypatch.setattr(ingest_notes, "_paddleocr_ocr_image", _should_not_be_called)

    lines = [{"text": "Ordinary prose with no equations.", "confidence": 0.9, "bbox": [0, 0, 500, 50]}]
    result = ingest_notes._analyze_math_equation_blocks(Image.new("L", (600, 600), "white"), lines)

    assert result == []


def test_analyze_math_equation_blocks_preserves_both_hypotheses_and_watermark_strips(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setattr(
        ingest_notes, "_paddleocr_ocr_image",
        lambda image: ("log(x) + 1\nScanned with CamScanner", 0.9, []),
    )

    lines = [{"text": "10g(x) + 1", "confidence": 0.8, "bbox": [50, 50, 300, 100]}]
    result = ingest_notes._analyze_math_equation_blocks(Image.new("L", (600, 600), "white"), lines)

    assert len(result) == 1
    block = result[0]
    assert block["ocr_text_raw"] == "10g(x) + 1"  # untouched primary text preserved
    assert block["normalized_text"] == "log(x) + 1"  # context-aware correction applied
    assert "CamScanner" not in block["second_opinion_text"]  # watermark stripped from the second opinion too
    assert block["latex"] is None
    assert block["review_required"] is True


def test_analyze_math_equation_blocks_degrades_gracefully_when_second_opinion_fails(monkeypatch):
    import scripts.ingest_notes as ingest_notes

    def _boom(image):
        raise RuntimeError("OCR exploded")

    monkeypatch.setattr(ingest_notes, "_paddleocr_ocr_image", _boom)

    lines = [{"text": "10g(x) + 1", "confidence": 0.8, "bbox": [50, 50, 300, 100]}]
    result = ingest_notes._analyze_math_equation_blocks(Image.new("L", (600, 600), "white"), lines)

    assert len(result) == 1
    assert result[0]["ocr_text_raw"] == "10g(x) + 1"
    assert result[0]["second_opinion_text"] == ""


def test_math_analysis_disabled_by_default_in_process_pdf(monkeypatch, tmp_path):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.delenv("SAARTHI_MATH_ANALYSIS", raising=False)

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("_analyze_math_equation_blocks must not run unless SAARTHI_MATH_ANALYSIS is set")

    monkeypatch.setattr(ingest_notes, "_analyze_math_equation_blocks", _should_not_be_called)
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda *a, **k: Image.new("RGB", (20, 20), "white"))
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda *a, **k: ingest_notes.OCRResult(
            text="N=10g(x) - a poorly recognized equation line here", confidence=0.6, engine="paddleocr", preprocessing=None, psm=None,
            lines=[{"text": "N=10g(x)", "confidence": 0.6, "bbox": [0, 0, 100, 20]}],
        ),
    )

    pdf_bytes = _make_simple_pdf("")
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(pdf_bytes)

    records = process_pdf(pdf_path, {"note_id": "X", "course": None, "topic": None}, only_page=1, dpi=300, preprocess=False)
    assert records[0].metadata["math_equation_blocks"] == []


def test_math_analysis_skipped_without_ocr_lines_even_when_enabled(monkeypatch, tmp_path):
    import scripts.ingest_notes as ingest_notes

    monkeypatch.setenv("SAARTHI_MATH_ANALYSIS", "1")

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("must not run without ocr_lines (e.g. a Tesseract-won page)")

    monkeypatch.setattr(ingest_notes, "_analyze_math_equation_blocks", _should_not_be_called)
    monkeypatch.setattr(ingest_notes, "render_pdf_page", lambda *a, **k: Image.new("RGB", (20, 20), "white"))
    monkeypatch.setattr(
        ingest_notes, "ocr_image",
        lambda *a, **k: ingest_notes.OCRResult(text="a poorly recognized line here", confidence=0.4, engine="tesseract", preprocessing=None, psm=6),
    )

    pdf_bytes = _make_simple_pdf("")
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(pdf_bytes)

    records = process_pdf(pdf_path, {"note_id": "X", "course": None, "topic": None}, only_page=1, dpi=300, preprocess=False)
    assert records[0].metadata["math_equation_blocks"] == []
