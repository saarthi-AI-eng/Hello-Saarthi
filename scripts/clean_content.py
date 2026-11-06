"""
Clean canonical ContentRecord JSONL: remove extraction artifacts only.
Deterministic, conservative — "clean only what is clearly an extraction
artifact", never "rewrite the text to sound better". Preserves timestamps,
page numbers, segment/page boundaries, and mathematical/technical notation
(e.g. x[n], x(t), X(jω), δ(t), H(z)) untouched.

Usage:
    python -m scripts.clean_content --input data/processed --output data/cleaned
    python -m scripts.clean_content --input data/processed --output data/cleaned --dry-run
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional

from scripts.content_common import DATA_DIR, get_logger
from scripts.schemas import ContentRecord, read_jsonl, write_jsonl

logger = get_logger("clean_content")

_NON_SPEECH_TAG_RE = re.compile(r"\[(music|applause|inaudible|laughter|silence|noise)\]", re.IGNORECASE)
_REPEATED_WORD_RE = re.compile(r"\b(\w+)( \1\b){1,}", re.IGNORECASE)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")


# ---------------------------------------------------------------------------
# Transcript cleaning
# ---------------------------------------------------------------------------

def clean_transcript_text(text: str) -> str:
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _NON_SPEECH_TAG_RE.sub("", text)
    text = _REPEATED_WORD_RE.sub(r"\1", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# OCR cleaning
# ---------------------------------------------------------------------------

def _dedupe_consecutive_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        if out and out[-1].strip() != "" and out[-1].strip() == line.strip():
            continue
        out.append(line)
    return out


def detect_repeated_header_footer_lines(page_texts: List[str], min_page_count: int = 3, threshold: float = 0.6) -> set:
    """Lines that recur across most pages of the same document — likely headers/footers, not content."""
    if len(page_texts) < min_page_count:
        return set()
    from collections import Counter

    counts: Counter = Counter()
    for text in page_texts:
        seen_this_page = set()
        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if line and len(line) <= 80:
                seen_this_page.add(line)
        counts.update(seen_this_page)

    min_occurrences = max(min_page_count, int(len(page_texts) * threshold))
    return {line for line, count in counts.items() if count >= min_occurrences}


def clean_ocr_text(text: str, header_footer_lines: Optional[set] = None) -> str:
    """Cleans OCR text while preserving blank-line paragraph/section boundaries
    (collapsed to a single blank line each) — build_knowledge_base.py uses those
    boundaries for logical-section chunking.
    """
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)  # repair a word broken across a line by a hyphen
    lines = text.split("\n")
    if header_footer_lines:
        lines = [l for l in lines if l.strip() not in header_footer_lines]
    lines = _dedupe_consecutive_lines(lines)
    cleaned_lines = [_MULTI_SPACE_RE.sub(" ", l).strip() for l in lines]

    collapsed: List[str] = []
    for line in cleaned_lines:
        if line == "" and collapsed and collapsed[-1] == "":
            continue  # collapse runs of blank lines to a single paragraph break
        collapsed.append(line)
    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return "\n".join(collapsed).strip()


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def clean_transcript_records(records: List[ContentRecord]) -> List[ContentRecord]:
    cleaned = []
    for record in records:
        new_text = clean_transcript_text(record.text)
        cleaned.append(record.model_copy(update={"text": new_text}))
    return cleaned


def clean_ocr_records(records: List[ContentRecord]) -> List[ContentRecord]:
    by_source: dict[str, List[ContentRecord]] = {}
    for record in records:
        by_source.setdefault(record.source_id or record.source, []).append(record)

    cleaned: List[ContentRecord] = []
    for _source_id, group in by_source.items():
        header_footer = detect_repeated_header_footer_lines([r.text for r in group])
        for record in group:
            new_text = clean_ocr_text(record.text, header_footer)
            cleaned.append(record.model_copy(update={"text": new_text}))
    return cleaned


def clean_file(input_path: Path, output_path: Path, kind: str, dry_run: bool) -> dict:
    records = list(read_jsonl(input_path))
    if kind == "transcript":
        cleaned = clean_transcript_records(records)
    else:
        cleaned = clean_ocr_records(records)

    changed = sum(1 for before, after in zip(records, cleaned) if before.text != after.text)
    if not dry_run:
        write_jsonl(cleaned, output_path)
    return {"total": len(records), "changed": changed, "output": str(output_path)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean canonical ContentRecord JSONL (artifact removal only).")
    parser.add_argument("--input", type=Path, default=DATA_DIR / "processed", help="Root containing transcripts/ and ocr/ subdirs.")
    parser.add_argument("--output", type=Path, default=DATA_DIR / "cleaned", help="Root to write cleaned transcripts/ and ocr/ subdirs.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing output.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    transcripts_in = args.input / "transcripts"
    ocr_in = args.input / "ocr"
    transcripts_out = args.output / "transcripts"
    ocr_out = args.output / "ocr"

    total_files = 0
    total_changed = 0

    for jsonl_path in sorted(transcripts_in.glob("*.jsonl")) if transcripts_in.exists() else []:
        result = clean_file(jsonl_path, transcripts_out / jsonl_path.name, "transcript", args.dry_run)
        logger.info(f"[transcript] {jsonl_path.name}: {result['changed']}/{result['total']} records changed"
                    + ("" if args.dry_run else f" -> {result['output']}"))
        total_files += 1
        total_changed += result["changed"]

    for jsonl_path in sorted(ocr_in.glob("*.jsonl")) if ocr_in.exists() else []:
        result = clean_file(jsonl_path, ocr_out / jsonl_path.name, "ocr", args.dry_run)
        logger.info(f"[ocr] {jsonl_path.name}: {result['changed']}/{result['total']} records changed"
                    + ("" if args.dry_run else f" -> {result['output']}"))
        total_files += 1
        total_changed += result["changed"]

    if total_files == 0:
        logger.warning(f"No JSONL files found under {args.input}")
    else:
        mode = "DRY RUN — " if args.dry_run else ""
        logger.info(f"{mode}Done. {total_files} files processed, {total_changed} records had text changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
