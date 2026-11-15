"""Opt-in integration test against a REAL, running Qdrant server (e.g.
started via `docker compose -f docker-compose.kb.yml up -d`). Skipped by
default — the normal test suite never depends on Docker or a live
service. Enable with:

    SAARTHI_KB_TEST_LIVE_QDRANT=1 pytest tests/kb/test_qdrant_store_live.py
"""
from __future__ import annotations

import os
import uuid

import pytest

from src.knowledge_base.qdrant_store import QdrantKBStore
from src.knowledge_base.schema import Chunk

pytestmark = pytest.mark.skipif(
    os.environ.get("SAARTHI_KB_TEST_LIVE_QDRANT", "").strip() != "1",
    reason="Set SAARTHI_KB_TEST_LIVE_QDRANT=1 to run this against a real Qdrant server (see docker-compose.kb.yml).",
)


def test_live_qdrant_roundtrip(kb_config):
    kb_config.qdrant_collection = f"saarthi_kb_livetest_{uuid.uuid4().hex[:8]}"  # isolated, disposable collection
    store = QdrantKBStore(kb_config)
    try:
        store.ensure_collection()
        chunk = Chunk(chunk_id="chunk_live", source_id="S1", source_type="pdf_note", source_file="f.pdf", text="live test", content_hash="h1")
        result = store.upsert_chunks([chunk], {"chunk_live": [0.1] * kb_config.embedding_dim})

        assert result["uploaded"] == 1
        assert store.count() == 1
    finally:
        client = store._ensure_client()
        if client.collection_exists(kb_config.qdrant_collection):
            client.delete_collection(kb_config.qdrant_collection)  # never leave test junk on a real server
