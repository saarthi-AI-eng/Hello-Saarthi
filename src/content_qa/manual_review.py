"""Manual QA review — applies a human reviewer's accept/reject/reprocess
decision directly to the SAME ContentRecord JSONL files
scripts/run_content_qa.py and scripts/normalize_content_kb.py already
read and write. This is deliberately the smallest integration: no second
source of truth for qa_status, no new database required for the pipeline
itself to keep working — the normalizer already reads qa_status straight
from these files, so a manual decision written here is picked up by the
very next normalize_content_kb run with zero extra plumbing.

Concurrency: an OS-level advisory lock (portalocker) on a sibling
`<file>.lock` file is held for the full read-modify-write, so two
reviewers (or a reviewer and a concurrent Auto-QA rerun) touching the
same source file never race. The actual update is conditional — it only
succeeds if the record's qa_status is still "pending" at the moment of
the locked read — so a stale decision (someone else already reviewed it,
or Auto-QA re-ran) is rejected with a clear error instead of silently
overwriting a newer status (Phase 4's "a reviewer must not overwrite a
newer decision"). The file write itself is atomic at the filesystem
level (write to a temp file, then os.replace() onto the original), so a
crash mid-write never leaves a truncated/corrupted JSONL file.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from scripts.schemas import ContentRecord, ContentType, QAStatus, read_jsonl, record_to_dict
from src.knowledge_base.config import KBConfig

_DECISION_TO_STATUS = {
    "accept": "approved",
    "reject": "rejected",
    "reprocess": "reprocess_requested",
}


class ManualReviewError(Exception):
    pass


class ManualReviewNotFound(ManualReviewError):
    pass


class ManualReviewConflict(ManualReviewError):
    """Raised when the record is no longer pending — never silently overwritten."""


def render_source_page_image(record: ContentRecord) -> bytes:
    """Renders the ONE PDF page this record came from, as PNG bytes — the
    same renderer OCR itself used (scripts.ingest_notes.render_pdf_page),
    so what the reviewer sees is exactly what was OCR'd, not a
    re-derivation. Raises ManualReviewError for non-PDF content or a
    missing source file — never silently returns a blank/wrong image."""
    if record.content_type != ContentType.PDF_NOTE or record.page is None:
        raise ManualReviewError("Source page preview is only available for PDF note pages.")

    from scripts.content_common import RAW_NOTES_DIR
    from scripts.ingest_notes import render_pdf_page

    pdf_path = RAW_NOTES_DIR / record.source
    if not pdf_path.exists():
        raise ManualReviewNotFound(f"Original source file not found: {pdf_path}")

    import io

    image = render_pdf_page(pdf_path, record.page - 1, dpi=150)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def resolve_source_jsonl_path(config: KBConfig, content_type: str, source_file: str) -> Path:
    """The JSONL file a given ContentRecord actually lives in — same
    stem as the original PDF/video, same directory
    scripts.ingest_notes/ingest_videos already write to."""
    stem = Path(source_file).stem
    base_dir = config.transcripts_dir if content_type == ContentType.VIDEO_TRANSCRIPT.value else config.ocr_output_dir
    return base_dir / f"{stem}.jsonl"


def list_pending_items(config: KBConfig) -> List[dict]:
    """One lightweight dict per qa_status=='pending' record across every
    OCR/transcript JSONL file — never loads full file contents into the
    caller beyond what's needed for a queue row (no OCR/transcript text
    truncation decision is made here; the API layer decides what to
    expose in a list vs a detail view)."""
    items: List[dict] = []
    for base_dir in (config.ocr_output_dir, config.transcripts_dir):
        if not base_dir.exists():
            continue
        for path in sorted(base_dir.glob("*.jsonl")):
            for record in read_jsonl(path, skip_invalid=True):
                if record.qa_status != QAStatus.PENDING:
                    continue
                qa_meta = (record.metadata or {}).get("qa") or {}
                items.append({
                    "content_id": record.content_id,
                    "source_file": record.source,
                    "source_jsonl_path": str(path),
                    "content_type": record.content_type.value,
                    "course": record.course,
                    "page": record.page,
                    "start_time": record.start_time,
                    "end_time": record.end_time,
                    "qa_score": qa_meta.get("score"),
                    "qa_issues": qa_meta.get("issues") or [],
                    "qa_timestamp": qa_meta.get("timestamp"),
                })
    return items


def build_review_hints(record: ContentRecord) -> dict:
    """Best-effort reviewer hints from data Auto-QA already computed —
    never a new OCR/analysis pass, never invented.

    line_confidences: per-line {text, confidence}, only present for
    PaddleOCR pages (metadata.ocr_lines) — Tesseract pages have just one
    page-level confidence number today, a real, documented limitation,
    not papered over here.

    equation_suggestions: for any math_equation_block Auto-QA already
    flagged uncertain (review_required, or quality != GOOD), the second-
    opinion re-OCR text, when it actually differs from what's already in
    the page — nothing invented, just surfacing an existing second
    reading the pipeline already computed."""
    metadata = record.metadata or {}
    line_confidences = [
        {"text": line["text"], "confidence": line.get("confidence")}
        for line in (metadata.get("ocr_lines") or [])
        if line.get("text")
    ]

    equation_suggestions = []
    for block in metadata.get("math_equation_blocks") or []:
        if not (block.get("review_required") or block.get("math_quality") != "GOOD"):
            continue
        suggestion = (block.get("second_opinion_text") or "").strip()
        original = (block.get("normalized_text") or block.get("ocr_text_raw") or "").strip()
        if suggestion and suggestion != original:
            equation_suggestions.append({"original": original, "suggestion": suggestion, "quality": block.get("math_quality")})

    return {"line_confidences": line_confidences, "equation_suggestions": equation_suggestions}


def get_record_detail(file_path: Path, content_id: str) -> ContentRecord:
    for record in read_jsonl(Path(file_path), skip_invalid=True):
        if record.content_id == content_id:
            return record
    raise ManualReviewNotFound(f"{content_id!r} not found in {file_path}")


def apply_manual_review(
    file_path: Path,
    content_id: str,
    decision: str,
    reviewer_id: str,
    reason: Optional[str] = None,
    edited_text: Optional[str] = None,
) -> dict:
    """Returns {"content_id", "previous_status", "new_status", "decision",
    "timestamp", "edited"}. Raises ManualReviewNotFound if content_id
    isn't in file_path, ManualReviewConflict if it's no longer pending,
    ValueError for an unknown decision string.

    edited_text, if given and different from the record's current text,
    becomes the record's new text regardless of decision (an edit made
    before rejecting/reprocessing is still worth keeping for history/the
    next pass) — the ORIGINAL text is preserved under
    metadata.manual_review.original_text, never discarded."""
    if decision not in _DECISION_TO_STATUS:
        raise ValueError(f"Unknown decision {decision!r} — must be one of {sorted(_DECISION_TO_STATUS)}.")
    new_status = _DECISION_TO_STATUS[decision]
    file_path = Path(file_path)

    import portalocker

    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    with portalocker.Lock(str(lock_path), timeout=10):
        records = list(read_jsonl(file_path, skip_invalid=False))
        target_idx = next((i for i, r in enumerate(records) if r.content_id == content_id), None)
        if target_idx is None:
            raise ManualReviewNotFound(f"{content_id!r} not found in {file_path}")

        record = records[target_idx]
        if record.qa_status != QAStatus.PENDING:
            raise ManualReviewConflict(
                f"{content_id!r} is no longer pending (current status: {record.qa_status.value!r}) — "
                "someone else may have already reviewed it, or Auto-QA re-ran. Refresh the queue."
            )

        previous_status = record.qa_status.value
        timestamp = datetime.now(timezone.utc).isoformat()
        original_text = record.text
        edited = edited_text is not None and edited_text != original_text
        record.qa_status = QAStatus(new_status)
        if edited:
            record.text = edited_text
        record.metadata = dict(record.metadata or {})
        record.metadata["manual_review"] = {
            "decision": decision,
            "reviewer_id": reviewer_id,
            "reason": reason,
            "previous_status": previous_status,
            "new_status": new_status,
            "timestamp": timestamp,
            "edited": edited,
            "original_text": original_text if edited else None,
        }
        records[target_idx] = record

        tmp_path = file_path.with_suffix(file_path.suffix + f".tmp-{os.getpid()}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(record_to_dict(r), ensure_ascii=False) + "\n")
        os.replace(tmp_path, file_path)  # atomic on both Windows and POSIX — never a partially-written file

    return {
        "content_id": content_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "decision": decision,
        "timestamp": timestamp,
        "edited": edited,
    }
