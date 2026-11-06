"""
Build the unified FAISS knowledge base from QA-approved canonical content.

Pipeline: approved ContentRecords -> semantic/content-aware chunking ->
metadata attachment -> embedding -> FAISS -> knowledge_base/unified/vector_store/

Consumes ONLY canonical cleaned JSONL (scripts/schemas.ContentRecord) — never
touches OCR/transcription internals directly, so those can change without
this script changing.

QA gate (Phase 8): by default only records with processing_status=="processed"
AND qa_status in {"approved","not_required"} are indexed. Pass --allow-pending
to also include qa_status=="pending" for demo/development — this prints a
prominent warning and must never be the default in production use.

This is additive to the existing per-agent FAISS convention in
src/tools/kb_ops.py (knowledge_base/<agent>/vector_store) — it does not
replace it. src/tools/kb_ops.py optionally reads this unified index instead,
gated behind the SAARTHI_USE_UNIFIED_KB environment variable, with the
legacy per-agent indexes kept as a fallback.

Usage:
    python -m scripts.build_knowledge_base
    python -m scripts.build_knowledge_base --allow-pending
    python -m scripts.build_knowledge_base --embedding-model text-embedding-3-small
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from scripts.content_common import DATA_DIR, UNIFIED_KB_DIR, get_logger, log_operation
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, read_jsonl

logger = get_logger("build_knowledge_base")

DEFAULT_EMBEDDING_MODEL = os.environ.get("SAARTHI_KB_EMBEDDING_MODEL", "text-embedding-3-large")
MAX_CHUNK_CHARS = 1200
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

DEFAULT_ALLOWED_QA = {QAStatus.APPROVED, QAStatus.NOT_REQUIRED}
PENDING_ALLOWED_QA = DEFAULT_ALLOWED_QA | {QAStatus.PENDING}


def load_cleaned_records(input_dir: Path) -> List[ContentRecord]:
    records: List[ContentRecord] = []
    for jsonl_path in sorted(input_dir.rglob("*.jsonl")):
        records.extend(read_jsonl(jsonl_path, skip_invalid=True))
    return records


def qa_gate(records: List[ContentRecord], allow_pending: bool) -> List[ContentRecord]:
    allowed_qa = PENDING_ALLOWED_QA if allow_pending else DEFAULT_ALLOWED_QA
    return [r for r in records if r.processing_status == ProcessingStatus.PROCESSED and r.qa_status in allowed_qa]


def build_chunk_metadata(record: ContentRecord) -> dict:
    """Every field an agent/citation layer might need to survive retrieval — see docs/content-management.md."""
    return {
        "content_id": record.content_id,
        "content_type": record.content_type.value,
        "source_id": record.source_id,
        "source": record.source,
        "course": record.course,
        "topic": record.topic,
        "lecture": record.lecture,
        "page": record.page,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "processing_status": record.processing_status.value,
        "qa_status": record.qa_status.value,
    }


def _get_fallback_splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)


def chunk_video_record(record: ContentRecord) -> list:
    """video -> timestamp segment (already the record) -> semantic chunk.

    A transcript segment is already a natural, timestamp-bounded chunk, so it
    is used as-is; only an unusually long segment falls back to a bounded
    splitter (all resulting sub-chunks keep the segment's original
    start_time/end_time rather than inventing sub-segment timestamps).
    """
    from langchain_core.documents import Document

    metadata = build_chunk_metadata(record)
    if len(record.text) <= MAX_CHUNK_CHARS:
        return [Document(page_content=record.text, metadata={**metadata, "chunk_id": record.content_id})]

    splitter = _get_fallback_splitter()
    pieces = splitter.split_text(record.text)
    return [
        Document(page_content=piece, metadata={**metadata, "chunk_id": f"{record.content_id}_C{i + 1}"})
        for i, piece in enumerate(pieces)
    ]


def chunk_note_record(record: ContentRecord) -> list:
    """document -> page (already the record) -> logical section (blank-line paragraph) -> semantic chunk.

    Splits on the blank-line section boundaries scripts/clean_content.py
    preserves, so an equation block sitting inside one paragraph is not
    split mid-formula unless that single section is itself still too large.
    """
    from langchain_core.documents import Document

    metadata = build_chunk_metadata(record)
    sections = [s.strip() for s in record.text.split("\n\n") if s.strip()]
    if not sections:
        sections = [record.text]

    documents = []
    for section_index, section in enumerate(sections, start=1):
        if len(section) <= MAX_CHUNK_CHARS:
            documents.append(
                Document(page_content=section, metadata={**metadata, "chunk_id": f"{record.content_id}_S{section_index}"})
            )
        else:
            splitter = _get_fallback_splitter()
            for piece_index, piece in enumerate(splitter.split_text(section), start=1):
                documents.append(
                    Document(
                        page_content=piece,
                        metadata={**metadata, "chunk_id": f"{record.content_id}_S{section_index}_C{piece_index}"},
                    )
                )
    return documents


def chunk_record(record: ContentRecord) -> list:
    if record.content_type == ContentType.VIDEO_TRANSCRIPT:
        return chunk_video_record(record)
    return chunk_note_record(record)


def build_knowledge_base(
    input_dir: Path,
    output_dir: Path,
    embedding_model: str,
    allow_pending: bool,
) -> dict:
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    all_records = load_cleaned_records(input_dir)
    eligible = qa_gate(all_records, allow_pending)
    skipped = len(all_records) - len(eligible)

    if allow_pending:
        print("DEMO MODE: indexing QA-pending content.")
        logger.warning("DEMO MODE: indexing QA-pending content.")

    documents = []
    for record in eligible:
        documents.extend(chunk_record(record))

    if not documents:
        logger.warning("No eligible content to index (QA gate excluded everything, or no cleaned records found).")
        log_operation(
            file=str(input_dir),
            type_="knowledge_base",
            operation="build",
            status="failed",
            error="No eligible content passed the QA gate",
            records_seen=len(all_records),
        )
        return {"indexed_records": 0, "skipped_records": skipped, "chunks": 0}

    embeddings = OpenAIEmbeddings(model=embedding_model)
    vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)

    output_dir.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(output_dir))

    manifest = {
        "embedding_model": embedding_model,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "num_source_records": len(eligible),
        "num_chunks": len(documents),
        "allow_pending": allow_pending,
    }
    (output_dir.parent / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    log_operation(
        file=str(input_dir),
        type_="knowledge_base",
        operation="build",
        status="success",
        output=str(output_dir),
        records=len(eligible),
        chunks=len(documents),
    )
    logger.info(f"Indexed {len(eligible)} records ({len(documents)} chunks, {skipped} skipped by QA gate) -> {output_dir}")
    return {"indexed_records": len(eligible), "skipped_records": skipped, "chunks": len(documents)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the unified FAISS knowledge base from QA-approved content.")
    parser.add_argument("--input", type=Path, default=DATA_DIR / "cleaned", help="Root of cleaned ContentRecord JSONL.")
    parser.add_argument("--output", type=Path, default=UNIFIED_KB_DIR / "vector_store")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Also settable via SAARTHI_KB_EMBEDDING_MODEL.")
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="DEMO MODE: also index qa_status=pending content (never use in production).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}. Run scripts.clean_content first.")
        return 1
    result = build_knowledge_base(args.input, args.output, args.embedding_model, args.allow_pending)
    return 0 if result["chunks"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
