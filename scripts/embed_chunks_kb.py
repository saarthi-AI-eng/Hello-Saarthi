"""Stage 3: BGE-M3 embedding generation for chunks.jsonl (stage 2's output).

Content-hash-aware by default — not just on --resume: every chunk is
checked against embeddings.checkpoint.jsonl's recorded content_hash for
that chunk_id, and only (re-)embedded if the hash doesn't match (new
chunk, or an existing chunk whose text actually changed). This is what
makes a bare re-run (no flags) skip unchanged chunks — satisfying "do
not needlessly re-embed unchanged chunks" as the DEFAULT, not something
--resume has to be remembered to enable. --force bypasses this entirely
and re-embeds every chunk regardless of hash (e.g. after an embedding
model/revision change).

On a clean, complete run, embeddings.jsonl is written as the final,
order-matching-input artifact; the checkpoint file is left in place
(harmless — a later run just finds nothing changed to re-embed).

Usage:
    python -m scripts.embed_chunks_kb
    python -m scripts.embed_chunks_kb --force
    python -m scripts.embed_chunks_kb --device cpu --batch-size 8
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

from src.knowledge_base.config import KBConfig, load_config
from src.knowledge_base.embedder import BGEEmbedder, append_checkpoint, load_checkpoint

logger = logging.getLogger("embed_chunks_kb")


def run(config: KBConfig, force: bool = False) -> dict:
    config.ensure_directories()
    chunks_path = config.chunks_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"{chunks_path} does not exist — run `python -m scripts.chunk_content_kb` first.")

    chunk_rows = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunk_rows.append(json.loads(line))

    checkpoint_path = config.embeddings_dir / "embeddings.checkpoint.jsonl"
    checkpoint = {} if force else load_checkpoint(checkpoint_path)
    # {chunk_id: vector}, kept separately from `checkpoint` (which also
    # carries content_hash) purely for the final-artifact write below.
    already_done = {cid: entry["vector"] for cid, entry in checkpoint.items()}

    def _is_unchanged(row: dict) -> bool:
        entry = checkpoint.get(row["chunk_id"])
        return entry is not None and entry.get("content_hash") == row.get("content_hash", "")

    pending = [row for row in chunk_rows if not _is_unchanged(row)]
    skipped_unchanged = len(chunk_rows) - len(pending)
    if skipped_unchanged:
        logger.info(f"{skipped_unchanged} chunk(s) unchanged since the last run (same chunk_id + content_hash) — skipping re-embedding.")

    embedder = BGEEmbedder(config)

    failed: List[str] = []
    interval = config.embedding_checkpoint_interval
    for start in tqdm(range(0, len(pending), interval), desc="Embedding chunks", unit="batch"):
        batch = pending[start:start + interval]
        texts = [row["text"] for row in batch]
        try:
            vectors = embedder.embed_texts(texts)
        except Exception as exc:  # noqa: BLE001 — one failed batch must not abort the whole job; recorded, not silently skipped
            logger.error(f"Embedding failed for chunks {[r['chunk_id'] for r in batch]}: {exc}")
            failed.extend(r["chunk_id"] for r in batch)
            continue
        for row, vector in zip(batch, vectors):
            already_done[row["chunk_id"]] = vector
            append_checkpoint(checkpoint_path, row["chunk_id"], vector, content_hash=row.get("content_hash", ""))

    # Final artifact: ordered to match chunks.jsonl's input order exactly.
    output_path = config.embeddings_dir / "embeddings.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for row in chunk_rows:
            vector = already_done.get(row["chunk_id"])
            if vector is None:
                continue  # failed chunk — not written as a fabricated/zero vector
            f.write(json.dumps({"chunk_id": row["chunk_id"], "vector": vector, "dim": len(vector)}, ensure_ascii=False) + "\n")

    stats = {
        "chunks_total": len(chunk_rows),
        "embedded": len(already_done),
        "skipped_unchanged": skipped_unchanged,
        "newly_embedded": len(pending) - len(failed),
        "failed": len(failed),
        "failed_chunk_ids": failed,
        "device": embedder.device,
        "output": str(output_path),
    }
    logger.info(f"Embedded {stats['embedded']}/{stats['chunks_total']} chunks ({len(failed)} failed) on device={embedder.device} -> {output_path}")
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate BGE-M3 embeddings for chunks.jsonl.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--resume", action="store_true", help="No-op kept for CLI-shape compatibility — content-hash-aware skipping of unchanged chunks is now the unconditional default (see this module's docstring). Use --force for the opposite behavior.")
    parser.add_argument("--force", action="store_true", help="Re-embed every chunk, ignoring content-hash matches (e.g. after an embedding model/revision change).")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    if args.device:
        config.embedding_device = args.device
    if args.batch_size:
        config.embedding_batch_size = args.batch_size
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    result = run(config, force=args.force)
    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
