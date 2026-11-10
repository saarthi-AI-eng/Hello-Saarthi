"""
Ingest handwritten/scanned notes (PDF or image) into canonical
page-level ContentRecords (JSONL) with OCR confidence preserved honestly.

Pipeline: PDF/image -> page extraction -> image preprocessing -> OCR
-> text cleanup (whitespace only — see scripts/clean_content.py for the
real cleaning pass) -> canonical metadata -> qa_status=pending JSONL.

For PDFs, a page that already has an extractable text layer is used
directly (no OCR, no invented confidence). Only image-based/scanned pages
are rendered and OCR'd — at high resolution, trying several preprocessing
variants (including the untouched original render) crossed with several
Tesseract page-segmentation modes, plus a region-based pass and an
optional handwriting-model fallback, keeping whichever attempt ranks best.
Every page in range always produces a record; a page whose best attempt is
still empty or low-confidence is flagged via metadata, never silently
dropped, and nothing here ever "corrects" a formula based on assumptions —
only what Tesseract/the fallback model actually produced is stored.

Usage:
    python -m scripts.ingest_notes --input data/raw/notes --output data/processed/ocr --course "Signals and Systems"
    python -m scripts.ingest_notes --file notes_012.pdf --page 4

OCR requires the optional `pytesseract` package AND the Tesseract OCR
binary installed separately on the system (see docs/content-management.md).
An optional handwriting-specialized OCR fallback (TrOCR) can be enabled
with SAARTHI_HANDWRITING_OCR=trocr — see run_handwriting_ocr() below; it is
only ever used as a fallback when Tesseract's best result is low-confidence,
and the normal Tesseract-only pipeline works with zero extra dependencies
if it's unset or unavailable.

This module is never imported by the FastAPI backend or the live
orchestrator/agents — it is independent, additive tooling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from scripts.content_common import PROCESSED_OCR_DIR, RAW_NOTES_DIR, get_logger, log_operation
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, read_jsonl, record_to_dict, write_jsonl

logger = get_logger("ingest_notes")

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS

_MIN_NATIVE_TEXT_CHARS = 20  # below this, a PDF page is treated as scanned/image-based

# Scanner apps sometimes stamp a watermark into the PDF's native text layer
# even on a page that is otherwise a pure image scan. Measured, real bug in
# this project's own expanded raw-data set: 3 PDFs (~39 pages total) were
# scanned with CamScanner, which stamps "Scanned with CamScanner" (24 chars)
# as the ENTIRE native text layer on every page — above _MIN_NATIVE_TEXT_CHARS,
# so the native-text-layer shortcut would have silently treated these pages
# as "has real native text", stored that watermark string as the page's
# entire content, and never run OCR at all, losing 100% of the actual
# handwritten notes. Known watermark substrings are stripped before the
# native-text-length check (and from the content actually stored, in case a
# page genuinely has both real text and the watermark).
_KNOWN_PDF_WATERMARKS = [
    "Scanned with CamScanner",
]


def _strip_known_watermarks(text: str) -> str:
    cleaned = text
    for pattern in _KNOWN_PDF_WATERMARKS:
        cleaned = cleaned.replace(pattern, "")
    return cleaned.strip()

# Confidence-tier thresholds (requirement: >=0.70 high, 0.50-0.70 moderate, <0.50 low).
# Unknown confidence (backend reported none) is treated as "low" — conservative,
# never assume quality we can't verify.
CONFIDENCE_HIGH_THRESHOLD = 0.70
CONFIDENCE_MODERATE_THRESHOLD = 0.50
LOW_CONFIDENCE_THRESHOLD = CONFIDENCE_MODERATE_THRESHOLD  # kept as a named alias for readability elsewhere

# Tesseract OCR language(s). No math/equation-specific trained data is bundled —
# there isn't a lightweight one worth adding as a hard dependency — so this
# stays at Tesseract's own default ("eng") unless overridden.
_OCR_LANGUAGE = os.environ.get("SAARTHI_OCR_LANGUAGE", "eng")


def _confidence_tier(text: str, confidence: Optional[float]) -> str:
    """high / moderate / low — see CONFIDENCE_*_THRESHOLD. Empty text or an
    unverifiable (None) confidence is always "low": never make poor OCR look
    acceptable by assuming the best when we can't actually check."""
    if not text or confidence is None:
        return "low"
    if confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if confidence >= CONFIDENCE_MODERATE_THRESHOLD:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Image preprocessing (conservative — must not destroy equations/handwriting)
# ---------------------------------------------------------------------------
#
# We don't commit to a single preprocessing recipe. Handwritten scans vary a
# lot (pencil vs pen, lighting, paper texture), and a fixed pipeline that's
# conservative enough not to erase faint strokes is often too gentle to help
# Tesseract on a noisy scan — while an aggressive one can erase a cleaner
# page's faint pencil marks. Instead we generate several candidate variants,
# including the completely untouched original render as a baseline, and let
# ocr_image() pick whichever attempt actually scores best.

def preprocess_image_variants(image: Image.Image) -> Dict[str, Image.Image]:
    """Return named preprocessing variants to try OCR against."""
    import cv2
    import numpy as np

    variants: Dict[str, Image.Image] = {
        # The untouched render, always tried — preprocessing must never be
        # the *only* option, since it can occasionally hurt a clean/faint scan.
        "original": image,
    }

    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = _crop_borders(gray)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)
    deskewed = _deskew(contrasted)
    variants["grayscale_clahe"] = Image.fromarray(deskewed)

    # Adaptive threshold: often a big win on uneven-lighting/faint pencil
    # scans, but can occasionally hurt a cleaner page — offered as a
    # candidate rather than forced, since the best-scoring attempt wins.
    adaptive = cv2.adaptiveThreshold(
        deskewed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    variants["adaptive_threshold"] = Image.fromarray(adaptive)

    # Global Otsu threshold + a light morphological close to reconnect thin
    # handwritten strokes that binarization can fragment into broken dots/dashes.
    _, otsu = cv2.threshold(deskewed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    otsu_closed = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    variants["otsu_threshold"] = Image.fromarray(otsu_closed)

    # Unsharp-style sharpening (no binarization) — helps crisp up faint,
    # slightly blurry pencil edges without the all-or-nothing risk of a threshold.
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(contrasted, -1, sharpen_kernel)
    variants["sharpened"] = Image.fromarray(sharpened)

    return variants


def _detect_text_bands(
    gray: "np.ndarray", min_band_height: int = 12, gap_threshold_frac: float = 0.004, pad: int = 12
) -> List[Tuple[int, int]]:
    """Split a page into vertical bands separated by mostly-blank rows, so a
    region (a heading, a paragraph, an equation block) can be OCR'd on its
    own — full-page segmentation can otherwise get confused when handwriting,
    diagrams, and equations are unevenly distributed across the page.

    Bands are padded and adjacent overlapping bands are merged, so content
    sitting right at a detected boundary is never cut off between two bands.
    """
    import cv2
    import numpy as np

    h, w = gray.shape
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    row_ink = thresh.sum(axis=1) / 255.0  # "ink" pixel count per row
    is_blank_row = row_ink < (w * gap_threshold_frac)

    raw_bands: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for y in range(h):
        if not is_blank_row[y]:
            if start is None:
                start = y
        elif start is not None:
            raw_bands.append((start, y))
            start = None
    if start is not None:
        raw_bands.append((start, h))

    padded = []
    for y0, y1 in raw_bands:
        if (y1 - y0) < min_band_height:
            continue  # too thin to be real content — likely scan noise
        padded.append((max(0, y0 - pad), min(h, y1 + pad)))

    merged: List[Tuple[int, int]] = []
    for band in padded:
        if merged and band[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], band[1]))
        else:
            merged.append(band)

    return merged


def _crop_borders(gray: "np.ndarray", margin_frac: float = 0.02) -> "np.ndarray":
    """Crop uniform blank margins around the content, if any.

    Conservative: only crops when the detected content bounding box still
    covers most of the page, so a small ink mark near an edge can't cause
    the rest of the page to be cropped away.
    """
    import cv2

    h, w = gray.shape
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return gray
    x, y, bw, bh = cv2.boundingRect(coords)
    if bw < 0.5 * w or bh < 0.5 * h:
        return gray  # bounding box too small relative to the page — likely noise, not real content
    pad_x = int(w * margin_frac)
    pad_y = int(h * margin_frac)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
    return gray[y0:y1, x0:x1]


def _deskew(gray: "np.ndarray", max_angle: float = 15.0) -> "np.ndarray":
    import cv2

    # Otsu threshold purely to *find* the skew angle — OCR still runs on `gray`, not this binary mask.
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)
    if coords is None or len(coords) < 20:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.3 or abs(angle) > max_angle:
        return gray  # not worth correcting, or too large a shift to trust
    (h, w) = gray.shape
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

# Default install locations for the UB-Mannheim Windows Tesseract build
# (the one documented in requirements-content-pipeline.txt). Its installer
# doesn't always register itself on PATH, so we fall back to these rather
# than requiring a machine-wide PATH edit.
_TESSERACT_WINDOWS_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _resolve_tesseract_cmd(pytesseract_module) -> None:
    """Point pytesseract at the tesseract binary if it isn't already resolvable on PATH.

    pytesseract defaults tesseract_cmd to the bare string 'tesseract' and
    relies on PATH at call time. TESSERACT_CMD env var always wins (for a
    non-default install location); otherwise we only override when PATH
    lookup would fail, so a working PATH-based install is left untouched.
    """
    import shutil

    env_override = os.environ.get("TESSERACT_CMD")
    if env_override:
        pytesseract_module.pytesseract.tesseract_cmd = env_override
        return

    if shutil.which(pytesseract_module.pytesseract.tesseract_cmd):
        return  # already resolvable on PATH — nothing to do

    candidates = list(_TESSERACT_WINDOWS_CANDIDATES)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(str(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe"))

    for candidate in candidates:
        if Path(candidate).exists():
            pytesseract_module.pytesseract.tesseract_cmd = candidate
            return


@dataclass
class OCRResult:
    text: str
    confidence: Optional[float]
    engine: str  # "tesseract" | "trocr" | "paddleocr"
    preprocessing: Optional[str]  # e.g. "grayscale_clahe", "otsu_threshold+regions"; None for whole-image trocr/paddleocr
    psm: Optional[int]  # Tesseract page-segmentation mode used; None for trocr/paddleocr
    lines: Optional[List[dict]] = None  # per-line {"text", "confidence", "bbox"} — paddleocr only; None otherwise


def _describe_extraction(result: OCRResult) -> str:
    """Human-readable composite of engine/psm/preprocessing, for logs and metadata.extraction_method."""
    parts = [result.engine]
    if result.psm is not None:
        parts.append(f"psm{result.psm}")
    if result.preprocessing:
        parts.append(result.preprocessing)
    return "_".join(parts)


# Page segmentation modes tried per preprocessing variant, in order:
#   6  = assume a single uniform block of text (the common case for one note page)
#   4  = assume a single column of variable-sized text
#   11 = sparse text, find as much as possible in no particular order
#        (helps scattered handwriting/equations that don't form clean paragraphs)
_OCR_PSM_MODES = [6, 4, 11]


def _run_tesseract_attempt(pytesseract_module, output_cls, image: Image.Image, psm: int) -> tuple[str, Optional[float]]:
    # --oem 1: LSTM-only engine — the modern, generally more accurate neural
    #   recognizer (vs. legacy pattern-matching), a deliberate choice rather
    #   than looping over engine modes (which would multiply attempt count).
    # preserve_interword_spaces=1: keeps spacing between tokens intact,
    #   which matters for reading subscripts/variable groupings back correctly.
    # No tessedit_char_whitelist is ever set — a whitelist could silently
    #   strip mathematical symbols (π, ω, ∑, etc.) that aren't anticipated.
    config = f"--oem 1 --psm {psm} -l {_OCR_LANGUAGE} -c preserve_interword_spaces=1"
    text = pytesseract_module.image_to_string(image, config=config).strip()

    confidence: Optional[float] = None
    try:
        data = pytesseract_module.image_to_data(image, config=config, output_type=output_cls.DICT)
        scores = [int(c) for c in data.get("conf", []) if _is_valid_conf(c)]
        if scores:
            confidence = round((sum(scores) / len(scores)) / 100.0, 4)
    except Exception as exc:  # noqa: BLE001 — confidence is best-effort; never invent a number on failure
        logger.warning(f"Could not compute OCR confidence (psm {psm}): {exc}")

    return text, confidence


def _ocr_regions(
    pytesseract_module, output_cls, image: Image.Image, bands: List[Tuple[int, int]], psm: int
) -> Tuple[str, Optional[float]]:
    """OCR each detected band separately and join them — see _detect_text_bands.
    Confidence is length-weighted (a long confidently-read band should count
    for more than a two-word fragment)."""
    texts: List[str] = []
    weighted_confidences: List[Tuple[float, int]] = []
    for y0, y1 in bands:
        crop = image.crop((0, y0, image.width, y1))
        text, confidence = _run_tesseract_attempt(pytesseract_module, output_cls, crop, psm)
        if text:
            texts.append(text)
            if confidence is not None:
                weighted_confidences.append((confidence, len(text)))

    combined_text = "\n\n".join(texts)
    combined_confidence: Optional[float] = None
    total_len = sum(length for _, length in weighted_confidences)
    if total_len > 0:
        combined_confidence = round(sum(c * length for c, length in weighted_confidences) / total_len, 4)
    return combined_text, combined_confidence


def _attempt_rank(text: str, confidence: Optional[float]) -> tuple:
    """Rank one OCR attempt for best-of-N selection.

    Empty text always loses, regardless of what confidence was reported for
    it — a "confident" attempt that recognized nothing useful (e.g. only
    stray symbols that collapse to nothing after cleanup) must never beat an
    attempt that actually recovered real text. Among non-empty attempts,
    higher confidence wins; unknown confidence ranks below any known
    confidence but still above empty text.
    """
    if not text:
        return (0, -1.0)
    if confidence is not None:
        return (2, confidence)
    return (1, 0.0)


def ocr_image(image: Image.Image, preprocess: bool = True) -> OCRResult:
    """Run OCR on a PIL image: multiple preprocessing variants x Tesseract page
    segmentation modes, then a region-based pass on the best variant, then — only
    if the result isn't high-confidence and SAARTHI_HANDWRITING_OCR is set — an
    optional handwriting-model fallback. Keeps whichever attempt ranks best (see
    _attempt_rank). Never invents a confidence score, never "corrects" recognized
    text — only what a backend actually produced is ever returned."""
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is not installed. Install it with `pip install -r "
            "requirements-content-pipeline.txt`. See docs/content-management.md for details."
        ) from exc

    _resolve_tesseract_cmd(pytesseract)

    variants = preprocess_image_variants(image) if preprocess else {"original": image}

    best = OCRResult(text="", confidence=None, engine="tesseract", preprocessing=None, psm=None)
    best_rank = _attempt_rank("", None)
    best_image: Optional[Image.Image] = None

    for variant_name, variant_image in variants.items():
        for psm in _OCR_PSM_MODES:
            try:
                text, confidence = _run_tesseract_attempt(pytesseract, Output, variant_image, psm)
            except pytesseract.TesseractNotFoundError as exc:
                raise RuntimeError(
                    "The Tesseract OCR binary is not installed or not on PATH "
                    f"(pytesseract looked for {pytesseract.pytesseract.tesseract_cmd!r}). "
                    "Install it (winget install --id UB-Mannheim.TesseractOCR -e, or see "
                    "https://github.com/UB-Mannheim/tesseract/wiki), or set the TESSERACT_CMD "
                    "environment variable to the full path of tesseract.exe. "
                    "See docs/content-management.md for details."
                ) from exc

            rank = _attempt_rank(text, confidence)
            if rank > best_rank or (rank == best_rank and len(text) > len(best.text)):
                best_rank = rank
                best = OCRResult(text=text, confidence=confidence, engine="tesseract", preprocessing=variant_name, psm=psm)
                best_image = variant_image

    # Region-based pass: split the best-scoring variant into text bands and
    # OCR each separately. Only kept if it actually outranks the whole-page
    # result — never trusted blindly.
    bands: List[Tuple[int, int]] = []
    if preprocess and best_image is not None:
        try:
            import numpy as np

            bands = _detect_text_bands(np.array(best_image.convert("L")))
            if len(bands) > 1:
                region_text, region_confidence = _ocr_regions(pytesseract, Output, best_image, bands, psm=6)
                region_rank = _attempt_rank(region_text, region_confidence)
                if region_rank > best_rank or (region_rank == best_rank and len(region_text) > len(best.text)):
                    best_rank = region_rank
                    best = OCRResult(
                        text=region_text,
                        confidence=region_confidence,
                        engine="tesseract",
                        preprocessing=f"{best.preprocessing}+regions",
                        psm=6,
                    )
        except Exception as exc:  # noqa: BLE001 — a bonus attempt; must never abort the page on failure
            logger.warning(f"Region-based OCR attempt failed, keeping whole-page result: {exc}")

    # Optional handwriting-specialized OCR fallback — reached whenever
    # Tesseract's best result isn't "high" confidence AND the operator opted
    # in via SAARTHI_HANDWRITING_OCR. If the backend/dependency is
    # unavailable, this must never break the normal Tesseract-only pipeline.
    #
    # Deliberately tier != "high", not tier == "low": measured against
    # data/evaluation/ocr_ground_truth_all.jsonl, Tesseract's own
    # image_to_data confidence on genuinely garbled handwriting can land in
    # the "moderate" (0.50-0.70) bucket even though the text is unusable —
    # pytesseract's score reflects per-word recognition certainty, not
    # whether the reading is semantically right. Two of six ground-truth
    # pages were kept as garbled "moderate"-tier Tesseract output because
    # the old "low"-only trigger never gave the fallback a chance. Running
    # the fallback on "moderate" pages too costs one extra GPU PaddleOCR
    # pass (~1-6s measured) per page, not a second Tesseract sweep.
    # Strip known watermarks before computing the tier used for this
    # decision, not just afterward in _ocr_page_metadata: a page whose only
    # recognizable content IS a watermark (e.g. "Scanned with CamScanner")
    # gets read by Tesseract cleanly and confidently — real case measured on
    # AnalogFilters.pdf pages 10/11, confidence 0.86-0.94 on the watermark
    # text alone, which looked "high" enough to skip the fallback entirely,
    # even though the page's actual content (a diagram) produced zero real
    # text. Stripping first means an all-watermark page correctly reads as
    # empty here too, so the fallback still gets a chance.
    tier = _confidence_tier(_strip_known_watermarks(best.text), best.confidence)
    handwriting_backend = os.environ.get("SAARTHI_HANDWRITING_OCR", "").strip().lower()
    if tier != "high" and handwriting_backend:
        try:
            hw_result = run_handwriting_ocr(image, handwriting_backend, bands)
            hw_rank = _attempt_rank(hw_result.text, hw_result.confidence)
            if hw_rank > best_rank or (hw_rank == best_rank and len(hw_result.text) > len(best.text)):
                best = hw_result
        except Exception as exc:  # noqa: BLE001 — fallback is best-effort; Tesseract's result must still stand
            logger.warning(f"Handwriting OCR fallback ({handwriting_backend!r}) unavailable/failed, keeping Tesseract result: {exc}")

    return best


def _is_valid_conf(raw) -> bool:
    try:
        return int(raw) >= 0
    except (TypeError, ValueError):
        return False


def run_light_tesseract(image: Image.Image) -> OCRResult:
    """Single Tesseract attempt (--psm 6, no preprocessing-variant sweep) —
    for use as a per-region FALLBACK, not the primary page-level pipeline.

    ocr_image() above is deliberately expensive (5 preprocessing variants x
    3 PSM modes + a region re-pass, ~15-20 actual Tesseract invocations) —
    appropriate when Tesseract IS the primary attempt on a whole,
    not-yet-understood page. Calling that full sweep again as a FALLBACK for
    every individually low-confidence region is wasteful: measured in this
    project's hybrid pipeline, chaining the full ocr_image() fallback per
    region pushed mean processing to 263.6s/page (2.8x plain PaddleOCR) for
    only an 11% relative CER improvement. The region is already cropped from
    a sensibly-segmented source; --psm 6 (uniform block of text) is the
    right default for a single pre-cropped region the same way it's the
    first variant tried in the full sweep, without re-running the variant
    search a cropped region doesn't need as much as a whole page does."""
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is not installed. Install it with `pip install -r "
            "requirements-content-pipeline.txt`. See docs/content-management.md for details."
        ) from exc

    _resolve_tesseract_cmd(pytesseract)

    try:
        text, confidence = _run_tesseract_attempt(pytesseract, Output, image, psm=6)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "The Tesseract OCR binary is not installed or not on PATH "
            f"(pytesseract looked for {pytesseract.pytesseract.tesseract_cmd!r}). "
            "See docs/content-management.md for details."
        ) from exc

    return OCRResult(text=text, confidence=confidence, engine="tesseract", preprocessing=None, psm=6)


# ---------------------------------------------------------------------------
# Optional handwriting-specialized OCR fallback (TrOCR / PaddleOCR)
# ---------------------------------------------------------------------------
# Enabled only via SAARTHI_HANDWRITING_OCR=trocr|paddleocr. transformers/torch are not
# added to requirements-content-pipeline.txt as new dependencies — this repo
# already depends on both (saarthi_backend/requirements.txt, for docling), so
# nothing extra installs by default; this just uses them if present. If they
# genuinely aren't importable, ocr_image() above catches that and falls back
# to the Tesseract-only result — this fallback is never required.

_TROCR_MODEL_CACHE: Dict[str, tuple] = {}


def _get_trocr_model(model_name: str):
    if model_name not in _TROCR_MODEL_CACHE:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        logger.info(f"Loading handwriting OCR model {model_name!r} (first use only, cached for this run)...")
        processor = TrOCRProcessor.from_pretrained(model_name)
        model = VisionEncoderDecoderModel.from_pretrained(model_name)
        model.eval()
        _TROCR_MODEL_CACHE[model_name] = (processor, model)
    return _TROCR_MODEL_CACHE[model_name]


def _trocr_ocr_image(image: Image.Image, model_name: str) -> Tuple[str, Optional[float]]:
    import torch
    import torch.nn.functional as F

    processor, model = _get_trocr_model(model_name)

    pixel_values = processor(images=image.convert("RGB"), return_tensors="pt").pixel_values
    with torch.no_grad():
        outputs = model.generate(pixel_values, max_new_tokens=256, output_scores=True, return_dict_in_generate=True)

    text = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0].strip()

    confidence: Optional[float] = None
    scores = getattr(outputs, "scores", None)
    if scores:
        # Mean of the model's own per-token max softmax probability — an
        # honest confidence signal derived from the model, not invented.
        probs = [float(F.softmax(step_logits[0], dim=-1).max()) for step_logits in scores]
        if probs:
            confidence = round(sum(probs) / len(probs), 4)

    return text, confidence


def _run_trocr_backend(image: Image.Image, regions: Optional[List[Tuple[int, int]]]) -> OCRResult:
    """TrOCR is a line/short-text recognizer, not a full-page layout model, so
    when regions are available (from the Tesseract pass) each region is
    cropped from the *original* image and OCR'd separately, then joined — a
    closer match to what TrOCR was trained on than a whole dense note page."""
    try:
        import torch  # noqa: F401
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "SAARTHI_HANDWRITING_OCR=trocr requires the `transformers` and `torch` packages."
        ) from exc

    model_name = os.environ.get("SAARTHI_TROCR_MODEL", "microsoft/trocr-base-handwritten")
    crops = [image.crop((0, y0, image.width, y1)) for y0, y1 in regions] if regions else []
    crops = [c for c in crops if c.height >= 8 and c.width >= 8] or [image]

    texts: List[str] = []
    confidences: List[float] = []
    for crop in crops:
        text, confidence = _trocr_ocr_image(crop, model_name)
        if text:
            texts.append(text)
        if confidence is not None:
            confidences.append(confidence)

    combined_text = "\n\n".join(texts)
    combined_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    return OCRResult(
        text=combined_text,
        confidence=combined_confidence,
        engine="trocr",
        preprocessing="regions" if regions else None,
        psm=None,
    )


def run_handwriting_ocr(image: Image.Image, backend: str, regions: Optional[List[Tuple[int, int]]] = None) -> OCRResult:
    """Handwriting-specialized OCR fallback, dispatching to whichever backend
    SAARTHI_HANDWRITING_OCR names. Supported: 'trocr' (line-cropped, see
    _run_trocr_backend) and 'paddleocr' (whole-page, see _run_paddleocr_backend
    below — PaddleOCR does its own text detection, so it doesn't need the
    Tesseract-derived regions TrOCR relies on)."""
    if backend == "trocr":
        return _run_trocr_backend(image, regions)
    if backend == "paddleocr":
        return _run_paddleocr_backend(image)
    raise RuntimeError(f"Unknown SAARTHI_HANDWRITING_OCR backend {backend!r} (supported: 'trocr', 'paddleocr').")


# ---------------------------------------------------------------------------
# Optional PaddleOCR backend
# ---------------------------------------------------------------------------
# Not a hard dependency: `paddleocr`/`paddlepaddle` are NOT listed in
# requirements-content-pipeline.txt (they pull in a heavy transitive
# dependency tree — paddlex, modelscope, etc. — unlike the rest of this
# repo's optional extras). Install separately: see
# docs/content-management.md for the exact command. If they aren't
# importable, run_handwriting_ocr() raises here and ocr_image()'s existing
# try/except catches it and keeps the Tesseract result — this backend is
# never required.
#
# PaddleOCR's own text detector finds and orders text lines/regions itself
# (unlike TrOCR, which only recognizes a pre-cropped line), so it always
# runs on the whole page rather than Tesseract-derived regions. Reading
# order and per-line bounding boxes come straight from that detector and
# are preserved in OCRResult.lines — never re-derived or guessed here.
#
# Empirically (see scripts/evaluate_ocr.py and data/evaluation/
# ocr_ground_truth.jsonl): PaddleOCR's general multilingual recognition
# model is NOT a dedicated handwriting model the way TrOCR's
# trocr-base-handwritten is — there is no English-specific "handwritten"
# PaddleOCR recognition model as of PaddleOCR 3.x (PP-OCRv5's improved
# handwriting support is documented primarily for Chinese script). It still
# produces usable text on real handwritten engineering notes (see the
# evaluation results), but that is a measured outcome, not an assumption —
# do not treat it as a guaranteed handwriting specialist.
#
# PaddleOCR's per-line rec_scores and Tesseract's image_to_data conf are
# computed completely differently (line-level softmax-derived vs.
# per-word/char engine confidence, different scales/semantics) — _attempt_rank
# compares them directly as a practical heuristic, not a calibrated
# cross-engine score. No validation data exists yet to calibrate them
# properly; treat cross-engine confidence comparisons as provisional.

_PADDLEOCR_INSTANCE_CACHE: Dict[str, "object"] = {}


def _detect_paddleocr_device() -> str:
    """Auto-detects whether this machine can actually use PaddleOCR on
    GPU — never assumes the RTX 4060 this was benchmarked on
    (docs/ocr-benchmark-final-report.md: ~24x faster than CPU, no
    accuracy tradeoff, on THAT machine) is present elsewhere. Checked at
    runtime via paddle itself (compiled-with-CUDA + at least one visible
    device), not inferred from any hardcoded GPU name/index/VRAM size.
    Falls back to CPU (with a clear log message, never a crash) if paddle
    isn't CUDA-enabled, no GPU is visible, or the check itself errors for
    any reason (e.g. driver/toolkit mismatch on an unfamiliar machine)."""
    try:
        import paddle

        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu"
    except Exception as exc:  # noqa: BLE001 — detection must never crash startup; CPU always works
        logger.warning(f"GPU detection for PaddleOCR failed ({exc}); falling back to CPU.")
        return "cpu"
    logger.info("No CUDA-enabled PaddlePaddle GPU detected — using CPU for PaddleOCR (this will be slower; see docs/ocr-benchmark-final-report.md for the measured GPU/CPU difference).")
    return "cpu"


def _get_paddleocr_instance(lang: str):
    """Lazily construct and cache a PaddleOCR pipeline instance (one per
    language — re-creating it per page would reload the detection/recognition
    models every call)."""
    if lang not in _PADDLEOCR_INSTANCE_CACHE:
        from paddleocr import PaddleOCR

        device = os.environ.get("SAARTHI_PADDLEOCR_DEVICE") or _detect_paddleocr_device()
        logger.info(f"Loading PaddleOCR (lang={lang!r}, device={device!r}, first use only, cached for this run)...")
        _PADDLEOCR_INSTANCE_CACHE[lang] = PaddleOCR(
            lang=lang,
            text_detection_model_name=os.environ.get("SAARTHI_PADDLEOCR_DET_MODEL") or None,
            text_recognition_model_name=os.environ.get("SAARTHI_PADDLEOCR_REC_MODEL") or None,
            # Auto-detected above — never hardcoded to this dev machine's
            # GPU. SAARTHI_PADDLEOCR_DEVICE, if set, always wins (explicit
            # operator override, e.g. to force "cpu" or target a specific
            # "gpu:N" on a multi-GPU box).
            device=device,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=_env_flag("SAARTHI_PADDLEOCR_TEXTLINE_ORIENTATION"),
            # Disabled by default: this pipeline hit a hard crash
            # (`NotImplementedError: ConvertPirAttribute2RuntimeAttribute...`)
            # with PaddlePaddle 3.3.1's oneDNN/PIR CPU backend on the
            # PP-OCRv5 detection model during evaluation. Opt back in with
            # SAARTHI_PADDLEOCR_MKLDNN=1 if your environment handles it —
            # it can be noticeably faster on CPU when it works.
            enable_mkldnn=_env_flag("SAARTHI_PADDLEOCR_MKLDNN"),
        )
    return _PADDLEOCR_INSTANCE_CACHE[lang]


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _paddleocr_ocr_image(image: Image.Image) -> Tuple[str, Optional[float], List[dict]]:
    import numpy as np

    lang = os.environ.get("SAARTHI_PADDLEOCR_LANG", "en")
    ocr = _get_paddleocr_instance(lang)

    # PaddleOCR/OpenCV expect BGR channel order.
    array = np.array(image.convert("RGB"))[:, :, ::-1]
    results = ocr.predict(array)
    if not results:
        return "", None, []

    page = results[0]
    texts = list(page.get("rec_texts") or [])
    scores = [float(s) for s in (page.get("rec_scores") or [])]
    boxes = page.get("rec_boxes")

    lines: List[dict] = []
    for i, line_text in enumerate(texts):
        if not line_text:
            continue
        entry: dict = {"text": line_text}
        if i < len(scores):
            entry["confidence"] = round(scores[i], 4)
        if boxes is not None and i < len(boxes):
            entry["bbox"] = [int(v) for v in boxes[i]]
        lines.append(entry)

    text = "\n".join(t for t in texts if t)
    confidence = round(sum(scores) / len(scores), 4) if scores else None
    return text, confidence, lines


def _run_paddleocr_backend(image: Image.Image) -> OCRResult:
    try:
        import paddleocr  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "SAARTHI_HANDWRITING_OCR=paddleocr requires the `paddleocr` and `paddlepaddle` "
            "packages — see docs/content-management.md for the install command."
        ) from exc

    text, confidence, lines = _paddleocr_ocr_image(image)
    return OCRResult(
        text=text,
        confidence=confidence,
        engine="paddleocr",
        preprocessing=None,
        psm=None,
        lines=lines or None,
    )


# ---------------------------------------------------------------------------
# PDF page extraction
# ---------------------------------------------------------------------------

def get_pdf_page_count(pdf_path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(pdf_path)).pages)


def extract_pdf_native_text(pdf_path: Path, page_index: int) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return (reader.pages[page_index].extract_text() or "").strip()


def render_pdf_page(pdf_path: Path, page_index: int, dpi: int = 300) -> Image.Image:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[page_index]
        bitmap = page.render(scale=dpi / 72)
        return bitmap.to_pil()
    finally:
        pdf.close()


# ---------------------------------------------------------------------------
# Metadata resolution (manifest / CLI — never invented)
# ---------------------------------------------------------------------------

def _load_manifest(source_path: Path) -> dict:
    manifest_path = source_path.with_suffix(".json")
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(f"Ignoring malformed manifest {manifest_path.name}: {exc}")
    return {}


def _derive_note_id(stem: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").upper()
    return slug or "NOTE"


def resolve_metadata(source_path: Path, cli_course: Optional[str], cli_topic: Optional[str], cli_note_id: Optional[str]) -> dict:
    manifest = _load_manifest(source_path)
    note_id = cli_note_id or manifest.get("note_id") or _derive_note_id(source_path.stem)
    course = cli_course or manifest.get("course")
    topic = cli_topic or manifest.get("topic")
    return {"note_id": note_id, "course": course, "topic": topic}


def _light_clean(text: str) -> str:
    """Whitespace-only normalization; artifact removal belongs to clean_content.py."""
    return re.sub(r"[ \t]+", " ", text).strip()


# ---------------------------------------------------------------------------
# Page-level quality classification — independent of engine confidence.
# ---------------------------------------------------------------------------
# Measured against this project's own real data (AnalogFilters.pdf, 17 pages):
# engine-reported confidence does not reliably predict correctness on dense
# handwritten math — pages with ~23 characters of near-garbage text (10, 11,
# 15) and pages with visibly garbled math worked-examples (4, 6, 7, 13, 16,
# 17) both reported "high" confidence (0.74-0.94) from their winning engine.
# These thresholds were inspection-calibrated against all 17 real pages, not
# picked arbitrarily — see docs/ocr-benchmark-final-report.md.
#
# Deliberately duplicated, not imported, from scripts/verification.py's
# check_character_anomalies (same repeated-run regex family, same threshold):
# ingest_notes.py's production path has zero import-time coupling to the
# opt-in evaluation/dev tooling, and this is cheap enough (one small regex)
# that a one-line duplicate is simpler than creating that coupling for a
# default, always-on page classification.
_REPEATED_RUN_RE = re.compile(r"(.{1,12}?)\1{19,}")
_WORDLIKE_RE = re.compile(r"[A-Za-z]{3,}")
_PAGE_QUALITY_MATH_CHARS = set("=+-*/^_<>≤≥≠∑∫πθωΩαβγδλμσΣ∏√∞±÷×")
_PAGE_QUALITY_MATH_DENSITY_THRESHOLD = 0.04
_PAGE_QUALITY_NEAR_EMPTY_CHARS = 60
_PAGE_QUALITY_MIN_TOKENS_FOR_FRAGMENTATION_CHECK = 4
_PAGE_QUALITY_WORDLIKE_RATIO_THRESHOLD = 0.35
# A single formula line can be badly garbled inside an otherwise-good,
# mostly-prose page (measured: AnalogFilters.pdf page 1 — "Lowpass
# Butterwoith.\n1HC2)^2=\n1+E" buried in 560 characters of decent prose,
# whole-page math density far below the threshold above). Checking per
# LINE as well as the whole-page average catches that case without an
# extra OCR/region pass — still a cheap, text-only check, and still a
# general mechanism (any page with one dense-enough line), not a rule
# aimed at this one page specifically.
_PAGE_QUALITY_LINE_MATH_DENSITY_THRESHOLD = 0.12
_PAGE_QUALITY_LINE_MIN_CHARS_FOR_DENSITY_CHECK = 6


def classify_page_quality(text: str, confidence: Optional[float]) -> Tuple[str, List[str]]:
    """GOOD / NEEDS_REVIEW / POOR_EXTRACTION + the reasons, computed purely
    from the recognized text (+ whether a confidence score exists at all) —
    never from the raw confidence NUMBER, which this project has repeatedly
    measured as uncorrelated with actual correctness on this content."""
    stripped = text.strip()
    length = len(stripped)
    reasons: List[str] = []

    if length == 0:
        reasons.append("EMPTY_OUTPUT")
    elif length < _PAGE_QUALITY_NEAR_EMPTY_CHARS:
        reasons.append("NEAR_EMPTY_OUTPUT")

    if _REPEATED_RUN_RE.search(stripped):
        reasons.append("SUSPICIOUS_REPETITION")

    tokens = stripped.split()
    if len(tokens) >= _PAGE_QUALITY_MIN_TOKENS_FOR_FRAGMENTATION_CHECK:
        wordlike = _WORDLIKE_RE.findall(stripped)
        if (len(wordlike) / len(tokens)) < _PAGE_QUALITY_WORDLIKE_RATIO_THRESHOLD:
            reasons.append("FRAGMENTED_TEXT")

    non_space = [c for c in stripped if not c.isspace()]
    math_hit = False
    if non_space:
        math_density = sum(1 for c in non_space if c in _PAGE_QUALITY_MATH_CHARS) / len(non_space)
        math_hit = math_density >= _PAGE_QUALITY_MATH_DENSITY_THRESHOLD
    if not math_hit:
        for line in stripped.split("\n"):
            line_non_space = [c for c in line if not c.isspace()]
            if len(line_non_space) < _PAGE_QUALITY_LINE_MIN_CHARS_FOR_DENSITY_CHECK:
                continue
            line_density = sum(1 for c in line_non_space if c in _PAGE_QUALITY_MATH_CHARS) / len(line_non_space)
            if line_density >= _PAGE_QUALITY_LINE_MATH_DENSITY_THRESHOLD:
                math_hit = True
                break
    if math_hit:
        reasons.append("MATHEMATICAL_CONTENT")

    if confidence is None:
        reasons.append("NO_CONFIDENCE_SCORE")

    severe = {"EMPTY_OUTPUT", "NEAR_EMPTY_OUTPUT", "SUSPICIOUS_REPETITION", "FRAGMENTED_TEXT"}
    if any(r in severe for r in reasons):
        label = "POOR_EXTRACTION"
    elif "MATHEMATICAL_CONTENT" in reasons or "NO_CONFIDENCE_SCORE" in reasons:
        label = "NEEDS_REVIEW"
    else:
        label = "GOOD"
    return label, reasons


# ---------------------------------------------------------------------------
# Conservative spelling correction — a small, curated, exact-match (case-
# insensitive) whitelist of real OCR misreads, NOT a generic dictionary/
# fuzzy spellchecker. A generic approach risks "correcting" a technical
# variable name (Hs, Tn, Rc, wp...) into an unrelated real English word;
# this whitelist contains zero tokens that look like variable names, so
# there is no such risk by construction. Every entry was confirmed against
# this project's own real OCR output (data/processed/ocr_improved/
# AnalogFilters.jsonl) and the original PDF's actual wording — never
# guessed. No new dependency: pure stdlib regex substitution.
#
# Confidence < _SPELLING_AUTO_APPLY_THRESHOLD is reported in
# `spelling_corrections` metadata but NEVER auto-applied to the text — e.g.
# "reifoim" could plausibly be "Reform" or "Perform" in isolation; flagged
# for manual review rather than silently guessed either way.
_SPELLING_CORRECTIONS: Dict[str, Tuple[str, float]] = {
    "cheractristic": ("characteristic", 0.95),
    "cheractristics": ("characteristics", 0.95),
    "butterwoith": ("butterworth", 0.95),
    "buttarworth": ("butterworth", 0.95),
    "freqeuency": ("frequency", 0.95),
    "prescrving": ("preserving", 0.9),
    "chebyiher": ("chebyshev", 0.9),
    "epossible": ("possible", 0.85),
    "atknuatim": ("attenuation", 0.75),
    "atknuatin": ("attenuation", 0.75),
    "cattententia": ("attenuation", 0.6),
    "parsband": ("passband", 0.85),
    "parstand": ("passband", 0.85),
    "ffilter": ("filter", 0.9),
    "fiter": ("filter", 0.9),
    "designi": ("design", 0.85),
    "propertics": ("properties", 0.85),
    "resporse": ("response", 0.85),
    "roats": ("roots", 0.75),
    "squlared": ("squared", 0.85),
    "incrcajing": ("increasing", 0.7),
    "kiven": ("given", 0.75),
    "iaterval": ("interval", 0.6),
    "reifoim": ("reform", 0.6),
}
_SPELLING_AUTO_APPLY_THRESHOLD = 0.7
_SPELLING_WORD_RE = re.compile(r"[A-Za-z]+")


def apply_spelling_corrections(text: str) -> Tuple[str, List[dict]]:
    """Returns (corrected_text, corrections) — corrections is a list of
    {"original", "suggested", "confidence", "applied"} for every candidate
    found, whether or not it was actually applied to the returned text."""
    corrections: List[dict] = []

    def _replace(match: "re.Match[str]") -> str:
        word = match.group(0)
        entry = _SPELLING_CORRECTIONS.get(word.lower())
        if entry is None:
            return word
        correction, confidence = entry
        applied = confidence >= _SPELLING_AUTO_APPLY_THRESHOLD
        corrections.append({"original": word, "suggested": correction, "confidence": confidence, "applied": applied})
        if not applied:
            return word
        if word.isupper():
            return correction.upper()
        if word[0].isupper():
            return correction.capitalize()
        return correction

    corrected_text = _SPELLING_WORD_RE.sub(_replace, text)
    return corrected_text, corrections


# ---------------------------------------------------------------------------
# Math-specific OCR improvement — equation-block grouping, context-aware
# symbol normalization, and a second-opinion hypothesis at higher
# resolution. Opt-in (SAARTHI_MATH_ANALYSIS=1), additive, never replaces
# the page's primary text or the existing math_regions/
# full_page_region_candidates from the prior iteration.
#
# Dedicated formula-recognition models were re-evaluated, not assumed to
# be worse: UniMERNet (already set up in this project's isolated venv —
# scripts/unimernet_adapter.py, zero new download) was run against the
# real Butterworth-formula crop from AnalogFilters.pdf page 1
# ([0, 2500, 2893, 2936]). Result: 36.4s (vs. ~1-6s for PaddleOCR on a
# whole page) and syntactically LaTeX-shaped but semantically meaningless
# output ("\hat{w}_1 -> oracler_flecter" repeated nonsense) — consistent
# with this project's prior finding that UniMERNet struggles on real
# handwriting (it's trained on printed/typeset formulas), and worse: this
# crop also mixes in ordinary prose ("Lowpass Butterworth."), which a
# formula-only model has no way to handle correctly. Not integrated — see
# docs/analogfilters-math-ocr-improvement-report.md §2 for the full
# finding. Pix2Text was not installed/evaluated: no local checkpoint
# exists, and a second dedicated-model download is a weak bet given
# UniMERNet and PP-FormulaNet (prior session) both already failed on this
# project's real handwritten content.
# ---------------------------------------------------------------------------

# Vertical gap (pixels, at native page render resolution) below which two
# math-dense OCR lines are considered part of the same equation block, not
# two separate ones. Inspection-calibrated against AnalogFilters.pdf's own
# line bboxes (typical single-line height ~100-150px at 350 DPI).
_MATH_BLOCK_MAX_LINE_GAP_PX = 150
_MATH_BLOCK_CROP_PADDING_PX = 20
_MATH_BLOCK_UPSCALE_FACTOR = 2
# Size caps on a single equation block, independent of the gap check above
# — see the comment at the grouping loop below for the real page-14 case
# these prevent. ~8 lines / ~1800px is generous for one real multi-line
# formula on this project's own pages (inspection-calibrated), without
# letting an uninterrupted dense run grow unbounded.
_MATH_BLOCK_MAX_LINES = 8
_MATH_BLOCK_MAX_HEIGHT_PX = 1800

# Context-aware, curated, exact-match math-OCR-symbol corrections — the
# math-specific sibling of _SPELLING_CORRECTIONS, kept separate because
# these patterns (e.g. "10g") would be actively wrong to apply to ordinary
# prose. Every entry confirmed against this project's own real OCR output
# (data/processed/ocr_final_test/AnalogFilters.jsonl pages 2, 4, 16).
# Confidence is boosted when the token is immediately followed by "(" in
# the source text (this corpus's "log"/"ln" is overwhelmingly followed by
# an opening parenthesis) — a real, cheap, local-context signal, not a
# global blind replace.
_MATH_TOKEN_CORRECTIONS: Dict[str, Tuple[str, float]] = {
    "10g": ("log", 0.55),
    "l0g": ("log", 0.55),
    "1og": ("log", 0.5),
    "loy": ("log", 0.35),
    "2l0g": ("2log", 0.45),
}
_MATH_TOKEN_FOLLOWED_BY_BRACKET_BONUS = 0.35
_MATH_TOKEN_AUTO_APPLY_THRESHOLD = 0.75
_MATH_TOKEN_RE = re.compile(r"[A-Za-z0-9]+[(\[]?")


def normalize_math_text(text: str) -> Tuple[str, List[dict]]:
    """Conservative, confidence-scored math-symbol normalization (e.g.
    "10g(x)" -> "log(x)"). Returns (normalized_text, corrections) —
    corrections lists every candidate with {"original", "suggested",
    "confidence", "applied"}, whether or not it was actually applied.
    Never a blind global replace: confidence depends on local context (is
    this token immediately followed by an opening "(" or "[" — this
    corpus's log/ln calls use both), and only entries at/above
    _MATH_TOKEN_AUTO_APPLY_THRESHOLD are applied."""
    corrections: List[dict] = []

    def _replace(match: "re.Match[str]") -> str:
        raw = match.group(0)
        bracket = raw[-1] if raw[-1] in "([" else ""
        word = raw[:-1] if bracket else raw
        entry = _MATH_TOKEN_CORRECTIONS.get(word.lower())
        if entry is None or entry[1] <= 0:
            return raw
        correction, base_confidence = entry
        confidence = min(0.95, base_confidence + (_MATH_TOKEN_FOLLOWED_BY_BRACKET_BONUS if bracket else 0.0))
        applied = confidence >= _MATH_TOKEN_AUTO_APPLY_THRESHOLD
        corrections.append({"original": word, "suggested": correction, "confidence": round(confidence, 2), "applied": applied})
        if not applied:
            return raw
        return correction + bracket

    normalized = _MATH_TOKEN_RE.sub(_replace, text)
    return normalized, corrections


def _group_math_lines_from_ocr_lines(ocr_lines: Optional[List[dict]]) -> List[dict]:
    """Groups spatially-adjacent, math-symbol-dense OCR lines (already
    recognized by the page's primary OCR pass — zero extra OCR call for
    this detection step) into equation blocks, using each line's existing
    bbox. Returns [] when there are no math-candidate lines (so callers
    can cheaply skip a page with no equations at all — see
    process_pdf()'s SAARTHI_MATH_ANALYSIS gating)."""
    if not ocr_lines:
        return []

    candidates = []
    for line in ocr_lines:
        text = (line.get("text") or "").strip()
        bbox = line.get("bbox")
        if not text or not bbox:
            continue
        non_space = [c for c in text if not c.isspace()]
        if not non_space:
            continue
        density = sum(1 for c in non_space if c in _PAGE_QUALITY_MATH_CHARS) / len(non_space)
        if density >= _PAGE_QUALITY_LINE_MATH_DENSITY_THRESHOLD:
            candidates.append((tuple(bbox), text, line.get("confidence")))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0][1])  # top-to-bottom, by bbox y0

    blocks: List[List[tuple]] = [[candidates[0]]]
    for item in candidates[1:]:
        current = blocks[-1]
        prev_bbox = current[-1][0]
        gap = item[0][1] - prev_bbox[3]
        prospective_height = item[0][3] - current[0][0][1]
        # Split on gap OR on hitting a size cap — a long, uninterrupted
        # run of math-dense lines (e.g. a multi-step derivation with no
        # blank-row gap between steps) would otherwise keep growing into
        # one oversized block that silently merges what are really
        # separate derivation steps (measured: AnalogFilters.pdf page 14,
        # one 11-line/1894px block covering what iteration 2's coarser
        # band detector correctly saw as 3-4 separate bands). Still never
        # splits a single short equation — both caps are generous enough
        # for a normal few-line formula.
        if (
            gap <= _MATH_BLOCK_MAX_LINE_GAP_PX
            and len(current) < _MATH_BLOCK_MAX_LINES
            and prospective_height <= _MATH_BLOCK_MAX_HEIGHT_PX
        ):
            current.append(item)
        else:
            blocks.append([item])

    results = []
    for block in blocks:
        x0 = min(b[0][0] for b in block)
        y0 = min(b[0][1] for b in block)
        x1 = max(b[0][2] for b in block)
        y1 = max(b[0][3] for b in block)
        confidences = [b[2] for b in block if b[2] is not None]
        results.append({
            "bbox": (x0, y0, x1, y1),
            "text": "\n".join(b[1] for b in block),
            "confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        })
    return results


# Deliberately NOT classify_page_quality's near-empty threshold (60 chars,
# calibrated for whole PAGES): an equation block is a deliberately small
# crop, legitimately 15-50 characters for a perfectly fine short formula —
# reusing the page-level threshold flagged essentially every real block
# POOR_EXTRACTION regardless of actual quality (measured: 100% of blocks
# across all 17 real pages on first implementation, before this fix).
_MATH_BLOCK_NEAR_EMPTY_CHARS = 8
# Below this length ratio (shorter hypothesis / longer hypothesis, after
# whitespace normalization), the two hypotheses aren't just "worded
# differently" — one of them is missing a substantial chunk of content.
# Distinguished from plain HYPOTHESIS_DISAGREEMENT (similar length, just
# different readings) because a reviewer needs to know which failure mode
# they're looking at — see docs/analogfilters-latest-math-ocr-evaluation.md
# §7, the finding this fixes: a 90% raw-disagreement rate that didn't
# distinguish "two real competing readings" from "one pass basically gave
# up." Calibrated loosely (not against a labeled set — none exists): a
# hypothesis missing more than half its partner's content is incomplete
# by any reasonable reading.
_MATH_HYPOTHESIS_INCOMPLETE_RATIO_THRESHOLD = 0.5


def _classify_math_block_quality(primary_text: str, second_opinion_text: str) -> Tuple[str, List[str]]:
    """GOOD/NEEDS_REVIEW/POOR_EXTRACTION/NOT_DETECTED for one equation
    block. Reuses _REPEATED_RUN_RE (the same degenerate-repetition check
    classify_page_quality uses) but NOT its near-empty/fragmentation/
    word-ratio thresholds, which are calibrated for whole pages, not short
    equation crops (see _MATH_BLOCK_NEAR_EMPTY_CHARS above). Independent
    of the page's own page_quality — a page can be GOOD overall with a
    badly garbled equation inside it, or vice versa.

    Distinguishes (never conflates, per the evaluation's explicit finding
    that lumping these together made the signal nearly uninformative):
    - genuine agreement (no reason added — the common case should be
      unremarkable, not flagged);
    - two non-empty hypotheses that genuinely disagree, at similar length
      (HYPOTHESIS_DISAGREEMENT — a real "which one is right?" case);
    - one hypothesis substantially shorter/missing content relative to
      the other (*_INCOMPLETE — never resolved by preferring the longer
      one as "correct", just named so a reviewer knows which is which);
    - the second opinion came back empty while the primary has real
      content (SECOND_OPINION_EMPTY — informational only, does not by
      itself demote a block that's otherwise fine: it means the second
      *attempt* failed, not that the primary is wrong);
    - the primary itself is empty while the second opinion found
      something (PRIMARY_EMPTY — the more concerning direction, since
      the primary is what actually reaches the page; kept at
      POOR_EXTRACTION severity);
    - both empty (NOT_DETECTED, unchanged from before)."""
    primary_stripped = (primary_text or "").strip()
    second_stripped = (second_opinion_text or "").strip()

    if not primary_stripped and not second_stripped:
        return "NOT_DETECTED", ["NO_TEXT_RECOGNIZED"]

    reasons: List[str] = []
    if primary_stripped and len(primary_stripped) < _MATH_BLOCK_NEAR_EMPTY_CHARS:
        reasons.append("NEAR_EMPTY_OUTPUT")
    if primary_stripped and _REPEATED_RUN_RE.search(primary_stripped):
        reasons.append("SUSPICIOUS_REPETITION")

    normalize_for_compare = lambda s: re.sub(r"\s+", "", s).lower()
    norm_primary = normalize_for_compare(primary_stripped)
    norm_second = normalize_for_compare(second_stripped)

    if not primary_stripped and second_stripped:
        reasons.append("PRIMARY_EMPTY")
    elif primary_stripped and not second_stripped:
        reasons.append("SECOND_OPINION_EMPTY")
    elif norm_primary != norm_second:
        shorter_len, longer_len = sorted([len(norm_primary), len(norm_second)])
        if longer_len > 0 and shorter_len / longer_len < _MATH_HYPOTHESIS_INCOMPLETE_RATIO_THRESHOLD:
            reasons.append("SECOND_OPINION_INCOMPLETE" if len(norm_second) < len(norm_primary) else "PRIMARY_INCOMPLETE")
        else:
            reasons.append("HYPOTHESIS_DISAGREEMENT")
    # else: genuine agreement — no reason added.

    severe = {"NEAR_EMPTY_OUTPUT", "SUSPICIOUS_REPETITION", "PRIMARY_EMPTY"}
    moderate = {"HYPOTHESIS_DISAGREEMENT", "SECOND_OPINION_INCOMPLETE", "PRIMARY_INCOMPLETE"}
    # SECOND_OPINION_EMPTY is deliberately in neither set — informational,
    # per this function's docstring above.
    if any(r in severe for r in reasons):
        label = "POOR_EXTRACTION"
    elif any(r in moderate for r in reasons):
        label = "NEEDS_REVIEW"
    else:
        label = "GOOD"
    return label, reasons


def _analyze_math_equation_blocks(image: Image.Image, ocr_lines: Optional[List[dict]]) -> List[dict]:
    """Opt-in (SAARTHI_MATH_ANALYSIS=1) math-equation-block extraction.
    Groups existing OCR lines into blocks (_group_math_lines_from_ocr_lines
    — no extra OCR call), crops + upscales each block
    (_MATH_BLOCK_UPSCALE_FACTOR) and runs ONE additional recognition pass
    on the upscaled crop as a second, independent hypothesis — higher
    effective resolution can genuinely help small-symbol/subscript
    recognition, and is cheap on GPU (~1-6s measured per page in
    docs/ocr-benchmark-final-report.md §3). The two hypotheses are never
    blindly merged: both are stored, and disagreement is flagged for
    review (_classify_math_block_quality), never silently resolved by
    picking whichever reports higher confidence (this project has
    repeatedly measured engine confidence as unreliable on this content)."""
    blocks = _group_math_lines_from_ocr_lines(ocr_lines)
    if not blocks:
        return []

    results = []
    for block in blocks:
        x0, y0, x1, y1 = block["bbox"]
        px0 = max(0, x0 - _MATH_BLOCK_CROP_PADDING_PX)
        py0 = max(0, y0 - _MATH_BLOCK_CROP_PADDING_PX)
        px1 = min(image.width, x1 + _MATH_BLOCK_CROP_PADDING_PX)
        py1 = min(image.height, y1 + _MATH_BLOCK_CROP_PADDING_PX)
        crop = image.crop((px0, py0, px1, py1))
        upscaled = crop.resize((crop.width * _MATH_BLOCK_UPSCALE_FACTOR, crop.height * _MATH_BLOCK_UPSCALE_FACTOR), Image.LANCZOS)

        second_opinion_text = ""
        try:
            second_opinion_text, _second_confidence, _lines = _paddleocr_ocr_image(upscaled)
            second_opinion_text = _strip_known_watermarks(second_opinion_text)
        except Exception as exc:  # noqa: BLE001 — the second opinion is best-effort; the first hypothesis must still stand
            logger.warning(f"Math equation-block second-opinion OCR failed, keeping the primary-pass text only: {exc}")

        primary_text = _strip_known_watermarks(block["text"])
        normalized_text, math_normalizations = normalize_math_text(primary_text)
        math_quality, math_quality_reasons = _classify_math_block_quality(primary_text, second_opinion_text)

        # Bbox safety validation (shared with _analyze_page_regions, see
        # validate_equation_bbox) — never discards the block or its OCR
        # output; a suspiciously-large bbox just adds a reason and, if the
        # block would otherwise have looked clean, bumps it to review.
        _bbox_is_valid, _bbox_reasons = validate_equation_bbox((px0, py0, px1, py1), image.width, image.height)
        if _bbox_reasons:
            math_quality_reasons = math_quality_reasons + _bbox_reasons
            if not _bbox_is_valid or ("SUSPICIOUSLY_LARGE_BBOX" in _bbox_reasons and math_quality == "GOOD"):
                math_quality = "NEEDS_REVIEW"

        results.append({
            "bbox": [px0, py0, px1, py1],
            "region_type": "mathematical_expression",
            "ocr_text_raw": primary_text,
            "second_opinion_text": second_opinion_text,
            "normalized_text": normalized_text,
            "math_normalizations": math_normalizations,
            "latex": None,  # UniMERNet evaluated and rejected this iteration (see module docstring above) — never populated
            "engine": "paddleocr",
            "confidence": block["confidence"],
            "math_quality": math_quality,
            "math_quality_reasons": math_quality_reasons,
            "review_required": True,
        })
    return results


# ---------------------------------------------------------------------------
# Core per-page / per-image pipeline
# ---------------------------------------------------------------------------

def _ocr_page_metadata(result: OCRResult, dpi: Optional[int]) -> tuple[str, dict]:
    """Shared by process_pdf/process_image: cleans OCR text and builds its metadata,
    flagging (never dropping) a page whose best attempt came back empty or
    low-confidence. `ocr_method` duplicates `ocr_engine` deliberately, matching
    the metadata shape documented in docs/content-management.md."""
    text_uncorrected = _light_clean(_strip_known_watermarks(result.text))
    tier = _confidence_tier(text_uncorrected, result.confidence)
    quality_label, quality_reasons = classify_page_quality(text_uncorrected, result.confidence)
    text, spelling_corrections = apply_spelling_corrections(text_uncorrected)

    ocr_lines = result.lines
    if ocr_lines:
        ocr_lines = [
            {**line, "text": _strip_known_watermarks(line.get("text", ""))}
            for line in ocr_lines
        ]

    metadata = {
        "ocr_engine": result.engine,
        "ocr_method": result.engine,
        "ocr_confidence": result.confidence,
        "confidence_tier": tier,
        "low_confidence": tier == "low",
        "preprocessing": result.preprocessing,
        "psm": result.psm,
        "dpi": dpi,
        "extraction_method": _describe_extraction(result),
        "ocr_lines": ocr_lines,
        "ocr_text_raw": result.text,
        "text_uncorrected": text_uncorrected,
        "spelling_corrections": spelling_corrections,
        "page_quality": quality_label,
        "review_reasons": quality_reasons,
        "visual_content_reference": (
            "[Possible visual content — refer to original PDF for this page]"
            if ("EMPTY_OUTPUT" in quality_reasons or "NEAR_EMPTY_OUTPUT" in quality_reasons)
            else None
        ),
        "math_regions": [],
        "visual_regions": [],
        "full_page_region_candidates": [],
        "math_equation_blocks": [],
    }
    return text, metadata


def _append_jsonl_record(record: ContentRecord, path: Path) -> None:
    """Append one record immediately, for page-level checkpointing — a crash
    partway through a long PDF loses only the page in progress, not every
    page already completed. Append-only, never rewrites prior lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record_to_dict(record), ensure_ascii=False))
        f.write("\n")


def _load_checkpoint(path: Optional[Path]) -> Dict[int, ContentRecord]:
    """Pages already completed by a prior, interrupted run — keyed by page
    number. skip_invalid=True tolerates a partially-written last line (the
    exact line being written when a crash happened)."""
    if path is None or not path.exists():
        return {}
    return {r.page: r for r in read_jsonl(path, skip_invalid=True) if r.page is not None}


_FULL_PAGE_AREA_RATIO_THRESHOLD = 0.6  # bbox area / page area >= this => "full-page candidate", not a localized region


def validate_equation_bbox(bbox: Tuple[int, int, int, int], page_width: int, page_height: int) -> Tuple[bool, List[str]]:
    """Reusable bbox safety check — shared by _analyze_page_regions (the
    coarse band mechanism, below) and _analyze_math_equation_blocks (the
    finer line-bbox mechanism) rather than duplicating the same area-ratio
    arithmetic twice. Never used to silently discard a region: callers
    record the returned reasons as review metadata and keep the region's
    OCR output regardless of what this returns.

    Returns (is_valid, reasons). is_valid is False only for malformed/
    out-of-bounds coordinates — which should not normally occur, since
    callers clamp against page bounds before building a bbox — and
    reasons can be non-empty even when is_valid is True (e.g. a
    structurally fine but suspiciously page-sized bbox)."""
    x0, y0, x1, y1 = bbox
    reasons: List[str] = []
    if x0 < 0 or y0 < 0 or x1 > page_width or y1 > page_height or x0 >= x1 or y0 >= y1:
        reasons.append("OUT_OF_BOUNDS")
        return False, reasons
    area = (x1 - x0) * (y1 - y0)
    page_area = page_width * page_height
    if page_area > 0 and (area / page_area) >= _FULL_PAGE_AREA_RATIO_THRESHOLD:
        reasons.append("SUSPICIOUSLY_LARGE_BBOX")
    return True, reasons


def _analyze_page_regions(image: Image.Image, page_number: int) -> Tuple[List[dict], List[dict], List[dict]]:
    """Opt-in, additive region-level analysis for one rendered page image.
    Reuses scripts.layout_detector.detect_regions + scripts.recognition_router.
    recognize_region directly (the same tooling scripts.hybrid_pipeline.
    process_page_hybrid wires together) rather than that orchestrator itself,
    specifically so a region whose bbox covers most of the page can be
    skipped BEFORE paying for a duplicate OCR call on it — see
    _FULL_PAGE_AREA_RATIO_THRESHOLD below. Never changes which text
    process_pdf() stores as the page's primary text.
    Returns (math_regions, visual_regions, full_page_candidates)."""
    from scripts.layout_detector import detect_regions, refine_region_with_text
    from scripts.recognition_router import recognize_region

    regions, canonical_image = detect_regions(image, page_number)

    math_regions: List[dict] = []
    visual_regions: List[dict] = []
    full_page_candidates: List[dict] = []

    for region in regions:
        _bbox_is_valid, _bbox_reasons = validate_equation_bbox(region.bbox, canonical_image.width, canonical_image.height)
        is_full_page = "SUSPICIOUSLY_LARGE_BBOX" in _bbox_reasons

        if is_full_page:
            # A region this large isn't a localized crop — it's (most of)
            # the whole page, already covered by process_pdf()'s own
            # primary OCR text. Re-running OCR on it here would be a
            # duplicate, wasted pass over content we've already recognized
            # once; record it as a candidate for a human to check against
            # the primary text instead of pretending it's a useful crop.
            full_page_candidates.append({
                "bbox": list(region.bbox),
                "region_type": region.region_type,
                "note": "full-page candidate (bbox covers most of the page) — see the page's primary text, not re-OCR'd separately",
            })
            continue

        if region.region_type in ("diagram", "table"):
            visual_regions.append({
                "bbox": list(region.bbox),
                "region_type": region.region_type,
                "review_required": True,
                "note": "[Possible visual content — refer to original PDF for this page]",
            })
            continue

        crop = canonical_image.crop(region.bbox)
        result = recognize_region(region, crop)
        if result.final_text:
            refine_region_with_text(region, result.final_text, tesseract_confidence=None)
        if region.region_type in ("mathematical_expression", "code"):
            math_regions.append({
                "bbox": list(region.bbox),
                "region_type": region.region_type,
                "text": _strip_known_watermarks(result.final_text),
                "confidence": result.final_confidence,
                "primary_engine": result.primary_engine,
                "fallback_invoked": result.fallback_invoked,
                "review_required": True,
            })
        elif region.region_type in ("diagram", "table"):  # refine_region_with_text can only promote INTO these from "unknown"
            visual_regions.append({
                "bbox": list(region.bbox),
                "region_type": region.region_type,
                "review_required": True,
                "note": "[Possible visual content — refer to original PDF for this page]",
            })

    return math_regions, visual_regions, full_page_candidates


def process_pdf(
    pdf_path: Path,
    meta: dict,
    only_page: Optional[int],
    dpi: int,
    preprocess: bool,
    checkpoint_path: Optional[Path] = None,
) -> List[ContentRecord]:
    """checkpoint_path, if given, makes this resumable: each page's record is
    appended to it immediately after processing (not just returned/written
    in bulk at the end), and any page already present there from a prior,
    interrupted run is reused instead of reprocessed. None (the default) is
    the original, non-checkpointed behavior — opt-in, not a default change."""
    page_count = get_pdf_page_count(pdf_path)
    pages = [only_page] if only_page else list(range(1, page_count + 1))
    records: List[ContentRecord] = []

    already_done = _load_checkpoint(checkpoint_path)
    if already_done:
        logger.info(f"{pdf_path.name}: resuming, {len(already_done)} page(s) already in {checkpoint_path.name}")

    for page_number in pages:
        page_index = page_number - 1
        if page_index < 0 or page_index >= page_count:
            logger.warning(f"{pdf_path.name}: page {page_number} out of range (1-{page_count}), skipping")
            continue

        if page_number in already_done:
            records.append(already_done[page_number])
            continue

        page_start = time.perf_counter()
        native_text = _strip_known_watermarks(extract_pdf_native_text(pdf_path, page_index))
        if len(native_text) >= _MIN_NATIVE_TEXT_CHARS:
            text_uncorrected = _light_clean(native_text)
            quality_label, quality_reasons = classify_page_quality(text_uncorrected, None)
            text, spelling_corrections = apply_spelling_corrections(text_uncorrected)
            metadata = {
                "ocr_engine": "pdf_text_layer",
                "ocr_method": "pdf_text_layer",
                "ocr_confidence": None,
                "confidence_tier": "native",
                "low_confidence": False,
                "preprocessing": None,
                "psm": None,
                "dpi": None,
                "extraction_method": "native_text_layer",
                "text_uncorrected": text_uncorrected,
                "spelling_corrections": spelling_corrections,
                "page_quality": quality_label,
                "review_reasons": quality_reasons,
                "visual_content_reference": None,
                "math_regions": [],
                "visual_regions": [],
                "full_page_region_candidates": [],
                "math_equation_blocks": [],
            }
        else:
            image = render_pdf_page(pdf_path, page_index, dpi=dpi)
            result = ocr_image(image, preprocess=preprocess)
            text, metadata = _ocr_page_metadata(result, dpi)
            if metadata["low_confidence"]:
                logger.warning(
                    f"{pdf_path.name} page {page_number}: low-confidence OCR "
                    f"(confidence={result.confidence}, method={metadata['extraction_method']}) — flagged for QA review, not dropped"
                )

            # Opt-in (SAARTHI_REGION_ANALYSIS=1), additive-only, and
            # SELECTIVE: only runs on pages the cheap, already-computed
            # page_quality already flagged as NEEDS_REVIEW/POOR_EXTRACTION —
            # a GOOD page has no identified problem for region analysis to
            # help with, so paying its OCR-per-region cost there would be
            # pure overhead (measured: region analysis added ~9% to total
            # processing time when run unconditionally on all 17 pages of
            # AnalogFilters.pdf — see docs/analogfilters-ocr-improvement-
            # report.md §7; only 2 of 17 pages were GOOD, so this gate saves
            # real time on any corpus with more straightforward pages).
            # Reuses the existing, already-tested layout_detector/
            # recognition_router tooling to find bbox-level mathematical/
            # code regions (separately re-OCR'd, never overwriting the
            # page's primary text above) and diagram/table regions (flagged
            # for review, never guessed). Never required: a failure here
            # falls back to the already-complete page-level result above.
            if _env_flag("SAARTHI_REGION_ANALYSIS") and metadata["page_quality"] != "GOOD":
                try:
                    metadata["math_regions"], metadata["visual_regions"], metadata["full_page_region_candidates"] = (
                        _analyze_page_regions(image, page_number)
                    )
                except Exception as exc:  # noqa: BLE001 — additive analysis must never break the primary page result
                    logger.warning(f"{pdf_path.name} page {page_number}: region analysis failed, continuing without it: {exc}")
                    metadata["math_regions"], metadata["visual_regions"], metadata["full_page_region_candidates"] = [], [], []

            # Opt-in (SAARTHI_MATH_ANALYSIS=1), additive, separately
            # configurable from SAARTHI_REGION_ANALYSIS above — a distinct,
            # more targeted stage (per-equation-block, not per-band). Gated
            # the same way (page_quality != "GOOD") AND requires ocr_lines
            # (only populated when PaddleOCR won the page — Tesseract's
            # OCRResult has no per-line bboxes to group; those pages keep
            # relying on the coarser full_page_region_candidates above,
            # an honest, documented limitation, not silently worked around).
            # _group_math_lines_from_ocr_lines itself returns [] on a page
            # with no math-candidate lines, so a page with text but no
            # equations costs nothing extra beyond that cheap check.
            if _env_flag("SAARTHI_MATH_ANALYSIS") and metadata["page_quality"] != "GOOD" and metadata.get("ocr_lines"):
                try:
                    metadata["math_equation_blocks"] = _analyze_math_equation_blocks(image, metadata["ocr_lines"])
                except Exception as exc:  # noqa: BLE001 — additive analysis must never break the primary page result
                    logger.warning(f"{pdf_path.name} page {page_number}: math equation-block analysis failed, continuing without it: {exc}")
                    metadata["math_equation_blocks"] = []
            else:
                metadata["math_equation_blocks"] = []

        metadata["processing_time_seconds"] = round(time.perf_counter() - page_start, 3)

        # Every page in range gets a record, even if OCR text came back empty —
        # low_confidence/ocr_confidence make that visible instead of silently
        # vanishing the page from the output.
        record = ContentRecord(
            content_id=f"{meta['note_id']}_PAGE_{page_number:02d}",
            content_type=ContentType.PDF_NOTE,
            course=meta["course"],
            topic=meta["topic"],
            source=pdf_path.name,
            source_id=meta["note_id"],
            lecture=None,
            page=page_number,
            start_time=None,
            end_time=None,
            text=text,
            processing_status=ProcessingStatus.PROCESSED,
            qa_status=QAStatus.PENDING,
            metadata=metadata,
        )
        records.append(record)
        if checkpoint_path is not None:
            _append_jsonl_record(record, checkpoint_path)
    return records


def process_image(image_path: Path, meta: dict, preprocess: bool, dpi: Optional[int] = None) -> List[ContentRecord]:
    image = Image.open(image_path)
    result = ocr_image(image, preprocess=preprocess)
    text, metadata = _ocr_page_metadata(result, dpi)
    if metadata["low_confidence"]:
        logger.warning(
            f"{image_path.name}: low-confidence OCR "
            f"(confidence={result.confidence}, method={metadata['extraction_method']}) — flagged for QA review, not dropped"
        )
    return [
        ContentRecord(
            content_id=f"{meta['note_id']}_PAGE_01",
            content_type=ContentType.HANDWRITTEN_NOTE,
            course=meta["course"],
            topic=meta["topic"],
            source=image_path.name,
            source_id=meta["note_id"],
            lecture=None,
            page=1,
            start_time=None,
            end_time=None,
            text=text,
            processing_status=ProcessingStatus.PROCESSED,
            qa_status=QAStatus.PENDING,
            metadata=metadata,
        )
    ]


def process_note_file(
    source_path: Path,
    output_dir: Path,
    only_page: Optional[int],
    dpi: int,
    preprocess: bool,
    cli_course: Optional[str],
    cli_topic: Optional[str],
    cli_note_id: Optional[str],
    resume: bool = False,
) -> dict:
    start = time.perf_counter()
    meta = resolve_metadata(source_path, cli_course, cli_topic, cli_note_id)
    jsonl_path = output_dir / f"{source_path.stem}.jsonl"
    try:
        if source_path.suffix.lower() in PDF_EXTENSIONS:
            # checkpoint_path=jsonl_path itself: each page is appended there as
            # it completes, so a crash mid-file leaves exactly the pages done
            # so far — the next --resume run reads that same file and picks
            # up where it left off, no separate checkpoint file to manage.
            records = process_pdf(source_path, meta, only_page, dpi, preprocess, checkpoint_path=jsonl_path if resume else None)
        else:
            records = process_image(source_path, meta, preprocess, dpi)

        if not records:
            raise RuntimeError("No pages produced usable text")

        write_jsonl(records, jsonl_path)

        duration = time.perf_counter() - start
        log_operation(
            file=source_path.name,
            type_="notes",
            operation="ocr",
            status="success",
            duration_seconds=round(duration, 3),
            output=str(jsonl_path),
            error=None,
            pages=len(records),
        )
        logger.info(f"{source_path.name}: {len(records)} page(s) -> {jsonl_path}")
        return {"status": "success", "pages": len(records), "output": str(jsonl_path)}

    except Exception as exc:  # noqa: BLE001 — one bad file must not abort the batch
        duration = time.perf_counter() - start
        log_operation(
            file=source_path.name,
            type_="notes",
            operation="ocr",
            status="failed",
            duration_seconds=round(duration, 3),
            output=None,
            error=str(exc),
        )
        logger.error(f"{source_path.name}: FAILED — {exc}")
        return {"status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest notes (PDF/image) into canonical OCR JSONL.")
    parser.add_argument("--input", type=Path, default=RAW_NOTES_DIR)
    parser.add_argument("--output", type=Path, default=PROCESSED_OCR_DIR)
    parser.add_argument("--file", type=str, default=None, help="Process a single file (name or path).")
    parser.add_argument("--page", type=int, default=None, help="Restrict processing to one page (1-indexed, PDF only).")
    parser.add_argument("--dpi", type=int, default=350, help="Render resolution for scanned PDF pages (300-400 recommended for handwriting).")
    parser.add_argument("--no-preprocess", action="store_true", help="Disable image preprocessing before OCR.")
    parser.add_argument(
        "--resume", action="store_true",
        help="Checkpoint each PDF page as it completes and skip pages already in the output "
             "file from a prior interrupted run — for large batches (e.g. an 800-page job) "
             "where a crash partway through shouldn't mean reprocessing everything already done.",
    )
    parser.add_argument("--course", default=None)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--note-id", default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)

    if args.file:
        candidate = Path(args.file)
        source_path = candidate if candidate.is_absolute() or candidate.exists() else args.input / candidate
        note_files = [source_path]
    else:
        if not args.input.exists():
            logger.error(f"Input directory not found: {args.input}")
            return 1
        note_files = sorted(p for p in args.input.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)

    if not note_files:
        logger.warning(f"No note files found in {args.input}")
        return 0

    succeeded = 0
    failed = 0
    for source_path in note_files:
        if not source_path.exists():
            logger.error(f"File not found: {source_path}")
            failed += 1
            continue
        result = process_note_file(
            source_path,
            args.output,
            args.page,
            args.dpi,
            not args.no_preprocess,
            args.course,
            args.topic,
            args.note_id,
            resume=args.resume,
        )
        if result["status"] == "success":
            succeeded += 1
        else:
            failed += 1

    logger.info(f"Done. {succeeded} succeeded, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
