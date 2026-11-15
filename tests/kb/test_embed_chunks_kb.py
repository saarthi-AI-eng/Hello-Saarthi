from __future__ import annotations

import json
import sys
import types

import pytest

import scripts.embed_chunks_kb as embed_chunks_kb


class _FakeBGEM3Model:
    calls = 0

    def __init__(self, *a, **k):
        pass

    def encode(self, texts, **kwargs):
        _FakeBGEM3Model.calls += len(texts)
        return {"dense_vecs": [[0.1] * 1024 for _ in texts]}


@pytest.fixture(autouse=True)
def fake_flagembedding(monkeypatch):
    _FakeBGEM3Model.calls = 0
    module = types.ModuleType("FlagEmbedding")
    module.BGEM3FlagModel = _FakeBGEM3Model
    monkeypatch.setitem(sys.modules, "FlagEmbedding", module)


def _write_chunks(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_bare_rerun_skips_unchanged_chunks_without_loading_model(kb_config):
    chunks_path = kb_config.chunks_dir / "chunks.jsonl"
    _write_chunks(chunks_path, [{"chunk_id": "c1", "text": "hello", "content_hash": "h1"}])

    first = embed_chunks_kb.run(kb_config)
    assert first["newly_embedded"] == 1
    assert _FakeBGEM3Model.calls == 1

    second = embed_chunks_kb.run(kb_config)  # bare re-run, no flags
    assert second["skipped_unchanged"] == 1
    assert second["newly_embedded"] == 0
    assert _FakeBGEM3Model.calls == 1  # model never called again — the whole point of being hash-aware


def test_changed_content_hash_triggers_re_embedding(kb_config):
    chunks_path = kb_config.chunks_dir / "chunks.jsonl"
    _write_chunks(chunks_path, [{"chunk_id": "c1", "text": "hello", "content_hash": "h1"}])
    embed_chunks_kb.run(kb_config)

    _write_chunks(chunks_path, [{"chunk_id": "c1", "text": "hello EDITED", "content_hash": "h2"}])
    result = embed_chunks_kb.run(kb_config)

    assert result["newly_embedded"] == 1
    assert result["skipped_unchanged"] == 0


def test_force_re_embeds_even_unchanged_chunks(kb_config):
    chunks_path = kb_config.chunks_dir / "chunks.jsonl"
    _write_chunks(chunks_path, [{"chunk_id": "c1", "text": "hello", "content_hash": "h1"}])
    embed_chunks_kb.run(kb_config)

    result = embed_chunks_kb.run(kb_config, force=True)

    assert result["newly_embedded"] == 1
    assert result["skipped_unchanged"] == 0


def test_output_order_matches_input_chunk_order(kb_config):
    chunks_path = kb_config.chunks_dir / "chunks.jsonl"
    _write_chunks(chunks_path, [
        {"chunk_id": "c3", "text": "third", "content_hash": "h3"},
        {"chunk_id": "c1", "text": "first", "content_hash": "h1"},
        {"chunk_id": "c2", "text": "second", "content_hash": "h2"},
    ])

    embed_chunks_kb.run(kb_config)

    rows = [json.loads(l) for l in (kb_config.embeddings_dir / "embeddings.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["chunk_id"] for r in rows] == ["c3", "c1", "c2"]


def test_raises_clear_error_when_chunks_file_missing(kb_config):
    with pytest.raises(FileNotFoundError, match="chunk_content_kb"):
        embed_chunks_kb.run(kb_config)
