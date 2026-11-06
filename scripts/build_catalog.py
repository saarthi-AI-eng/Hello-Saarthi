"""
Scan data/raw, data/processed, and data/cleaned and produce a single
master content catalog (CSV) plus a console summary.

Usage:
    python -m scripts.build_catalog
    python -m scripts.build_catalog --output data/catalog/content_catalog.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional

from scripts.content_common import (
    CATALOG_DIR,
    CLEANED_OCR_DIR,
    CLEANED_TRANSCRIPTS_DIR,
    PROCESSED_OCR_DIR,
    PROCESSED_TRANSCRIPTS_DIR,
    RAW_NOTES_DIR,
    RAW_VIDEOS_DIR,
    UNIFIED_KB_DIR,
    get_logger,
    latest_log_status,
)
from scripts.ingest_notes import SUPPORTED_EXTENSIONS as NOTE_EXTENSIONS
from scripts.ingest_videos import VIDEO_EXTENSIONS
from scripts.schemas import ContentRecord, read_jsonl

logger = get_logger("build_catalog")

CSV_COLUMNS = [
    "content_id",
    "content_type",
    "source",
    "source_id",
    "course",
    "topic",
    "lecture",
    "page",
    "start_time",
    "end_time",
    "processing_status",
    "qa_status",
    "indexed",
    "file_path",
    "text_length",
    "metadata_summary",
]


def load_indexed_content_ids(index_dir: Path = UNIFIED_KB_DIR / "vector_store") -> set:
    """Content ids present in the unified knowledge base, read without any embedding API call."""
    if not (index_dir / "index.faiss").exists():
        return set()
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_core.embeddings import Embeddings

        class _NullEmbeddings(Embeddings):
            """No-op Embeddings: we only read vs.docstore._dict directly below, never
            similarity_search, so these zero vectors are never used for a real
            comparison — this just lets FAISS.load_local run without
            OPENAI_API_KEY/network for a read-only "which content_ids are indexed" check."""

            def embed_documents(self, texts: list) -> list:
                return [[0.0] for _ in texts]

            def embed_query(self, text: str) -> list:
                return [0.0]

        vs = FAISS.load_local(str(index_dir), _NullEmbeddings(), allow_dangerous_deserialization=True)
        return {
            doc.metadata["content_id"]
            for doc in vs.docstore._dict.values()
            if doc.metadata.get("content_id")
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not read unified KB index for indexed-status check: {exc}")
        return set()


def _collect_records(directory: Path, file_path_by_id: Dict[str, str]) -> Dict[str, ContentRecord]:
    records: Dict[str, ContentRecord] = {}
    if not directory.exists():
        return records
    for jsonl_path in sorted(directory.glob("*.jsonl")):
        for record in read_jsonl(jsonl_path, skip_invalid=True):
            records[record.content_id] = record
            file_path_by_id[record.content_id] = str(jsonl_path)
    return records


def _discovered_rows_for_raw_files(raw_dir: Path, extensions: set, existing_source_files: set) -> List[dict]:
    """Placeholder catalog rows for raw files that have not produced any processed/cleaned record yet."""
    rows: List[dict] = []
    if not raw_dir.exists():
        return rows
    for path in sorted(raw_dir.iterdir()):
        if path.suffix.lower() not in extensions:
            continue
        if path.name in existing_source_files:
            continue
        status = latest_log_status(path.name) or "discovered"
        processing_status = "failed" if status == "failed" else "discovered"
        rows.append(
            {
                "content_id": f"RAW_{path.stem.upper()}",
                "content_type": "unknown",
                "source": path.name,
                "source_id": None,
                "course": None,
                "topic": None,
                "lecture": None,
                "page": None,
                "start_time": None,
                "end_time": None,
                "processing_status": processing_status,
                "qa_status": "not_required",
                "indexed": "no",
                "file_path": str(path),
                "text_length": 0,
                "metadata_summary": "",
            }
        )
    return rows


def build_catalog(output_path: Path) -> List[dict]:
    file_path_by_id: Dict[str, str] = {}

    # Cleaned records win over processed (they're the more authoritative/newer stage).
    processed = {}
    processed.update(_collect_records(PROCESSED_TRANSCRIPTS_DIR, file_path_by_id))
    processed.update(_collect_records(PROCESSED_OCR_DIR, file_path_by_id))
    cleaned = {}
    cleaned.update(_collect_records(CLEANED_TRANSCRIPTS_DIR, file_path_by_id))
    cleaned.update(_collect_records(CLEANED_OCR_DIR, file_path_by_id))

    merged: Dict[str, ContentRecord] = {**processed, **cleaned}

    indexed_ids = load_indexed_content_ids()
    existing_source_files = {r.source for r in merged.values()}

    rows: List[dict] = []
    for content_id, record in sorted(merged.items()):
        rows.append(
            {
                "content_id": record.content_id,
                "content_type": record.content_type.value if hasattr(record.content_type, "value") else record.content_type,
                "source": record.source,
                "source_id": record.source_id,
                "course": record.course,
                "topic": record.topic,
                "lecture": record.lecture,
                "page": record.page,
                "start_time": record.start_time,
                "end_time": record.end_time,
                "processing_status": record.processing_status.value if hasattr(record.processing_status, "value") else record.processing_status,
                "qa_status": record.qa_status.value if hasattr(record.qa_status, "value") else record.qa_status,
                "indexed": "yes" if content_id in indexed_ids else "no",
                "file_path": file_path_by_id.get(content_id, ""),
                "text_length": len(record.text),
                # Scalars only — a structured field like metadata["ocr_lines"]
                # (per-line boxes/confidences, dozens of entries on a dense
                # page) would otherwise blow up this single CSV cell.
                "metadata_summary": "; ".join(
                    f"{k}={v}" for k, v in record.metadata.items() if v is not None and not isinstance(v, (list, dict))
                ),
            }
        )

    rows.extend(_discovered_rows_for_raw_files(RAW_VIDEOS_DIR, VIDEO_EXTENSIONS, existing_source_files))
    rows.extend(_discovered_rows_for_raw_files(RAW_NOTES_DIR, NOTE_EXTENSIONS, existing_source_files))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def print_summary(rows: List[dict]) -> None:
    videos = [r for r in rows if r["content_type"] == "video_transcript" or (r["content_type"] == "unknown" and r["source"].lower().endswith(tuple(VIDEO_EXTENSIONS)))]
    notes = [r for r in rows if r["content_type"] in ("pdf_note", "handwritten_note") or (r["content_type"] == "unknown" and r["source"].lower().endswith(tuple(NOTE_EXTENSIONS)))]

    def by_video(records: List[dict]) -> Dict[Optional[str], List[dict]]:
        grouped: Dict[Optional[str], List[dict]] = {}
        for r in records:
            key = r["source_id"] or r["source"]
            grouped.setdefault(key, []).append(r)
        return grouped

    video_groups = by_video(videos)
    total_videos = len(video_groups)
    processed_videos = sum(1 for g in video_groups.values() if all(r["processing_status"] == "processed" for r in g))
    failed_videos = sum(1 for g in video_groups.values() if any(r["processing_status"] == "failed" for r in g))
    pending_qa_videos = sum(1 for g in video_groups.values() if any(r["qa_status"] == "pending" for r in g))

    total_pages = len(notes)
    processed_pages = sum(1 for r in notes if r["processing_status"] == "processed")
    failed_pages = sum(1 for r in notes if r["processing_status"] == "failed")
    qa_approved_pages = sum(1 for r in notes if r["qa_status"] == "approved")
    qa_pending_pages = sum(1 for r in notes if r["qa_status"] == "pending")

    indexed = sum(1 for r in rows if r["indexed"] == "yes")
    not_indexed = len(rows) - indexed

    print()
    print("VIDEOS")
    print("------")
    print(f"Total videos: {total_videos}")
    print(f"Processed: {processed_videos}")
    print(f"Failed: {failed_videos}")
    print(f"Pending QA: {pending_qa_videos}")
    print()
    print("NOTES")
    print("-----")
    print(f"Total pages: {total_pages}")
    print(f"Processed: {processed_pages}")
    print(f"Failed: {failed_pages}")
    print(f"QA approved: {qa_approved_pages}")
    print(f"QA pending: {qa_pending_pages}")
    print()
    print("INDEX")
    print("-----")
    print(f"Indexed: {indexed}")
    print(f"Not indexed: {not_indexed}")
    print()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the master content catalog.")
    parser.add_argument("--output", type=Path, default=CATALOG_DIR / "content_catalog.csv")
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = build_catalog(args.output)
    logger.info(f"Wrote {len(rows)} rows to {args.output}")
    print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
