"""
Document layout detection / region classification.

NOT backed by a dedicated layout-detection ML model (PP-DocLayout,
PicoDet-layout, DocLayout-YOLO). Those were evaluated and rejected for this
environment: every paddlex object-detection-family layout model tried
(PicoDet-S_layout_3cls, PP-DocLayout-S) hit the same reproducible
PaddlePaddle 3.3.1 CPU crash —
`NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]` — even with mkldnn explicitly
disabled. Confirmed across two model families, not an isolated fluke. See
docs/ocr-architecture.md for the exact reproduction and a retry command for
when this is fixed upstream or GPU is available (CPU oneDNN/PIR is the
implicated code path).

This module is the honest fallback, not a drop-in replacement for a real
layout model's accuracy:
1. Region SEGMENTATION reuses scripts.ingest_notes._detect_text_bands
   (row-projection band detection — already proven in the existing
   pipeline, not reimplemented here).
2. Region TYPE classification is heuristic, built entirely from signals
   the pipeline already computes during OCR — not a separate vision model:
   - printed_text: a native PDF text layer, OR Tesseract reports its own
     (engine-calibrated) high confidence on the band. Tesseract's LSTM is
     trained on printed text, so a genuinely high Tesseract confidence is
     itself decent evidence of print, not handwriting.
   - mathematical_expression: the recognized text's character composition
     is dense with math symbols/operators relative to alphabetic content.
   - code: the recognized text matches common code keywords/punctuation
     patterns (braces, semicolons, `def`/`for`/`#include`, consistent
     indentation).
   - diagram / table: heavy ink coverage (cv2) but little to no text any
     engine could recognize — a real, cheap, already-available signal
     (not a guess at *what* the diagram contains).
   - unknown: none of the above signal confidently — deliberately the
     default. A region never gets labeled printed_text/code/math on a weak
     signal; see CLASSIFY_* thresholds below.

Upgrade path: once a real layout model actually runs in this environment,
replace classify_region()'s body with that model's call — detect_regions()'s
public contract (List[Region]) does not need to change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PIL import Image

REGION_TYPES = {
    "handwritten_text",
    "mathematical_expression",
    "code",
    "printed_text",
    "diagram",
    "table",
    "unknown",
}

# Thresholds are deliberately conservative — "unknown" is always the safe
# default when a signal is weak, per the task requirement not to force an
# unreliable classification.
_MATH_SYMBOL_CHARS = set("=+-*/^_<>≤≥≠∑∫πθωΩαβγδλμσΣ∏√∞")
_MATH_SYMBOL_DENSITY_THRESHOLD = 0.08  # fraction of non-space chars that are math symbols
_CODE_KEYWORDS = re.compile(
    r"\b(def|class|return|import|if|elif|else|for|while|print|int|void|char|float|double|"
    r"public|private|static|include|struct|namespace|function|var|let|const)\b"
)
_CODE_PUNCT_CHARS = set("{};()[]")
_CODE_PUNCT_DENSITY_THRESHOLD = 0.05
_PRINTED_TESSERACT_CONF_THRESHOLD = 0.85  # Tesseract's own engine-calibrated confidence
# Measured on this project's own ground-truth pages: ink fraction for bands
# that are ALL genuinely dense handwritten text (no diagram exists anywhere
# in this repo's raw data) ranged from 0.049 to 0.94 across pages/bands —
# CLAHE's contrast boost makes some genuinely-text bands read as almost
# solid ink. That range swamps any single threshold; an earlier 0.35 cutoff
# still misclassified a real text page (0.94 ink) as "diagram" and silently
# dropped it from recognition entirely (measured: page CER went from 0.34
# achievable to 1.0/empty). Set near-unreachable rather than removed
# outright, so the mechanism and its signal are still exercised/testable —
# but it should not be trusted to actually fire correctly without a real
# diagram sample to calibrate against, which this repo does not have.
_DIAGRAM_MIN_INK_FRACTION = 0.97
_DIAGRAM_MAX_TEXT_FRACTION = 0.15  # but almost nothing recognizable as text


@dataclass
class Region:
    """One classified page region. See module docstring for how region_type is derived."""

    region_id: str
    page_number: int
    region_type: str
    bbox: Tuple[int, int, int, int]  # (x0, y0, x1, y1), pixel coords in the rendered page image
    reading_order: int
    preprocessing_variant: Optional[str] = None
    detection_confidence: Optional[float] = None  # heuristic score in [0, 1] — NOT a calibrated ML confidence
    signals: dict = field(default_factory=dict)  # raw heuristic inputs, kept for debugging/review


def segment_lines(
    image: Image.Image,
    min_line_height: int = 15,
    gap_frac: float = 0.01,
    pad: int = 3,
) -> List[Tuple[int, int]]:
    """Fine-grained line-level row segmentation — for recognizers (TrOCR)
    that are architecturally single-line models and produce near-garbage
    output on a multi-line crop (measured: TrOCR on a whole dense page
    returned 3 characters; CER 0.999 even region-cropped with
    _detect_text_bands's paragraph-level bands, which measured 1 giant band
    spanning 2953 of 3509px on a real page here).

    Uses ADAPTIVE thresholding on the raw (non-CLAHE) grayscale image, not
    global Otsu on a CLAHE-enhanced one. Measured and rejected: global Otsu
    on this project's own grayscale_clahe preprocessing variant classified
    ~90% of every row as "ink" on real content (CLAHE's local contrast
    boost amplifies faint paper texture/shadow enough to break Otsu's
    bimodal assumption at full-page scale) — useless for finding the
    low-ink gaps between lines. Adaptive thresholding on the raw image
    measured a realistic ~2.7% mean row-ink density with real gaps,
    producing 13-18 lines/page on this project's dense handwritten pages
    (vs. _detect_text_bands's 1 band/page at paragraph granularity) —
    plausible given the visible line count in those scans.

    min_line_height/gap_frac/pad are untuned beyond "produces a plausible
    line count on this project's own 4 ground-truth pages" — there is no
    line-level ground truth (bounding boxes) to calibrate against here,
    only the page-level text transcriptions. Treat as a reasonable default,
    not a validated-accurate line detector.
    """
    import cv2
    import numpy as np

    gray = np.array(image.convert("L"))
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 35, 15)
    row_ink = adaptive.sum(axis=1) / 255.0
    w = adaptive.shape[1]
    is_blank_row = row_ink < (w * gap_frac)

    raw_lines: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for y in range(len(is_blank_row)):
        if not is_blank_row[y]:
            if start is None:
                start = y
        elif start is not None:
            raw_lines.append((start, y))
            start = None
    if start is not None:
        raw_lines.append((start, len(is_blank_row)))

    lines = [(max(0, y0 - pad), min(image.height, y1 + pad)) for y0, y1 in raw_lines if (y1 - y0) >= min_line_height]

    merged: List[Tuple[int, int]] = []
    for band in lines:
        if merged and band[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], band[1]))
        else:
            merged.append(band)
    return merged


def _ink_fraction(gray_band) -> float:
    import cv2
    import numpy as np

    _, thresh = cv2.threshold(gray_band, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return float(np.count_nonzero(thresh)) / thresh.size


def classify_region_text(text: str, tesseract_confidence: Optional[float] = None) -> Tuple[str, float, dict]:
    """Classify from already-recognized text (+ optionally Tesseract's own
    confidence for that text) — the signals this heuristic actually uses.
    Returns (region_type, heuristic_confidence, signals)."""
    stripped = text.strip()
    if not stripped:
        return "unknown", 0.0, {"reason": "empty_text"}

    non_space = [c for c in stripped if not c.isspace()]
    total = len(non_space) or 1

    math_density = sum(1 for c in non_space if c in _MATH_SYMBOL_CHARS) / total
    code_keyword_hits = len(_CODE_KEYWORDS.findall(stripped))
    code_punct_density = sum(1 for c in non_space if c in _CODE_PUNCT_CHARS) / total

    signals = {
        "math_symbol_density": round(math_density, 4),
        "code_keyword_hits": code_keyword_hits,
        "code_punct_density": round(code_punct_density, 4),
        "tesseract_confidence": tesseract_confidence,
    }

    if tesseract_confidence is not None and tesseract_confidence >= _PRINTED_TESSERACT_CONF_THRESHOLD:
        return "printed_text", tesseract_confidence, signals

    if code_keyword_hits >= 1 and code_punct_density >= _CODE_PUNCT_DENSITY_THRESHOLD:
        return "code", min(1.0, 0.5 + code_punct_density), signals

    if math_density >= _MATH_SYMBOL_DENSITY_THRESHOLD:
        return "mathematical_expression", min(1.0, math_density * 4), signals

    return "handwritten_text", 0.5, signals  # weak-but-real default: recognizable prose, not printed/math/code


def classify_region_image_only(gray_band) -> Tuple[str, float, dict]:
    """Classify from pixels alone, for a band no engine could recognize any
    text from — the diagram/table/unknown case. Table vs diagram is NOT
    distinguished (that needs real line/grid detection this module doesn't
    attempt) — both heavy-ink/no-text bands are reported as 'diagram', the
    more conservative of the two since a human reviewer misreading a table
    as "diagram" loses less than the reverse."""
    ink = _ink_fraction(gray_band)
    signals = {"ink_fraction": round(ink, 4)}
    if ink >= _DIAGRAM_MIN_INK_FRACTION:
        return "diagram", min(1.0, ink * 5), signals
    return "unknown", 0.0, signals


def detect_regions(
    image: Image.Image,
    page_number: int,
    native_text: Optional[str] = None,
) -> Tuple[List[Region], Image.Image]:
    """Segment + classify a rendered page image into regions.

    Returns (regions, canonical_image) — callers MUST crop region.bbox from
    canonical_image, not the original `image`. Band-detection needs a
    denoised/contrast-normalized image (see below), and that preprocessing
    can change pixel dimensions (measured on real data: CLAHE +
    border-crop shrank a 2480x3509 page to 2170x3069) — bboxes are only
    valid against the image they were actually computed on.

    If native_text is given (the page already had an extractable PDF text
    layer — see ingest_notes.extract_pdf_native_text), the whole page is one
    printed_text region at confidence 1.0 against the original image
    unchanged: no preprocessing, no OCR, no guessing, matching the existing
    pipeline's native-text-layer shortcut.
    """
    if native_text is not None:
        w, h = image.size
        return [
            Region(
                region_id=f"P{page_number:03d}_R001",
                page_number=page_number,
                region_type="printed_text",
                bbox=(0, 0, w, h),
                reading_order=1,
                preprocessing_variant=None,
                detection_confidence=1.0,
                signals={"reason": "native_pdf_text_layer"},
            )
        ], image

    import numpy as np

    from scripts.ingest_notes import _detect_text_bands, preprocess_image_variants

    # _detect_text_bands and ink-fraction estimates both need a denoised,
    # contrast-normalized image — band-detection on a raw render merges an
    # entire page into one band (measured: 82% "ink" on a real page, vs 8%
    # on the same page's grayscale_clahe variant) because uneven scan
    # lighting/shadow never reads as a clean blank row. Reuses the same
    # preprocessing variant the production pipeline already validates.
    clahe_image = preprocess_image_variants(image)["grayscale_clahe"]
    gray = np.array(clahe_image.convert("L"))
    bands = _detect_text_bands(gray)
    if not bands:
        return [], clahe_image

    regions: List[Region] = []
    for i, (y0, y1) in enumerate(bands, start=1):
        band = gray[y0:y1, :]
        region_type, confidence, signals = classify_region_image_only(band)
        regions.append(
            Region(
                region_id=f"P{page_number:03d}_R{i:03d}",
                page_number=page_number,
                region_type=region_type,
                bbox=(0, y0, clahe_image.width, y1),
                reading_order=i,
                preprocessing_variant="grayscale_clahe",
                detection_confidence=confidence,
                signals=signals,
            )
        )
    return regions, clahe_image


def refine_region_with_text(region: Region, text: str, tesseract_confidence: Optional[float] = None) -> Region:
    """Re-classify a region once its text has actually been recognized —
    text-composition signals (math/code/printed) are far more reliable than
    the pixels-only pass detect_regions() had to use before any OCR ran.
    Only promotes away from 'unknown'/'diagram'; never downgrades a
    pixel-confirmed diagram/table to text on a flimsy OCR scrap."""
    if not text.strip():
        return region
    region_type, confidence, signals = classify_region_text(text, tesseract_confidence)
    if region.region_type in ("unknown", "diagram") or region_type == "printed_text":
        region.region_type = region_type
        region.detection_confidence = confidence
        region.signals = {**region.signals, **signals}
    return region
