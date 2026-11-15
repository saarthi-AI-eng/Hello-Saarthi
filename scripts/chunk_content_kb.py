"""Stage 2 of the BGE-M3 + Qdrant KB pipeline: structural + semantic-aware
+ size-aware chunking. Reads normalized_docs.jsonl (stage 1's output),
writes chunks.jsonl.

Usage:
    python -m scripts.chunk_content_kb
    python -m scripts.chunk_content_kb --semantic-boundaries   # loads BGE-M3 to detect semantic boundaries too (slower, needs the model)
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

from src.knowledge_base.chunker import chunk_documents
from src.knowledge_base.config import KBConfig, load_config
from src.knowledge_base.schema import NormalizedDoc

logger = logging.getLogger("chunk_content_kb")


def load_normalized_docs(path: Path) -> List[NormalizedDoc]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist — run `python -m scripts.normalize_content_kb` first.")
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    for line_number, line in enumerate(tqdm(lines, desc="Loading normalized docs", unit="doc"), start=1):
        try:
            docs.append(NormalizedDoc(**json.loads(line)))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"Malformed NormalizedDoc at {path}:{line_number}: {exc}") from exc
    return docs


def run(config: KBConfig, semantic_boundaries: bool = False) -> dict:
    config.ensure_directories()
    docs = load_normalized_docs(config.normalized_dir / "normalized_docs.jsonl")

    embed_fn = None
    if semantic_boundaries:
        from src.knowledge_base.embedder import BGEEmbedder
        embedder = BGEEmbedder(config)
        embed_fn = lambda texts: embedder.embed_texts(texts, show_progress=False)  # noqa: E731

    config_for_run = config
    if not semantic_boundaries:
        # Explicit, not implicit: a run without --semantic-boundaries must
        # not silently also skip it due to some other code path forgetting
        # to pass embed_fn — the config flag and the embed_fn argument
        # agree here by construction.
        config_for_run.semantic_boundary_detection = False

    chunks = chunk_documents(docs, config_for_run, embed_fn=embed_fn)

    output_path = config.chunks_dir / "chunks.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")

    token_counts = [c.token_count for c in chunks] or [0]
    stats = {
        "docs_in": len(docs),
        "chunks_out": len(chunks),
        "avg_tokens": round(sum(token_counts) / len(token_counts), 1),
        "min_tokens": min(token_counts),
        "max_tokens": max(token_counts),
        "equation_chunks": sum(1 for c in chunks if c.has_equation),
        "ocr_review_flagged": sum(1 for c in chunks if c.ocr_review_flagged),
        "output": str(output_path),
    }
    logger.info(f"Chunked {stats['docs_in']} docs -> {stats['chunks_out']} chunks -> {output_path}")
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chunk normalized docs for the KB pipeline.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--semantic-boundaries", action="store_true", help="Also use BGE-M3 embeddings to refine chunk boundaries (slower; loads the embedding model).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(config, semantic_boundaries=args.semantic_boundaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
