"""
Routes a classified region (scripts.layout_detector.Region) to a recognition
engine, based on region_type. Single place model selection lives — nothing
in ingest_notes.py hardcodes which engine handles which content type.

Default routing table (region_type -> primary, fallback):

    handwritten_text          paddleocr   -> trocr
    printed_text               paddleocr   -> tesseract_light
    mathematical_expression    paddleocr   -> trocr   (see "Math/code" below)
    code                       paddleocr   -> trocr   (see "Math/code" below)
    diagram / table             (none — human review only)
    unknown                     paddleocr   -> tesseract_light

Math/code: the task's target architecture specifies UniMERNet/PP-FormulaNet
for math and HTR-VT for handwritten code. HTR-VT and UniMERNet now both run
successfully on CPU (see docs/ocr-architecture.md) but aren't wired in as
working routes: HTR-VT only has a wrong-language (LAM/Italian, not IAM/
English) checkpoint available, and UniMERNet needs a per-region crop
pipeline (192x672 input) not yet built. PP-FormulaNet-S runs but was
measured to fail outright on real handwritten formulas. See
UNAVAILABLE_ENGINES below and docs/ocr-architecture.md for the exact,
reproduced reason for each. Math and code regions are therefore routed
through the same general handwriting path as plain prose (paddleocr ->
trocr) rather than silently downgraded to
"unknown"/skipped — a transcribed-but-unspecialized result is more useful to
a reviewer than nothing, and `verification.flag_region_for_review()` always
marks these two types for human review regardless of recognition confidence,
so no one downstream mistakes "transcribed" for "verified correct LaTeX/code".

To use a backend not in ROUTING_TABLE's defaults (or to point a region type
at a different already-available engine), pass a `config` override to
route_region()/recognize_region() — see RouterConfig.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from PIL import Image

from scripts.ingest_notes import OCRResult, _attempt_rank, ocr_image, run_handwriting_ocr, run_light_tesseract
from scripts.layout_detector import Region

# Review-only region types never get routed to a recognizer — the task is
# explicit that diagram/table content should go to human review, not a
# guessed transcription.
REVIEW_ONLY_REGION_TYPES = {"diagram", "table"}

# Region types where recognition succeeding is not the same as the content
# being verified correct (a transcribed equation can still have a wrong
# subscript; transcribed code can still be syntactically invalid) — always
# flagged for review downstream regardless of engine confidence.
ALWAYS_FLAG_FOR_REVIEW_REGION_TYPES = {"mathematical_expression", "code"}


class RecognitionEngineUnavailable(RuntimeError):
    """Raised when a region is routed to an engine this environment cannot
    run — never silently skipped, never a fabricated result."""


# Engines evaluated for this task but not wired in as working routes. Keyed
# by the name a RouterConfig override could name them with; selecting one
# raises RecognitionEngineUnavailable with the reason below instead of
# silently falling through to something else.
UNAVAILABLE_ENGINES: Dict[str, str] = {
    "htr_vt": (
        "HTR-VT DOES run on CPU in an isolated venv (verified: real checkpoint "
        "loaded strict=True, forward pass works — the earlier 'needs CUDA/apex' "
        "finding was wrong, see docs/ocr-architecture.md). Not wired in because "
        "the only checkpoint obtained is LAM (Italian historical manuscripts), "
        "not IAM (English) — an IAM checkpoint needs its own FKI dataset "
        "registration to reconstruct the matching charset, not completed. "
        "Using the LAM checkpoint on English content would measure 'wrong "
        "language', not model quality."
    ),
    "pp_formulanet": (
        "PP-FormulaNet-S was downloaded and run successfully, but produced "
        "degenerate repeated-token output (e.g. '\\\\\\\\ \\\\\\\\ \\\\\\\\ ...') with zero "
        "usable content on two different real handwritten-formula crops from "
        "this project's own data — a measured failure, not a compatibility "
        "issue. It is trained on printed/typeset formula images and does not "
        "generalize to this project's handwriting. See "
        "docs/ocr-architecture.md for the exact reproduction."
    ),
}

# Engines that actually work here, each exposing (image: Image.Image) -> OCRResult.
# "tesseract" is the full multi-variant sweep (ingest_notes.ocr_image — ~15-20
# actual Tesseract invocations); "tesseract_light" is a single --psm 6 attempt
# (ingest_notes.run_light_tesseract). The routing table below uses the light
# version for FALLBACK slots — see the comment on run_light_tesseract for why:
# measured, chaining the full sweep per low-confidence region pushed the
# hybrid pipeline to 263.6s/page for an 11% relative CER gain over plain
# PaddleOCR. "tesseract" (full sweep) stays available for explicit use as a
# PRIMARY engine, where the thorough variant search is worth its cost.
#
# "unimernet" is a real, working engine (verified: real formula crop decoded
# to valid, well-formed LaTeX — see docs/ocr-architecture.md §4) but needs
# SAARTHI_UNIMERNET_PYTHON/SAARTHI_UNIMERNET_CHECKPOINT configured (isolated
# Python 3.11 venv — see scripts/unimernet_adapter.py); raises
# UniMERNetUnavailable with a clear setup message if unset, same honesty
# pattern as UNAVAILABLE_ENGINES above. NOT in ROUTING_TABLE's defaults —
# opt in via a RouterConfig override — since most environments won't have
# the isolated venv set up, and it hasn't been measured as better than
# PaddleOCR on this content yet (only shown structurally valid on one crop).
AVAILABLE_ENGINES: Dict[str, Callable[[Image.Image], OCRResult]] = {
    "tesseract": lambda image: ocr_image(image, preprocess=True),
    "tesseract_light": lambda image: run_light_tesseract(image),
    "paddleocr": lambda image: run_handwriting_ocr(image, "paddleocr"),
    "trocr": lambda image: run_handwriting_ocr(image, "trocr"),
    "unimernet": lambda image: _recognize_formula_or_unavailable(image),
}


def _recognize_formula_or_unavailable(image: Image.Image) -> OCRResult:
    from scripts.unimernet_adapter import UniMERNetUnavailable, recognize_formula

    try:
        return recognize_formula(image)
    except UniMERNetUnavailable as exc:
        raise RecognitionEngineUnavailable(str(exc)) from exc

ROUTING_TABLE: Dict[str, Tuple[str, Optional[str]]] = {
    "handwritten_text": ("paddleocr", "trocr"),
    "printed_text": ("paddleocr", "tesseract_light"),
    "mathematical_expression": ("paddleocr", "trocr"),
    "code": ("paddleocr", "trocr"),
    # paddleocr, not tesseract: "unknown" means "not yet classified", not
    # "confirmed non-text" — routing the uncertain case to this project's
    # worst-measured engine (Tesseract: CER 0.769 vs PaddleOCR's 0.341 on
    # this content) was a bug, not a deliberate conservative choice.
    "unknown": ("paddleocr", "tesseract_light"),
}


@dataclass
class RouterConfig:
    """Override which engine handles which region_type. Any value not in
    AVAILABLE_ENGINES is checked against UNAVAILABLE_ENGINES for an honest
    error; anything in neither raises a plain KeyError-style ValueError."""

    routing_table: Dict[str, Tuple[str, Optional[str]]] = field(default_factory=lambda: dict(ROUTING_TABLE))

    def for_region_type(self, region_type: str) -> Tuple[str, Optional[str]]:
        if region_type not in self.routing_table:
            raise ValueError(f"No route configured for region_type={region_type!r}")
        return self.routing_table[region_type]


@dataclass
class RegionResult:
    region: Region
    primary_engine: str
    primary_result: Optional[OCRResult]
    fallback_engine: Optional[str]
    fallback_result: Optional[OCRResult]
    fallback_invoked: bool
    final_text: str
    final_confidence: Optional[float]
    review_required: bool
    review_reason: Optional[str]


def _invoke_engine(engine_name: str, image: Image.Image) -> OCRResult:
    if engine_name in AVAILABLE_ENGINES:
        return AVAILABLE_ENGINES[engine_name](image)
    if engine_name in UNAVAILABLE_ENGINES:
        raise RecognitionEngineUnavailable(f"{engine_name!r} is not available: {UNAVAILABLE_ENGINES[engine_name]}")
    raise ValueError(f"Unknown recognition engine {engine_name!r}")


def recognize_region(
    region: Region,
    image_crop: Image.Image,
    config: Optional[RouterConfig] = None,
) -> RegionResult:
    """Run the configured primary engine for region.region_type, falling
    back only if the primary result is empty/low-confidence (same
    best-of-N philosophy as ingest_notes._attempt_rank — reused directly,
    not reimplemented)."""
    config = config or RouterConfig()

    if region.region_type in REVIEW_ONLY_REGION_TYPES:
        return RegionResult(
            region=region, primary_engine="none", primary_result=None,
            fallback_engine=None, fallback_result=None, fallback_invoked=False,
            final_text="", final_confidence=None,
            review_required=True, review_reason=f"region_type={region.region_type} is never auto-recognized",
        )

    primary_name, fallback_name = config.for_region_type(region.region_type)
    primary_result = _invoke_engine(primary_name, image_crop)
    best = primary_result
    fallback_result: Optional[OCRResult] = None
    fallback_invoked = False

    primary_rank = _attempt_rank(primary_result.text, primary_result.confidence)
    low_confidence = primary_rank[0] < 2 or (primary_result.confidence or 0.0) < 0.5
    if fallback_name and low_confidence:
        fallback_invoked = True
        try:
            fallback_result = _invoke_engine(fallback_name, image_crop)
            fallback_rank = _attempt_rank(fallback_result.text, fallback_result.confidence)
            # Accept the fallback only when it strictly improves RANK TIER
            # (real text where primary had none, or a confidence score where
            # primary had none) — never when both engines already report
            # their OWN confidence (tier 2) and the only difference is which
            # raw number happens to be larger. Different engines' confidence
            # scores are not calibrated against each other (documented
            # throughout this project — see docs/content-management.md), so
            # "pick whichever number is bigger across engines" is not a
            # valid comparison, even though _attempt_rank's tuple ordering
            # would technically let one win that way via plain `>`. When
            # both reach tier 2, primary is left standing;
            # verification.check_model_disagreement flags a real
            # disagreement between the two for human review instead of this
            # function silently picking a side on an uncalibrated number.
            if fallback_rank[0] > primary_rank[0]:
                best = fallback_result
        except RecognitionEngineUnavailable:
            raise  # a configured-but-unavailable fallback must not be swallowed silently
        except Exception:  # noqa: BLE001 — fallback is best-effort; primary result must still stand
            pass

    review_required = region.region_type in ALWAYS_FLAG_FOR_REVIEW_REGION_TYPES or not best.text.strip()
    review_reason = None
    if region.region_type in ALWAYS_FLAG_FOR_REVIEW_REGION_TYPES:
        review_reason = f"region_type={region.region_type} is always flagged — recognized != verified"
    elif not best.text.strip():
        review_reason = "empty recognition output"

    return RegionResult(
        region=region,
        primary_engine=primary_name,
        primary_result=primary_result,
        fallback_engine=fallback_name if fallback_invoked else None,
        fallback_result=fallback_result,
        fallback_invoked=fallback_invoked,
        final_text=best.text,
        final_confidence=best.confidence,
        review_required=review_required,
        review_reason=review_reason,
    )
