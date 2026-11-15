"""Automated Content Quality Assessment stage (Part 1), run between
ingestion and normalization:

    OCR/transcription -> [this script] -> normalize_content_kb

Reads the same ContentRecord JSONL files scripts.ingest_notes /
scripts.ingest_videos already produce (config.ocr_output_dir /
config.transcripts_dir), scores each record individually (one PDF page or
one transcript segment at a time — never a whole file at once, so a mostly-
good PDF doesn't lose its usable pages over a few bad ones), and writes the
SAME files back in place with an updated qa_status and a new
metadata['qa'] block (score/version/method/checks/issues/timestamp).
Never touches OCR/transcription code or the recognized text itself.

Idempotent: a record already scored under the current qa_version, whose
scoring-relevant content hasn't changed, is left untouched — the model is
never re-loaded or re-run for it (there's no model here, but per Part 1.6,
"identical content with the same qa_version should not require unnecessary
reprocessing"). A record whose qa['method'] doesn't match this module's own
automated methods (i.e. was set by something else, e.g. a future manual
review tool) is left untouched too — "never silently promote pending
content to approved" by overriding someone else's decision.

Usage:
    python -m scripts.run_content_qa
    python -m scripts.run_content_qa --config configs/kb_pipeline.yaml
    python -m scripts.run_content_qa --qa-config configs/content_qa.yaml
    python -m scripts.run_content_qa --force   # re-score every record regardless of qa_version/content_hash
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

from scripts.schemas import ContentRecord, ContentType, QAStatus, read_jsonl, record_to_dict
from src.content_qa.checks import DuplicateTracker, qa_content_hash
from src.content_qa.config import QAConfig, load_qa_config
from src.content_qa.pdf_qa import score_pdf_page
from src.content_qa.video_qa import score_video_segment
from src.knowledge_base.config import KBConfig, load_config

logger = logging.getLogger("run_content_qa")

_AUTOMATED_METHODS = {"pdf_heuristic_v1", "video_heuristic_v1"}


def _is_externally_set(record: ContentRecord) -> bool:
    """True if qa_status/metadata['qa'] was set by something other than
    this module's own automated methods (e.g. a future manual review
    tool). Never touched here, not even with --force — overriding
    someone else's explicit decision is exactly what Part 1.6 forbids
    ("never silently promote pending content to approved")."""
    qa = (record.metadata or {}).get("qa")
    return bool(qa) and qa.get("method") not in _AUTOMATED_METHODS


def _already_current(record: ContentRecord, qa_config: QAConfig) -> bool:
    """True if this record's existing qa metadata was produced by one of
    OUR automated methods, under the current qa_version, from content
    that scores identically to what we'd compute now — i.e. it is safe
    (and correctly described by Part 1.6 as unnecessary) to skip."""
    qa = (record.metadata or {}).get("qa")
    if not qa:
        return False
    if qa.get("method") not in _AUTOMATED_METHODS:
        return False  # not ours (e.g. a future manual review tool) — never touch it
    if qa.get("version") != qa_config.qa_version:
        return False
    metadata = record.metadata or {}
    if record.content_type == ContentType.VIDEO_TRANSCRIPT:
        expected_hash = qa_content_hash(
            record.text or "",
            (
                ("avg_logprob", metadata.get("avg_logprob")),
                ("no_speech_prob", metadata.get("no_speech_prob")),
                ("transcription_provider", metadata.get("transcription_provider")),
            ),
        )
    else:
        expected_hash = qa_content_hash(
            record.text or "",
            (
                ("ocr_confidence", metadata.get("ocr_confidence")),
                ("ocr_engine", metadata.get("ocr_engine")),
                ("page_quality", metadata.get("page_quality")),
            ),
        )
    return qa.get("content_hash") == expected_hash


def score_record(record: ContentRecord, qa_config: QAConfig, dup_tracker: DuplicateTracker):
    if record.content_type == ContentType.VIDEO_TRANSCRIPT:
        return score_video_segment(record, qa_config, dup_tracker)
    return score_pdf_page(record, qa_config, dup_tracker)


def run(
    config: KBConfig,
    qa_config: Optional[QAConfig] = None,
    input_dirs: Optional[List[Path]] = None,
    force: bool = False,
) -> dict:
    qa_config = qa_config or load_qa_config()
    config.ensure_directories()
    config.qa_reports_dir.mkdir(parents=True, exist_ok=True)

    dirs = input_dirs or [config.ocr_output_dir, config.transcripts_dir]
    jsonl_files = []
    for d in dirs:
        if d.exists():
            jsonl_files.extend(sorted(d.glob("*.jsonl")))

    counts = {"approved": 0, "pending": 0, "rejected": 0}
    skipped_unchanged = 0
    records_scored = 0
    report_rows: List[dict] = []
    dup_tracker = DuplicateTracker()

    for path in tqdm(jsonl_files, desc="Automated QA", unit="file"):
        records = list(read_jsonl(path, skip_invalid=False))
        changed = False
        for i, record in enumerate(records):
            if _is_externally_set(record):
                counts[record.qa_status.value] = counts.get(record.qa_status.value, 0) + 1
            elif not force and _already_current(record, qa_config):
                skipped_unchanged += 1
                counts[record.qa_status.value] = counts.get(record.qa_status.value, 0) + 1
            else:
                result = score_record(record, qa_config, dup_tracker)
                record.qa_status = QAStatus(result.status)
                record.metadata = dict(record.metadata or {})
                record.metadata["qa"] = result.to_metadata()
                records[i] = record
                changed = True
                records_scored += 1
                counts[result.status] = counts.get(result.status, 0) + 1

            # Every record gets a report row, whether freshly scored or
            # already-current — the report must reflect the FULL current
            # QA state after this run, not just what changed in it (a bare
            # idempotent rerun would otherwise overwrite 'latest' with an
            # empty report).
            qa_meta = (record.metadata or {}).get("qa") or {}
            report_rows.append({
                "source_file": path.name,
                "content_id": record.content_id,
                "page": record.page,
                "start_time": record.start_time,
                "end_time": record.end_time,
                "status": record.qa_status.value,
                "score": qa_meta.get("score"),
                **{f"check_{k}": v for k, v in (qa_meta.get("checks") or {}).items()},
                "issues": ";".join(qa_meta.get("issues") or []),
                "engine_or_model": (record.metadata or {}).get("ocr_engine") or (record.metadata or {}).get("transcription_provider"),
                "qa_version": qa_meta.get("version"),
            })

        if changed:
            with open(path, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record_to_dict(record), ensure_ascii=False) + "\n")

    _write_reports(config, report_rows)
    summary = {
        "files": len(jsonl_files),
        "records_scored": records_scored,
        "records_skipped_unchanged": skipped_unchanged,
        "counts": counts,
        "qa_version": qa_config.qa_version,
    }
    logger.info(f"QA complete: {summary}")
    return summary


def _write_reports(config: KBConfig, rows: List[dict]) -> None:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = config.qa_reports_dir / f"qa_report_{ts}.jsonl"
    csv_path = config.qa_reports_dir / f"qa_report_{ts}.csv"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (config.qa_reports_dir / "latest_qa_report.jsonl").write_text(
        jsonl_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    fieldnames = sorted({k for row in rows for k in row}) if rows else [
        "source_file", "content_id", "page", "start_time", "end_time", "status", "score", "issues", "engine_or_model", "qa_version",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automated Content QA for OCR/transcript output.")
    parser.add_argument("--config", type=Path, default=None, help="KB pipeline config (for data_root/ocr/transcripts dirs).")
    parser.add_argument("--qa-config", type=Path, default=None, help="configs/content_qa.yaml override.")
    parser.add_argument("--input", type=Path, action="append", default=None, help="Override input directory (repeatable).")
    parser.add_argument("--force", action="store_true", help="Re-score every record regardless of qa_version/content_hash.")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    qa_config = load_qa_config(args.qa_config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(config, qa_config, input_dirs=args.input, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
