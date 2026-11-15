"""BGE-M3 embedding generation. Lazy-imports FlagEmbedding (not a hard
dependency of this module or of anything that only chunks/validates) —
same pattern scripts/ingest_notes.py already uses for pytesseract/
paddleocr, so importing this file never requires the model library or
weights to be present.

Device selection mirrors scripts.ingest_notes._detect_paddleocr_device:
auto-detect via the ML framework itself (torch here, since FlagEmbedding
runs on torch), never hardcoded to a specific GPU, always falls back to
CPU rather than crashing.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from src.knowledge_base.config import KBConfig

logger = logging.getLogger("kb.embedder")


def detect_embedding_device(requested: str = "auto") -> str:
    """requested: "auto" | "cuda" | "cpu". Never assumes a GPU — checks
    torch.cuda.is_available() at runtime, same reasoning as the OCR
    pipeline's own GPU auto-detection."""
    if requested in ("cuda", "cpu"):
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception as exc:  # noqa: BLE001 — detection must never crash startup
        logger.warning(f"GPU detection for embeddings failed ({exc}); falling back to CPU.")
        return "cpu"


class BGEEmbedder:
    """Lazy-loaded (model only loads on first .embed_texts() call), one
    instance = one loaded model, reused across batches — avoids reloading
    the model per chunk/batch."""

    def __init__(self, config: KBConfig):
        self.config = config
        self._model = None
        self.device = detect_embedding_device(config.embedding_device)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise RuntimeError(
                "FlagEmbedding is not installed. Install it with `pip install -r "
                "requirements-kb.txt` (see docs/KB_PIPELINE_SETUP.md) — this downloads "
                f"the {self.config.embedding_model} model (~2.2GB) to "
                f"{self.config.models_cache_dir} on first use."
            ) from exc

        logger.info(f"Loading {self.config.embedding_model} (revision={self.config.embedding_revision}, device={self.device})...")
        self._model = BGEM3FlagModel(
            self.config.embedding_model,
            use_fp16=(self.device == "cuda"),
            devices=[self.device] if self.device == "cuda" else None,
            cache_dir=str(self.config.models_cache_dir),
            revision=self.config.embedding_revision if self.config.embedding_revision != "main" else None,
        )

    def embed_texts(self, texts: List[str], show_progress: bool = True) -> List[List[float]]:
        """Dense embeddings only, per the spec (no sparse/multi-vector).
        Batches internally at config.embedding_batch_size; on a CUDA OOM,
        halves the batch size once and retries rather than failing the
        whole call outright (never silently drops a text — either it
        gets an embedding or an exception propagates naming which batch
        failed)."""
        self._ensure_loaded()
        batch_size = self.config.embedding_batch_size
        vectors: List[List[float]] = []

        i = 0
        while i < len(texts):
            batch = texts[i:i + batch_size]
            try:
                output = self._model.encode(batch, batch_size=len(batch), max_length=8192, return_dense=True, return_sparse=False, return_colbert_vecs=False)
                vectors.extend([v.tolist() if hasattr(v, "tolist") else list(v) for v in output["dense_vecs"]])
                i += len(batch)
            except RuntimeError as exc:  # noqa: BLE001 — specifically retry-on-OOM, re-raise everything else
                if "out of memory" not in str(exc).lower() or batch_size <= 1:
                    raise
                logger.warning(f"CUDA OOM at batch_size={batch_size}; halving and retrying this batch.")
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:  # noqa: BLE001 — best-effort cache clear only
                    pass
                batch_size = max(1, batch_size // 2)

        return vectors


def load_checkpoint(path) -> dict:
    """{chunk_id: {"vector": [...], "content_hash": "..."}} already
    embedded in a prior run. content_hash is stored alongside the vector
    (not just the chunk_id) so a chunk whose ID is unchanged but whose
    TEXT changed — a real edit, not just a re-run — is correctly
    detected as needing re-embedding rather than skipped on the strength
    of a stale, no-longer-matching vector. This is what makes a bare
    (non---resume) re-run content-hash-aware, per Phase 9's "unchanged
    chunks should not be needlessly re-embedded" requirement."""
    import json
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        return {}
    done = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            done[row["chunk_id"]] = {"vector": row["vector"], "content_hash": row.get("content_hash", "")}
    return done


def append_checkpoint(path, chunk_id: str, vector: List[float], content_hash: str = "") -> None:
    import json
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"chunk_id": chunk_id, "vector": vector, "content_hash": content_hash}) + "\n")
