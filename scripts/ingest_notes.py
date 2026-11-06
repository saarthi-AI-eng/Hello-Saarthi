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
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl

logger = get_logger("ingest_notes")

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS

_MIN_NATIVE_TEXT_CHARS = 20  # below this, a PDF page is treated as scanned/image-based

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
    if the result is still low-confidence and SAARTHI_HANDWRITING_OCR is set — an
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

    # Optional handwriting-specialized OCR fallback — only reached when
    # Tesseract's best result is genuinely low-confidence AND the operator
    # opted in via SAARTHI_HANDWRITING_OCR. If the backend/dependency is
    # unavailable, this must never break the normal Tesseract-only pipeline.
    tier = _confidence_tier(best.text, best.confidence)
    handwriting_backend = os.environ.get("SAARTHI_HANDWRITING_OCR", "").strip().lower()
    if tier == "low" and handwriting_backend:
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


def _get_paddleocr_instance(lang: str):
    """Lazily construct and cache a PaddleOCR pipeline instance (one per
    language — re-creating it per page would reload the detection/recognition
    models every call)."""
    if lang not in _PADDLEOCR_INSTANCE_CACHE:
        from paddleocr import PaddleOCR

        logger.info(f"Loading PaddleOCR (lang={lang!r}, first use only, cached for this run)...")
        _PADDLEOCR_INSTANCE_CACHE[lang] = PaddleOCR(
            lang=lang,
            text_detection_model_name=os.environ.get("SAARTHI_PADDLEOCR_DET_MODEL") or None,
            text_recognition_model_name=os.environ.get("SAARTHI_PADDLEOCR_REC_MODEL") or None,
            device=os.environ.get("SAARTHI_PADDLEOCR_DEVICE", "cpu"),
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
# Core per-page / per-image pipeline
# ---------------------------------------------------------------------------

def _ocr_page_metadata(result: OCRResult, dpi: Optional[int]) -> tuple[str, dict]:
    """Shared by process_pdf/process_image: cleans OCR text and builds its metadata,
    flagging (never dropping) a page whose best attempt came back empty or
    low-confidence. `ocr_method` duplicates `ocr_engine` deliberately, matching
    the metadata shape documented in docs/content-management.md."""
    text = _light_clean(result.text)
    tier = _confidence_tier(text, result.confidence)
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
        "ocr_lines": result.lines,
    }
    return text, metadata


def process_pdf(
    pdf_path: Path,
    meta: dict,
    only_page: Optional[int],
    dpi: int,
    preprocess: bool,
) -> List[ContentRecord]:
    page_count = get_pdf_page_count(pdf_path)
    pages = [only_page] if only_page else list(range(1, page_count + 1))
    records: List[ContentRecord] = []

    for page_number in pages:
        page_index = page_number - 1
        if page_index < 0 or page_index >= page_count:
            logger.warning(f"{pdf_path.name}: page {page_number} out of range (1-{page_count}), skipping")
            continue

        native_text = extract_pdf_native_text(pdf_path, page_index)
        if len(native_text) >= _MIN_NATIVE_TEXT_CHARS:
            text = _light_clean(native_text)
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

        # Every page in range gets a record, even if OCR text came back empty —
        # low_confidence/ocr_confidence make that visible instead of silently
        # vanishing the page from the output.
        records.append(
            ContentRecord(
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
        )
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
) -> dict:
    start = time.perf_counter()
    meta = resolve_metadata(source_path, cli_course, cli_topic, cli_note_id)
    try:
        if source_path.suffix.lower() in PDF_EXTENSIONS:
            records = process_pdf(source_path, meta, only_page, dpi, preprocess)
        else:
            records = process_image(source_path, meta, preprocess, dpi)

        if not records:
            raise RuntimeError("No pages produced usable text")

        jsonl_path = output_dir / f"{source_path.stem}.jsonl"
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
        )
        if result["status"] == "success":
            succeeded += 1
        else:
            failed += 1

    logger.info(f"Done. {succeeded} succeeded, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
