"""Stage 1 of the BGE-M3 + Qdrant KB pipeline: normalize existing OCR/
transcript ContentRecord JSONL into the documented NormalizedDoc shape
(src.knowledge_base.schema.NormalizedDoc).

Never re-implements OCR or transcription — reads only the JSONL files
scripts.ingest_notes / scripts.ingest_videos already produce (see
scripts.schemas.ContentRecord). Rejects malformed input with a clear
error naming the file and line; never silently drops a record.

Usage:
    python -m scripts.normalize_content_kb
    python -m scripts.normalize_content_kb --config configs/kb_pipeline.yaml
    python -m scripts.normalize_content_kb --input "E:\\SaarthiData\\source_content\\ocr" --sample 3
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

from scripts.schemas import ContentRecord, read_jsonl
from src.knowledge_base.config import KBConfig, load_config
from src.knowledge_base.schema import NormalizedDoc

logger = logging.getLogger("normalize_content_kb")


def normalize_record(record: ContentRecord) -> NormalizedDoc:
    metadata = record.metadata or {}
    return NormalizedDoc(
        doc_id=record.content_id,
        source_id=record.source_id,
        source_type=record.content_type.value,
        source_file=record.source,
        course=record.course,
        topic=record.topic,
        lecture=record.lecture,
        page=record.page,
        start_time=record.start_time,
        end_time=record.end_time,
        text=record.text,
        qa_status=record.qa_status.value,
        qa_score=(metadata.get("qa") or {}).get("score"),
        ocr_quality=metadata.get("page_quality"),
        ocr_confidence=metadata.get("ocr_confidence"),
        review_reasons=list(metadata.get("review_reasons") or []),
        math_equation_blocks=list(metadata.get("math_equation_blocks") or []),
        raw_metadata=dict(metadata),
    )


def normalize_file(input_path: Path, allow_pending: bool) -> List[NormalizedDoc]:
    """Reads one ContentRecord JSONL file. Raises a clear error (file +
    line) on a malformed line rather than silently skipping it —
    skip_invalid=False, the opposite default of the checkpoint-resume
    use case elsewhere in this project."""
    docs = []
    for i, record in enumerate(read_jsonl(input_path, skip_invalid=False), start=1):
        if record.qa_status.value == "rejected":
            continue  # never index explicitly rejected content
        if record.qa_status.value == "reprocess_requested":
            continue  # manual QA sent this back for reprocessing — never KB-eligible, regardless of --allow-pending
        if record.qa_status.value == "pending" and not allow_pending:
            continue
        if not record.text or not record.text.strip():
            logger.warning(f"{input_path.name}:{i} ({record.content_id}) has empty text — kept as a 0-length NormalizedDoc, not dropped, for traceability")
        docs.append(normalize_record(record))
    return docs


def run(config: KBConfig, input_dirs: Optional[List[Path]] = None, sample: Optional[int] = None, allow_pending: bool = False) -> dict:
    config.ensure_directories()
    dirs = input_dirs or [config.ocr_output_dir, config.transcripts_dir]
    jsonl_files = []
    for d in dirs:
        if d.exists():
            jsonl_files.extend(sorted(d.glob("*.jsonl")))
    if sample:
        jsonl_files = jsonl_files[:sample]

    if not jsonl_files:
        logger.warning(f"No input JSONL found under {dirs} — nothing to normalize.")
        return {"files": 0, "docs": 0, "output": None}

    all_docs: List[NormalizedDoc] = []
    failed_files = []
    for path in tqdm(jsonl_files, desc="Normalizing source files", unit="file"):
        try:
            all_docs.extend(normalize_file(path, allow_pending))
        except Exception as exc:  # noqa: BLE001 — one bad file must not abort the whole batch; recorded, not swallowed
            logger.error(f"Failed to normalize {path}: {exc}")
            failed_files.append(str(path))

    output_path = config.normalized_dir / "normalized_docs.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for doc in all_docs:
            f.write(json.dumps(doc.__dict__, ensure_ascii=False) + "\n")

    logger.info(f"Normalized {len(all_docs)} docs from {len(jsonl_files)} file(s) -> {output_path}")
    if failed_files:
        logger.error(f"{len(failed_files)} file(s) failed: {failed_files}")
    return {"files": len(jsonl_files), "docs": len(all_docs), "failed_files": failed_files, "output": str(output_path)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize OCR/transcript ContentRecord JSONL for the KB pipeline.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--input", type=Path, action="append", default=None, help="Override input directory (repeatable). Default: config's ocr_output_dir + transcripts_dir.")
    parser.add_argument("--sample", type=int, default=None, help="Only process the first N input files — for a quick test, per Phase 10.")
    parser.add_argument("--allow-pending", action="store_true", help="Also normalize qa_status=='pending' records (development only — mirrors scripts.build_knowledge_base's existing --allow-pending convention).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    result = run(config, input_dirs=args.input, sample=args.sample, allow_pending=args.allow_pending)
    return 0 if not result.get("failed_files") else 1


if __name__ == "__main__":
    raise SystemExit(main())
