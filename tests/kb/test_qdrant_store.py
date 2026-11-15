"""Real integration tests against qdrant-client's in-memory mode
(QdrantClient(":memory:")) — exercises the actual Qdrant wire protocol
logic without needing Docker or a running server. A separate,
explicitly-opt-in test against a real local Qdrant server (started via
docker-compose.kb.yml) is in test_qdrant_store_live.py."""
from __future__ import annotations

from qdrant_client import QdrantClient

from src.knowledge_base.qdrant_store import QdrantKBStore, chunk_id_to_point_id
from src.knowledge_base.schema import Chunk


def _store(kb_config) -> QdrantKBStore:
    store = QdrantKBStore(kb_config)
    store._client = QdrantClient(":memory:")  # bypass the real-server connection; same client type
    return store


def _chunk(chunk_id="chunk_a", text="hello", content_hash="h1") -> Chunk:
    return Chunk(chunk_id=chunk_id, source_id="S1", source_type="pdf_note", source_file="f.pdf", text=text, content_hash=content_hash)


def test_chunk_id_to_point_id_is_deterministic():
    assert chunk_id_to_point_id("chunk_abc") == chunk_id_to_point_id("chunk_abc")
    assert chunk_id_to_point_id("chunk_abc") != chunk_id_to_point_id("chunk_def")


def test_ensure_collection_creates_once_and_is_idempotent(kb_config):
    store = _store(kb_config)

    store.ensure_collection()
    store.ensure_collection()  # must not raise or duplicate on a second call

    assert store.count() == 0


def test_upsert_uploads_new_chunks(kb_config):
    store = _store(kb_config)
    chunks = [_chunk("chunk_a"), _chunk("chunk_b")]
    vectors = {"chunk_a": [0.1] * kb_config.embedding_dim, "chunk_b": [0.2] * kb_config.embedding_dim}

    result = store.upsert_chunks(chunks, vectors)

    assert result["uploaded"] == 2
    assert result["skipped_unchanged"] == 0
    assert store.count() == 2


def test_upsert_is_idempotent_for_unchanged_content(kb_config):
    store = _store(kb_config)
    chunk = _chunk("chunk_a", content_hash="h1")
    vectors = {"chunk_a": [0.1] * kb_config.embedding_dim}
    store.upsert_chunks([chunk], vectors)

    result = store.upsert_chunks([chunk], vectors)  # re-run with identical content_hash

    assert result["uploaded"] == 0
    assert result["skipped_unchanged"] == 1
    assert store.count() == 1  # no duplicate point


def test_upsert_re_embeds_when_content_hash_changes(kb_config):
    store = _store(kb_config)
    vectors = {"chunk_a": [0.1] * kb_config.embedding_dim}
    store.upsert_chunks([_chunk("chunk_a", content_hash="h1")], vectors)

    changed_vectors = {"chunk_a": [0.9] * kb_config.embedding_dim}
    result = store.upsert_chunks([_chunk("chunk_a", content_hash="h2")], changed_vectors)

    assert result["uploaded"] == 1
    assert store.count() == 1  # still one point — updated in place, not duplicated


def test_upsert_skips_chunks_with_no_vector_without_failing(kb_config):
    store = _store(kb_config)
    chunks = [_chunk("chunk_a"), _chunk("chunk_b")]
    vectors = {"chunk_a": [0.1] * kb_config.embedding_dim}  # chunk_b has none

    result = store.upsert_chunks(chunks, vectors)

    assert result["uploaded"] == 1
    assert result["skipped_no_vector"] == 1


def test_force_rebuild_re_uploads_even_unchanged_content(kb_config):
    store = _store(kb_config)
    chunk = _chunk("chunk_a", content_hash="h1")
    vectors = {"chunk_a": [0.1] * kb_config.embedding_dim}
    store.upsert_chunks([chunk], vectors)

    result = store.upsert_chunks([chunk], vectors, force=True)

    assert result["uploaded"] == 1
    assert result["skipped_unchanged"] == 0


def test_payload_round_trips_chunk_metadata(kb_config):
    store = _store(kb_config)
    chunk = _chunk("chunk_a")
    chunk.course = "DSP"
    chunk.page = 4
    store.upsert_chunks([chunk], {"chunk_a": [0.1] * kb_config.embedding_dim})

    points, _ = store._client.scroll(kb_config.qdrant_collection, limit=10, with_payload=True)

    assert points[0].payload["course"] == "DSP"
    assert points[0].payload["page"] == 4
    assert points[0].payload["text"] == "hello"
