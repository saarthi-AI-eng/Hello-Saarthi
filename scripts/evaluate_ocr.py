"""
Compare OCR engines against a hand-transcribed ground-truth set using
Character/Word Error Rate (CER/WER) and related metrics. Never claims an
accuracy number that wasn't actually measured — if the ground-truth file is
missing or empty, this reports that plainly instead of inventing results.

CER/WER are computed with a plain Levenshtein edit distance (stdlib only —
deliberately not an extra dependency for something this small). See
_normalize_for_cer/_normalize_for_wer for the exact, documented
normalization rules.

Usage:
    python -m scripts.evaluate_ocr
    python -m scripts.evaluate_ocr --engines tesseract,paddleocr
    python -m scripts.evaluate_ocr --ground-truth data/evaluation/ocr_ground_truth.jsonl
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from scripts.content_common import EVALUATION_DIR, REPO_ROOT, get_logger
from scripts.ingest_notes import OCRResult, ocr_image, render_pdf_page, run_handwriting_ocr

logger = get_logger("evaluate_ocr")


# ---------------------------------------------------------------------------
# Edit distance / CER / WER
# ---------------------------------------------------------------------------

def _levenshtein(a: List[str], b: List[str]) -> int:
    """Classic O(len(a)*len(b)) edit distance over a list of tokens (chars or words).
    Rolling two-row DP — plenty fast for page-length OCR text."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, token_a in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, token_b in enumerate(b, start=1):
            if token_a == token_b:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr
    return prev[-1]


def _normalize_for_cer(text: str) -> str:
    """Case-sensitive (OCR case errors are real errors); internal whitespace
    runs (including newlines, since engines disagree on line-wrapping for the
    same content) collapsed to a single space; leading/trailing trimmed."""
    return " ".join(text.split())


def _normalize_for_wer(text: str) -> str:
    """Same whitespace handling as CER, plus lowercased — word-level
    comparison conventionally ignores case. Punctuation is NOT stripped:
    this pipeline's own philosophy (see ingest_notes.py) is to never
    guess away characters that might be meaningful math/technical notation."""
    return _normalize_for_cer(text).lower()


def compute_cer(reference: str, hypothesis: str) -> Optional[float]:
    """None (not 0.0) when the reference is empty — a 0% error rate against
    nothing to measure against would be misleading, not honest."""
    ref = _normalize_for_cer(reference)
    hyp = _normalize_for_cer(hypothesis)
    if not ref:
        return None
    return _levenshtein(list(ref), list(hyp)) / len(ref)


def compute_wer(reference: str, hypothesis: str) -> Optional[float]:
    ref = _normalize_for_wer(reference).split()
    hyp = _normalize_for_wer(hypothesis).split()
    if not ref:
        return None
    return _levenshtein(ref, hyp) / len(ref)


def compute_exact_word_accuracy(reference: str, hypothesis: str) -> Optional[float]:
    """1 - WER — the fraction of reference words reproduced correctly once
    insertions/deletions/substitutions are accounted for (standard WER-derived
    accuracy, not a naive positional match)."""
    wer = compute_wer(reference, hypothesis)
    if wer is None:
        return None
    return max(0.0, 1.0 - wer)


def compute_exact_line_accuracy(reference: str, hypothesis: str) -> Optional[float]:
    """Order-insensitive: the fraction of reference lines (normalized) that
    appear verbatim among the hypothesis's lines. Order-insensitive because
    engines disagree on exact line segmentation for the same dense content —
    this measures whether a line was recovered intact at all, not whether
    line order matched."""
    ref_lines = [_normalize_for_cer(l) for l in reference.split("\n") if l.strip()]
    if not ref_lines:
        return None
    hyp_lines = {_normalize_for_cer(l) for l in hypothesis.split("\n") if l.strip()}
    hits = sum(1 for l in ref_lines if l in hyp_lines)
    return hits / len(ref_lines)


# ---------------------------------------------------------------------------
# Ground truth / engines
# ---------------------------------------------------------------------------

def load_ground_truth(path: Path) -> List[dict]:
    records = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(f"{path.name}:{line_number}: skipping malformed line — {exc}")
    return records


def _run_tesseract(image, dpi: int) -> OCRResult:
    return ocr_image(image, preprocess=True)


def _run_paddleocr(image, dpi: int) -> OCRResult:
    return run_handwriting_ocr(image, "paddleocr")


def _run_trocr(image, dpi: int) -> OCRResult:
    return run_handwriting_ocr(image, "trocr")


ENGINE_RUNNERS: Dict[str, Callable] = {
    "tesseract": _run_tesseract,
    "paddleocr": _run_paddleocr,
    "trocr": _run_trocr,
}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_engine(engine: str, ground_truth: List[dict], dpi: int) -> dict:
    runner = ENGINE_RUNNERS[engine]
    per_page: List[dict] = []

    for record in ground_truth:
        source_path = REPO_ROOT / record["source"]
        reference = record["text"]
        entry = {
            "source": record["source"],
            "page": record["page"],
            "difficulty": record.get("difficulty"),
        }
        if not source_path.exists():
            entry["error"] = f"source file not found: {source_path}"
            per_page.append(entry)
            continue

        start = time.perf_counter()
        try:
            image = render_pdf_page(source_path, record["page"] - 1, dpi=dpi)
            result = runner(image, dpi)
            hypothesis = result.text
            engine_confidence = result.confidence
        except Exception as exc:  # noqa: BLE001 — one bad page/engine failure must not abort the sweep
            entry["error"] = str(exc)
            per_page.append(entry)
            continue
        duration = time.perf_counter() - start

        entry.update(
            {
                "processing_seconds": round(duration, 3),
                "engine_confidence": engine_confidence,
                "hypothesis_chars": len(hypothesis),
                "cer": compute_cer(reference, hypothesis),
                "wer": compute_wer(reference, hypothesis),
                "exact_word_accuracy": compute_exact_word_accuracy(reference, hypothesis),
                "exact_line_accuracy": compute_exact_line_accuracy(reference, hypothesis),
                "empty": len(hypothesis.strip()) == 0,
            }
        )
        per_page.append(entry)

    def _mean(key: str) -> Optional[float]:
        values = [p[key] for p in per_page if key in p and p[key] is not None]
        return round(sum(values) / len(values), 4) if values else None

    evaluated = [p for p in per_page if "error" not in p]
    empty_count = sum(1 for p in evaluated if p["empty"])

    return {
        "engine": engine,
        "pages_total": len(ground_truth),
        "pages_evaluated": len(evaluated),
        "pages_failed": len(ground_truth) - len(evaluated),
        "mean_cer": _mean("cer"),
        "mean_wer": _mean("wer"),
        "mean_exact_word_accuracy": _mean("exact_word_accuracy"),
        "mean_exact_line_accuracy": _mean("exact_line_accuracy"),
        "empty_page_rate": round(empty_count / len(evaluated), 4) if evaluated else None,
        "mean_processing_seconds": _mean("processing_seconds"),
        "pages": per_page,
    }


def print_report(reports: List[dict]) -> None:
    print()
    print("OCR ENGINE EVALUATION")
    print("----------------------")
    header = f"{'engine':<12}{'pages':>7}{'mean CER':>10}{'mean WER':>10}{'word acc':>10}{'line acc':>10}{'empty %':>9}{'sec/page':>10}"
    print(header)
    for r in reports:
        def fmt(v):
            return f"{v:.3f}" if v is not None else "n/a"

        print(
            f"{r['engine']:<12}{r['pages_evaluated']:>7}{fmt(r['mean_cer']):>10}{fmt(r['mean_wer']):>10}"
            f"{fmt(r['mean_exact_word_accuracy']):>10}{fmt(r['mean_exact_line_accuracy']):>10}"
            f"{(fmt(r['empty_page_rate'])):>9}{fmt(r['mean_processing_seconds']):>10}"
        )
        if r["pages_failed"]:
            print(f"  ({r['pages_failed']} page(s) failed to process — see report JSON for errors)")
    print()
    print("Lower is better: mean CER, mean WER, empty %. Higher is better: word acc, line acc.")
    print()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare OCR engines against a ground-truth set (CER/WER).")
    parser.add_argument("--ground-truth", type=Path, default=EVALUATION_DIR / "ocr_ground_truth.jsonl")
    parser.add_argument("--engines", default="tesseract,paddleocr", help="Comma-separated: tesseract,paddleocr,trocr")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--output", type=Path, default=EVALUATION_DIR / "ocr_evaluation_results.json")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    ground_truth = load_ground_truth(args.ground_truth)
    if not ground_truth:
        logger.error(
            f"No ground-truth records found at {args.ground_truth} — nothing to evaluate. "
            "CER/WER cannot be reported without ground truth; see data/evaluation/README.md."
        )
        return 1

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    unknown = [e for e in engines if e not in ENGINE_RUNNERS]
    if unknown:
        logger.error(f"Unknown engine(s): {unknown}. Supported: {sorted(ENGINE_RUNNERS)}")
        return 1

    reports = []
    for engine in engines:
        logger.info(f"Evaluating engine={engine!r} against {len(ground_truth)} ground-truth page(s)...")
        report = evaluate_engine(engine, ground_truth, args.dpi)
        if report["pages_evaluated"] == 0:
            first_error = next((p.get("error") for p in report["pages"] if "error" in p), "unknown error")
            logger.warning(f"Skipping engine={engine!r} — every page failed (e.g. {first_error!r}).")
            continue
        reports.append(report)

    if not reports:
        logger.error("No engine could be evaluated (all unavailable/failed). See warnings above.")
        return 1

    print_report(reports)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
