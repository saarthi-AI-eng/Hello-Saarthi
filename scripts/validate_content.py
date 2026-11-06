"""
Validate canonical ContentRecord JSONL before it is allowed into the
catalog/knowledge-base pipeline. Produces both a machine-readable
(data/catalog/validation_report.json) and human-readable
(data/catalog/validation_report.txt) report.

Usage:
    python -m scripts.validate_content
    python -m scripts.validate_content --input data/cleaned
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from scripts.content_common import CATALOG_DIR, DATA_DIR, get_logger
from scripts.schemas import ContentRecord, ContentType, validate_record

logger = get_logger("validate_content")

NOTE_TYPES = {ContentType.PDF_NOTE, ContentType.HANDWRITTEN_NOTE}
VALID_PROCESSING_STATUSES = {"discovered", "processing", "processed", "failed"}
VALID_QA_STATUSES = {"not_required", "pending", "approved", "rejected"}


def load_records_with_errors(path: Path) -> Tuple[List[ContentRecord], List[str]]:
    records: List[ContentRecord] = []
    errors: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(validate_record(data))
            except Exception as exc:  # noqa: BLE001 — collect every bad record instead of aborting
                errors.append(f"{path.name}:{line_number}: {exc}")
    return records, errors


def validate_videos(records: List[ContentRecord]) -> dict:
    errors: List[str] = []
    by_source: dict = {}
    seen_ids: set = set()
    duplicate_ids = 0
    missing_timestamps = 0
    invalid_ids = set()

    for r in records:
        by_source.setdefault(r.source_id, []).append(r)
        if r.content_id in seen_ids:
            duplicate_ids += 1
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: duplicate content_id")
        seen_ids.add(r.content_id)

        if not r.text.strip():
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: empty text")
        if not r.source:
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: missing source")
        if not r.source_id:
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: missing source_id")
        if r.start_time is None or r.end_time is None:
            missing_timestamps += 1
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: missing start_time/end_time")
        elif r.start_time >= r.end_time:
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: start_time >= end_time")

    for source_id, group in by_source.items():
        prev_start: Optional[float] = None
        for r in group:
            if r.start_time is not None:
                if prev_start is not None and r.start_time < prev_start:
                    invalid_ids.add(r.content_id)
                    errors.append(f"{r.content_id}: timestamps not monotonically ordered within video {source_id}")
                prev_start = r.start_time

    total = len(records)
    invalid = len(invalid_ids)
    return {
        "total": total,
        "valid": total - invalid,
        "invalid": invalid,
        "missing_timestamps": missing_timestamps,
        "duplicate_ids": duplicate_ids,
        "errors": errors,
    }


def validate_notes(records: List[ContentRecord], low_confidence_threshold: float) -> dict:
    errors: List[str] = []
    seen_pages: set = set()
    duplicate_pages = 0
    missing_page_numbers = 0
    low_confidence = 0
    invalid_ids = set()

    for r in records:
        if r.page is None:
            missing_page_numbers += 1
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: missing page number")
        elif r.page < 1:
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: page must be >= 1")

        key = (r.source_id, r.page)
        if key in seen_pages:
            duplicate_pages += 1
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: duplicate page record for source_id={r.source_id} page={r.page}")
        seen_pages.add(key)

        if not r.text.strip():
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: empty text")
        if not r.source:
            invalid_ids.add(r.content_id)
            errors.append(f"{r.content_id}: missing source")

        confidence = r.metadata.get("ocr_confidence")
        if confidence is not None:
            if not (0.0 <= float(confidence) <= 1.0):
                invalid_ids.add(r.content_id)
                errors.append(f"{r.content_id}: ocr_confidence {confidence} out of range [0, 1]")
            elif float(confidence) < low_confidence_threshold:
                low_confidence += 1

    total = len(records)
    invalid = len(invalid_ids)
    return {
        "total": total,
        "valid": total - invalid,
        "invalid": invalid,
        "low_confidence": low_confidence,
        "missing_page_numbers": missing_page_numbers,
        "duplicate_page_records": duplicate_pages,
        "errors": errors,
    }


def build_report(input_dir: Path, low_confidence_threshold: float) -> dict:
    video_records: List[ContentRecord] = []
    note_records: List[ContentRecord] = []
    parse_errors: List[str] = []

    for jsonl_path in sorted(input_dir.rglob("*.jsonl")):
        records, errors = load_records_with_errors(jsonl_path)
        parse_errors.extend(errors)
        for r in records:
            if r.content_type == ContentType.VIDEO_TRANSCRIPT:
                video_records.append(r)
            elif r.content_type in NOTE_TYPES:
                note_records.append(r)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "parse_errors": parse_errors,
        "videos": validate_videos(video_records),
        "notes": validate_notes(note_records, low_confidence_threshold),
    }


def format_text_report(report: dict) -> str:
    v = report["videos"]
    n = report["notes"]
    lines = [
        "VALIDATION REPORT",
        "",
        "Videos",
        "------",
        f"Total: {v['total']}",
        f"Valid: {v['valid']}",
        f"Invalid: {v['invalid']}",
        f"Missing timestamps: {v['missing_timestamps']}",
        f"Duplicate IDs: {v['duplicate_ids']}",
        "",
        "Notes",
        "-----",
        f"Total pages: {n['total']}",
        f"Valid: {n['valid']}",
        f"Invalid: {n['invalid']}",
        f"Low confidence: {n['low_confidence']}",
        f"Missing page numbers: {n['missing_page_numbers']}",
        "",
    ]
    if report["parse_errors"]:
        lines.append(f"Unparseable records: {len(report['parse_errors'])}")
        lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate canonical ContentRecord JSONL.")
    parser.add_argument("--input", type=Path, default=DATA_DIR / "cleaned", help="Directory to scan recursively for .jsonl files.")
    parser.add_argument("--output-dir", type=Path, default=CATALOG_DIR)
    parser.add_argument("--low-confidence-threshold", type=float, default=0.5)
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(args.input, args.low_confidence_threshold)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "validation_report.json"
    txt_path = args.output_dir / "validation_report.txt"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    text_report = format_text_report(report)
    txt_path.write_text(text_report, encoding="utf-8")

    print(text_report)
    logger.info(f"Wrote {json_path} and {txt_path}")

    total_invalid = report["videos"]["invalid"] + report["notes"]["invalid"] + len(report["parse_errors"])
    return 0 if total_invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
