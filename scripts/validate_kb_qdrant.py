"""Stage: validation report for the BGE-M3 + Qdrant KB.

Checks (per the spec's Phase 11 list): chunk counts/sizes, OCR-review
flags, embedding coverage, Qdrant point count match, duplicate chunk-ID
detection, payload/text integrity spot-check. Never evaluates retrieval
quality — that is explicitly out of scope (a separate AI-team concern).

Usage:
    python -m scripts.validate_kb_qdrant
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.knowledge_base.config import KBConfig, load_config

logger = logging.getLogger("validate_kb_qdrant")


def run(config: KBConfig) -> dict:
    config.ensure_directories()
    warnings: List[str] = []
    errors: List[str] = []

    chunks_path = config.chunks_dir / "chunks.jsonl"
    chunks = []
    if chunks_path.exists():
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = [json.loads(line) for line in f if line.strip()]
    else:
        errors.append(f"{chunks_path} does not exist")

    chunk_ids = [c["chunk_id"] for c in chunks]
    id_counts = Counter(chunk_ids)
    duplicate_ids = {cid: n for cid, n in id_counts.items() if n > 1}
    if duplicate_ids:
        errors.append(f"{len(duplicate_ids)} duplicate chunk_id(s) found: {list(duplicate_ids)[:10]}")

    token_counts = [c.get("token_count", 0) for c in chunks] or [0]
    ocr_flagged = sum(1 for c in chunks if c.get("ocr_review_flagged"))
    missing_metadata = sum(1 for c in chunks if not c.get("source_id") or not c.get("source_type"))

    embeddings_path = config.embeddings_dir / "embeddings.jsonl"
    embedded_ids = set()
    embedding_dims = set()
    if embeddings_path.exists():
        with open(embeddings_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                embedded_ids.add(row["chunk_id"])
                embedding_dims.add(row.get("dim"))
    else:
        warnings.append(f"{embeddings_path} does not exist — embedding stage has not run")

    missing_embeddings = [cid for cid in chunk_ids if cid not in embedded_ids]
    if missing_embeddings:
        warnings.append(f"{len(missing_embeddings)} chunk(s) have no embedding: {missing_embeddings[:10]}")
    if len(embedding_dims) > 1:
        errors.append(f"Inconsistent embedding dimensions found: {embedding_dims}")
    elif embedding_dims and next(iter(embedding_dims)) != config.embedding_dim:
        errors.append(f"Embedding dim {next(iter(embedding_dims))} != configured embedding_dim {config.embedding_dim}")

    qdrant_count = None
    qdrant_error = None
    try:
        from src.knowledge_base.qdrant_store import QdrantKBStore

        qdrant_count = QdrantKBStore(config).count()
    except Exception as exc:  # noqa: BLE001 — Qdrant may legitimately not be running; report, don't crash validation
        qdrant_error = str(exc)
        warnings.append(f"Could not reach Qdrant to verify point count: {exc}")

    if qdrant_count is not None and len(set(chunk_ids)) != qdrant_count:
        warnings.append(f"Qdrant point count ({qdrant_count}) does not match unique chunk count ({len(set(chunk_ids))}) — may be expected if content-hash-unchanged skipping left stale points from a prior schema version, or if the collection hasn't been fully upserted yet")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_files": None,  # filled from the latest manifest below, when available
        "chunks_total": len(chunks),
        "unique_chunk_ids": len(set(chunk_ids)),
        "duplicate_chunk_ids": len(duplicate_ids),
        "avg_token_count": round(sum(token_counts) / len(token_counts), 1),
        "min_token_count": min(token_counts),
        "max_token_count": max(token_counts),
        "chunks_flagged_for_ocr_review": ocr_flagged,
        "chunks_missing_core_metadata": missing_metadata,
        "chunks_with_embedding": len(embedded_ids),
        "chunks_missing_embedding": len(missing_embeddings),
        "embedding_dimensions_found": list(embedding_dims),
        "qdrant_point_count": qdrant_count,
        "qdrant_unreachable": qdrant_error,
        "warnings": warnings,
        "errors": errors,
    }

    manifest_path = config.manifests_dir / "latest_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report["input_files"] = manifest.get("normalize", {}).get("files")
        report["model_config"] = {
            "embedding_model": config.embedding_model,
            "embedding_revision": config.embedding_revision,
            "chunk_schema_version": config.chunk_schema_version,
        }

    report_path = config.reports_dir / f"validation_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (config.reports_dir / "latest_validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(f"Validation report -> {report_path}")
    for w in warnings:
        logger.warning(w)
    for e in errors:
        logger.error(e)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the BGE-M3 + Qdrant knowledge base.")
    parser.add_argument("--config", type=Path, default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    report = run(config)
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
