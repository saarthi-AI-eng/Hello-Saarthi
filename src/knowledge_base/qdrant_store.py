"""Qdrant collection management: creation, idempotent upsert, and the
point-ID scheme. Lazy-imports qdrant_client so nothing that only
chunks/embeds needs it installed.

Idempotency: Qdrant point IDs must be a UUID or unsigned int, not an
arbitrary string — chunk_id (a "chunk_<hex>" string) is deterministically
mapped to a UUID5 so the SAME chunk_id always produces the SAME point ID
across runs/machines (stable, not random), satisfying "use deterministic
point IDs based on stable chunk IDs" without fighting Qdrant's ID type
restriction. content_hash is stored in the payload specifically so a
re-run can skip re-upserting a point whose content hasn't changed
("unchanged chunks should not be needlessly re-embedded or re-uploaded").
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Iterable, List, Optional

from src.knowledge_base.config import KBConfig
from src.knowledge_base.schema import Chunk

logger = logging.getLogger("kb.qdrant_store")

_POINT_ID_NAMESPACE = uuid.UUID("f4b8c9a0-1234-4e56-8abc-def012345678")  # fixed, arbitrary — only needs to be stable across runs, never regenerated


def chunk_id_to_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, chunk_id))


class QdrantKBStore:
    def __init__(self, config: KBConfig):
        self.config = config
        self._client = None

    def _ensure_client(self):
        """The one centralized Qdrant client factory — every script in
        this repo goes through QdrantKBStore, never constructs a
        QdrantClient directly, so backend selection (local vs Qdrant
        Cloud) lives in exactly one place. Never logs or raises an
        exception containing the actual api_key value, even on a cloud
        validation failure."""
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError(
                "qdrant-client is not installed. Install it with `pip install -r "
                "requirements-kb.txt` (see docs/KB_PIPELINE_SETUP.md)."
            ) from exc

        backend = (self.config.qdrant_backend or "local").strip().lower()
        if backend not in ("local", "cloud"):
            raise ValueError(f"Invalid qdrant_backend {backend!r} — must be 'local' or 'cloud'.")

        if backend == "cloud":
            url = self.config.qdrant_cloud_url
            api_key = self.config.qdrant_cloud_api_key
            if not url:
                raise ValueError(
                    "QDRANT_BACKEND=cloud requires QDRANT_CLOUD_URL to be set (in .env.kb) — "
                    "see docs/CLOUD_QDRANT_PIPELINE.md."
                )
            if not api_key:
                raise ValueError(
                    "QDRANT_BACKEND=cloud requires QDRANT_CLOUD_API_KEY to be set (in .env.kb) — "
                    "see docs/CLOUD_QDRANT_PIPELINE.md."
                )
            if not url.startswith("https://"):
                raise ValueError(
                    "QDRANT_CLOUD_URL must use https:// — Qdrant Cloud requires a secure connection."
                )
        else:
            url = self.config.qdrant_url
            # api_key=None is valid and expected for a local, unauthenticated
            # Qdrant instance — never required for local development.
            api_key = self.config.qdrant_api_key or None

        logger.info(f"Connecting to Qdrant ({backend} backend) at {url}")  # api_key deliberately never logged
        self._client = QdrantClient(url=url, api_key=api_key)
        return self._client

    def verify_connection(self) -> bool:
        """Lightweight connectivity check for either backend. Raises a
        clear RuntimeError on failure that includes only the backend name
        and exception TYPE — never the raw exception text, since a wrapped
        HTTP client error could in principle echo back request details."""
        client = self._ensure_client()
        backend = (self.config.qdrant_backend or "local").strip().lower()
        try:
            client.get_collections()
            return True
        except Exception as exc:  # noqa: BLE001 — deliberately re-raised narrow, never the raw exception text
            raise RuntimeError(
                f"Could not connect to Qdrant ({backend} backend): {type(exc).__name__}"
            ) from None

    def ensure_collection(self, recreate: bool = False) -> None:
        from qdrant_client.models import Distance, VectorParams

        client = self._ensure_client()
        exists = client.collection_exists(self.config.qdrant_collection)
        if exists and recreate:
            logger.warning(f"Recreating collection {self.config.qdrant_collection!r} — all existing points will be deleted.")
            client.delete_collection(self.config.qdrant_collection)
            exists = False
        if not exists:
            client.create_collection(
                collection_name=self.config.qdrant_collection,
                vectors_config=VectorParams(size=self.config.embedding_dim, distance=Distance.COSINE),
            )
            logger.info(f"Created collection {self.config.qdrant_collection!r} (dim={self.config.embedding_dim}, distance=COSINE).")

    def existing_content_hashes(self, chunk_ids: Iterable[str]) -> Dict[str, str]:
        """{chunk_id: content_hash already stored in Qdrant}, for the
        subset of chunk_ids that already exist as points — used to skip
        re-upserting unchanged chunks."""
        client = self._ensure_client()
        point_ids = [chunk_id_to_point_id(cid) for cid in chunk_ids]
        id_to_chunk_id = {chunk_id_to_point_id(cid): cid for cid in chunk_ids}
        found: Dict[str, str] = {}
        # Qdrant's retrieve() takes a bounded list; chunk in batches of 256 to stay well under any server-side request-size limit.
        for start in range(0, len(point_ids), 256):
            batch = point_ids[start:start + 256]
            records = client.retrieve(collection_name=self.config.qdrant_collection, ids=batch, with_payload=["content_hash"])
            for record in records:
                found[id_to_chunk_id[str(record.id)]] = (record.payload or {}).get("content_hash", "")
        return found

    def upsert_chunks(self, chunks: List[Chunk], vectors_by_chunk_id: Dict[str, List[float]], force: bool = False) -> dict:
        """Idempotent: skips a chunk whose content_hash already matches
        what's stored, unless force=True. Never silently drops a chunk
        that's missing its vector — counted as skipped_no_vector, not
        uploaded as a zero/fake vector."""
        from qdrant_client.models import PointStruct

        self.ensure_collection(recreate=False)
        existing_hashes = {} if force else self.existing_content_hashes([c.chunk_id for c in chunks])

        points = []
        skipped_unchanged = 0
        skipped_no_vector = 0
        for chunk in chunks:
            vector = vectors_by_chunk_id.get(chunk.chunk_id)
            if vector is None:
                skipped_no_vector += 1
                continue
            if not force and existing_hashes.get(chunk.chunk_id) == chunk.content_hash:
                skipped_unchanged += 1
                continue
            points.append(PointStruct(id=chunk_id_to_point_id(chunk.chunk_id), vector=vector, payload=chunk.to_payload()))

        client = self._ensure_client()
        uploaded = 0
        failed_batches = 0
        for start in range(0, len(points), self.config.qdrant_upsert_batch_size):
            batch = points[start:start + self.config.qdrant_upsert_batch_size]
            try:
                client.upsert(collection_name=self.config.qdrant_collection, points=batch, wait=True)
                uploaded += len(batch)
            except Exception as exc:  # noqa: BLE001 — one failed batch must not abort the whole upload; recorded, not silently dropped
                logger.error(f"Upsert failed for a batch of {len(batch)} point(s): {exc}")
                failed_batches += 1

        return {
            "chunks_total": len(chunks),
            "uploaded": uploaded,
            "skipped_unchanged": skipped_unchanged,
            "skipped_no_vector": skipped_no_vector,
            "failed_batches": failed_batches,
        }

    def count(self) -> int:
        client = self._ensure_client()
        if not client.collection_exists(self.config.qdrant_collection):
            return 0
        return client.count(self.config.qdrant_collection, exact=True).count
