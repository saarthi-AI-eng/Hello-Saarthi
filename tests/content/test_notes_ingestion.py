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
